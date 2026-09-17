"""评价意图识别 + 确定性预检索（方案3）。

问题：主助手是否调用 search_reviews 完全由大模型自主决定；对知名景点，模型常
“凭自身知识直接作答”并伪造来源链接（例如给出裸域名 https://www.ctrip.com）。

方案：在进入对话图之前，用规则识别“询问某景点评价”的意图，命中则直接调用
`fetch_tavily_reviews_sync`（内部天然先查库、未命中再调 Tavily、随后落库），
把材料作为上下文注入，从而不再依赖模型“自觉”，并复用本地评价缓存。

两条防线：
- 命中意图且有材料 → 注入【评价检索材料·预取】，指令模型仅据此作答并附来源；
- 命中意图但无材料 → 注入【评价检索结果·无材料】，指令模型如实告知、禁止编造。

可通过环境变量 REVIEW_PREFETCH_ENABLED=0 关闭本机制（回退为纯模型自主调用工具）。
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from app.services.city_names import CITIES
from tools.reviews_tools import fetch_tavily_reviews_sync

logger = logging.getLogger(__name__)

# 开关：REVIEW_PREFETCH_ENABLED=0/false/no/off 时关闭预检索
_ENABLED = os.getenv("REVIEW_PREFETCH_ENABLED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# 预取上下文标记。注意：graph_chat/assistant.py 里的后置校验依赖该前缀
# （见 _REVIEW_CTX_MARK），两处必须保持一致。
MARK_MATERIAL = "【评价检索材料·预取】"
MARK_NO_MATERIAL = "【评价检索结果·无材料】"
MARK_PREFIX = "【评价检索"

# 评价意图关键词（采用“强特征”词，命中任一才视为评价类提问，避免误触发）
_INTENT_KEYWORDS = (
    "评价", "点评", "口碑", "游记", "好评", "差评", "游客", "游人",
    "值得去", "好玩吗", "推荐吗", "游客体验", "游玩体验",
)

# 非景点类主题词：命中则不做评价预检索（“酒店评价 / 天气怎么样”等由其它工具处理）
_GENERIC_BLOCK = (
    "天气", "路线", "酒店", "机票", "航班", "门票", "交通", "美食", "餐厅",
    "住宿", "价格", "费用", "规划", "行程",
)

# 常见城市（用于从问句里粗略抽取城市；与航班意图识别共用同一份列表）
_CITIES = CITIES

# 口语化填充词（抽景点名时剥离）
_FILLER_WORDS = (
    "帮我", "请问", "麻烦", "查一下", "查询", "搜一下", "搜索", "看看", "找一下", "找",
    "了解一下", "说说", "介绍一下", "介绍", "告诉我", "想知道", "给我讲讲",
    "关于", "一下", "有吗", "吗", "呢", "啊", "呀", "吧", "的", "请",
)

_PUNCT_RE = re.compile(r"[\s,，。.、;；:：!！?？~～\-—_/\\'\"“”‘’()（）\[\]【】<>《》]+")


def is_enabled() -> bool:
    return _ENABLED


def extract_city(message: str) -> str:
    if not message:
        return ""
    for city in _CITIES:
        if city in message:
            return city
    return ""


def _extract_poi(message: str, city: str = "") -> str:
    """从问句里粗略抽取景点名（规则法，够用即可）。

    例如「青岛小珠山的游客评价怎么样」→ 剥离城市「青岛」、意图词「评价/怎么样」、
    填充词「的」→「小珠山」。
    """
    text = message or ""
    if city:
        text = text.replace(city, "")
    for c in _CITIES:
        text = text.replace(c, "")
    for kw in sorted(_INTENT_KEYWORDS, key=len, reverse=True):
        text = text.replace(kw, "")
    for w in sorted(_FILLER_WORDS, key=len, reverse=True):
        text = text.replace(w, "")
    text = _PUNCT_RE.sub("", text)
    # 控制长度，避免把整句话当景点名
    if len(text) > 20:
        text = text[:20]
    return text.strip()


def detect_review_intent(message: str) -> Optional[tuple[str, str]]:
    """命中评价意图时返回 (景点名, 城市)；否则返回 None。"""
    if not _ENABLED or not message:
        return None
    if not any(kw in message for kw in _INTENT_KEYWORDS):
        return None
    city = extract_city(message)
    poi = _extract_poi(message, city)
    if not poi or len(poi) < 2:
        return None
    # 命中通用主题词（非景点）时不预检索，避免对“酒店评价/天气”等产生误触发
    if any(block in poi for block in _GENERIC_BLOCK):
        return None
    return poi, city


def _format_material(poi: str, items: list[dict]) -> str:
    blocks = []
    for idx, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        content = item.get("content", "")
        blocks.append(f"[{idx}] 标题：{title}\n来源链接：{url}\n摘要：{content}")
    head = (
        f"{MARK_MATERIAL}\n"
        f"已为「{poi}」检索到互联网公开游记/攻略材料（共 {len(items)} 条，"
        f"来自 Tavily 联网检索或本地评价缓存）。"
        f"请仅依据以下材料聚合提炼游客评价，必须附上原始来源链接，严禁编造；"
        f"材料有限时如实说明信息有限。\n"
    )
    return head + "\n\n".join(blocks)


def _format_no_material(poi: str) -> str:
    return (
        f"{MARK_NO_MATERIAL}\n"
        f"已为「{poi}」调用评价检索（Tavily 联网 / 本地缓存），但未获取到任何材料。"
        f"请如实告知用户当前无法提供该景点的游客评价/攻略信息，"
        f"严禁凭自身知识编造评价内容或来源链接。"
    )


def build_material_context(poi: str, city: str = "") -> tuple[str, list[dict]]:
    """现调检索（内部含“缓存优先”）并返回 (上下文, 结构化条目)。

    检索异常或无结果时，降级为“无材料”上下文（引导模型如实告知、不要编造）。
    """
    try:
        items = fetch_tavily_reviews_sync(poi, city=city or "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("评价预检索失败（%s / %s）：%s", poi, city or "-", exc)
        items = []
    if items:
        return _format_material(poi, items), items
    return _format_no_material(poi), []


def no_material_context(poi: str) -> str:
    """供超时/异常分支直接构造“无材料”上下文。"""
    return _format_no_material(poi)
