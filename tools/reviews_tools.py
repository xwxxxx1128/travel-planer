"""景点评价检索工具（基于 Tavily 网页搜索）。

评价功能不再使用自研爬虫抓取，改为调用 Tavily 网页搜索 MCP 工具获取互联网公开
游记/攻略材料（标题、摘要、来源链接），交由大模型基于这些材料聚合提炼游客评价。

关键约束（对应需求）：
- 大模型仅基于 API 返回的网页材料做聚合，严禁编造；
- 返回材料时一并提供可跳转的原始来源链接；
- 检索结果按「地点 + 城市 + time_range + max_results」缓存到本地 reviews 表
  （见 app/models/review.py）：同一地点在 REVIEW_CACHE_TTL_DAYS（默认 30 天，
  与 time_range=month 对齐）内再次询问时优先从库里返回，避免每次都现调 Tavily；
  force_refresh=True 可强制刷新。缓存读写异常时优雅降级为「直接现检索」。
- 若检索命中有限（部分站点反爬仅返回摘要），如实呈现有限信息；未命中则如实告知。
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from langchain_core.tools import tool

from tools.mcp_tavily_client import TavilyMcpClient
from tools.poi_normalize import cache_key

logger = logging.getLogger(__name__)
# 单次检索返回条数（可通过环境变量调整）
_TAVILY_MAX_RESULTS = int(os.getenv("TAVILY_MAX_RESULTS", "5"))
# 评价检索的时效范围：召回近一个月内的联网材料（温和时效，契合「比较新的内容」需求）。
_TAVILY_REVIEW_TIME_RANGE = os.getenv("TAVILY_REVIEW_TIME_RANGE", "month")
# 评价缓存有效期（天）：与 time_range=month 对齐，默认 30 天。
_REVIEW_CACHE_TTL_DAYS = int(os.getenv("REVIEW_CACHE_TTL_DAYS", "30"))


# ----------------------------------------------------------------------
# 评价缓存（落库）：同一地点一个月内先查库，避免重复调 Tavily。
# 缓存读写异常时优雅降级为「直接现检索」，不影响主流程。
# ----------------------------------------------------------------------
def _cache_lookup(poi_key: str, time_range: str, max_results: int) -> list[dict] | None:
    """按归一化 key 命中且未过期则返回缓存的评价条目，否则返回 None。

    poi_key 由 tools.poi_normalize.cache_key(poi_name, city) 生成，统一了
    「小珠山 / 珠山国家森林公园」等不同叫法，保证同景点复用同一份缓存。
    """
    try:
        from app.db.session import SessionLocal
        from app.models.review import Review

        with SessionLocal() as session:
            now = datetime.now()
            rows = (
                session.query(Review)
                .filter(
                    Review.poi_key == poi_key,
                    Review.time_range == time_range,
                    Review.max_results == max_results,
                    Review.expires_at > now,
                )
                .all()
            )
            if not rows:
                return None
            return [
                {
                    "poi_name": r.poi_name,
                    "city": r.city or "",
                    "title": r.title or "",
                    "url": r.url or "",
                    "content": r.content,
                    "source": r.source or "tavily",
                }
                for r in rows
            ]
    except Exception as exc:  # 表未建/连接异常等：降级为“现调 Tavily”
        logger.warning("评价缓存读取失败（key=%s）：%s（已降级为现调 Tavily）", poi_key, exc)
        return None


def _cache_store(
    poi_key: str,
    poi_name: str,
    city: str,
    time_range: str,
    max_results: int,
    items: list[dict],
) -> None:
    """写入本次检索结果（含归一化 key），并清理同 key 的旧缓存（含已过期）。"""
    try:
        from app.db.session import SessionLocal
        from app.models.review import Review

        with SessionLocal() as session:
            session.query(Review).filter(
                Review.poi_key == poi_key,
                Review.time_range == time_range,
                Review.max_results == max_results,
            ).delete()
            now = datetime.now()
            expires = now + timedelta(days=_REVIEW_CACHE_TTL_DAYS)
            for it in items:
                session.add(
                    Review(
                        poi_key=poi_key,
                        poi_name=poi_name,
                        city=city or "",
                        title=it.get("title", ""),
                        url=it.get("url", ""),
                        content=it.get("content", ""),
                        source=it.get("source", "tavily"),
                        time_range=time_range,
                        max_results=max_results,
                        fetched_at=now,
                        expires_at=expires,
                        created_at=now,
                    )
                )
            session.commit()
    except Exception as exc:  # 表未建/连接异常等：仅记日志，不阻断主流程
        logger.warning("评价缓存写入失败（key=%s）：%s（本次结果未落库）", poi_key, exc)


# 在任何调用上下文（同步路由 / 异步事件循环内）都能安全跑异步 Tavily 客户端：
# 丢到独立线程里 asyncio.run，避免「已有运行中的事件循环」冲突。
def _run_async(coro):
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


async def fetch_tavily_reviews(
    poi_name: str,
    city: str = "",
    max_results: int | None = None,
    time_range: str | None = None,
    force_refresh: bool = False,
) -> list[dict]:
    """抓取某景点的互联网公开评价/攻略材料（Tavily 网页搜索）。

    返回 [{poi_name, city, title, url, content, source}]，供计划页/评价 agent 直接使用；
    调用失败或无结果时返回空列表（由上层如实告知，不编造）。
    非强制刷新且命中未过期缓存时，直接返回库内结果，不再现调 Tavily。
    """
    resolved_max = max_results or _TAVILY_MAX_RESULTS
    resolved_tr = time_range or _TAVILY_REVIEW_TIME_RANGE
    # 归一化缓存 key（城市::规范景点名）：使同景点不同叫法命中同一份缓存
    poi_key = cache_key(poi_name, city)
    logger.info(
        "fetch_tavily_reviews 被调用 poi=%s city=%s force_refresh=%s "
        "time_range=%s max_results=%s poi_key=%s",
        poi_name, city or "-", force_refresh, resolved_tr, resolved_max, poi_key,
    )

    # 缓存优先：同地点一个月内直接返回库内结果
    if not force_refresh:
        cached = _cache_lookup(poi_key, resolved_tr, resolved_max)
        if cached is not None:
            logger.info("评价命中本地缓存（%s / %s）条数=%d", poi_name, city or "-", len(cached))
            return cached
        logger.info("评价未命中本地缓存，准备现调 Tavily（%s / %s）", poi_name, city or "-")

    query = f"{poi_name} 游客真实评价 游玩攻略 游记 推荐"
    try:
        async with TavilyMcpClient() as client:
            items = await client.search(
                query,
                max_results=resolved_max,
                time_range=resolved_tr,
            )
    except Exception as exc:  # 无 Key / Server 拉起失败 / 调用异常
        logger.warning("Tavily 评价检索失败（%s）：%s", poi_name, exc)
        return []

    # 命中结果落库缓存，供一个月内复用
    if items:
        _cache_store(poi_key, poi_name, city, resolved_tr, resolved_max, items)
        logger.info("Tavily 返回 %d 条并写入缓存（%s / %s）", len(items), poi_name, city or "-")
    else:
        logger.info("Tavily 未返回任何结果（%s / %s）", poi_name, city or "-")

    return [
        {
            "poi_name": poi_name,
            "city": city,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "source": "tavily",
        }
        for item in items
    ]


def fetch_tavily_reviews_sync(
    poi_name: str,
    city: str = "",
    max_results: int | None = None,
    time_range: str | None = None,
    force_refresh: bool = False,
) -> list[dict]:
    """同步封装：供 ReviewRAGAgent / 同步路由调用。"""
    return _run_async(
        fetch_tavily_reviews(poi_name, city, max_results, time_range, force_refresh)
    )


@tool
async def search_reviews(poi_name: str) -> str:
    """查询指定景点的游客评价/攻略素材。

    通过 Tavily 网页搜索获取该景点相关的互联网公开游记、攻略与点评材料
    （含标题、摘要与来源链接）。请基于返回的材料聚合提炼游客真实评价，
    并附上原始来源链接；严禁编造内容。材料有限时如实说明，未命中时如实告知。
    """
    logger.info("search_reviews 被调用 poi_name=%s", poi_name)
    items = await fetch_tavily_reviews(poi_name)
    if not items:
        return f"未检索到「{poi_name}」的相关网络评价材料，暂无法提供游客评价。"

    # 将网页片段实时交给大模型处理；此处仅组装材料（材料已按需从本地缓存或 Tavily 取得）。
    blocks = []
    for idx, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        content = item.get("content", "")
        blocks.append(f"[{idx}] 标题：{title}\n来源链接：{url}\n摘要：{content}")

    header = (
        f"以下是「{poi_name}」的互联网公开游记/攻略材料（共 {len(items)} 条），"
        f"请仅据此聚合提炼游客评价并附上来源链接："
    )
    return header + "\n\n" + "\n\n".join(blocks)
