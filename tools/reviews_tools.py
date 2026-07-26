"""景点/地点用户评价查询工具。

原仓库中该文件缺失（从未提交至 git），此处基于项目内 reviews 表结构
（见 app/models/review.py：poi_name / source / rating / label / content）重建，
供 graph_chat.assistant 的主助理工具集使用。

约定（与 graph_chat/assistant.py 提示词一致）：
- 正常时返回「评价列表」的 JSON 字符串（每条含 poi_name / source / rating / label / content）；
- 当数据库中没有该景点的评价数据时，返回包含 'fallback': True 的结果，
  以便 LLM 退而使用自身知识为用户撰写介绍。

数据库路径统一取自 tools.db（其来源为 app.core.config.TRAVEL_DB_PATH）。
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List

from langchain_core.tools import tool
from tools import db


# 单次最多返回的评价条数，避免超长上下文拖慢后续 LLM 调用。
# 原 50 条会把单条工具结果撑到数千字，直接占满历史裁剪预算、压慢下一轮 LLM；
# 8 条已足够覆盖展示与信息量，显著削减喂给模型的 token。
MAX_REVIEWS = 8


@tool
def search_reviews(poi_name: str) -> str:
    """根据用户提供的景点/地点名称查询用户评价。

    参数:
        poi_name: 景点或地点名称，例如「外滩」「故宫」。
    返回:
        JSON 字符串：评价列表（成功），或包含 'fallback': True 的提示结果（缺失/出错）。
    """
    if not poi_name or not poi_name.strip():
        return json.dumps(
            {"fallback": True, "poi_name": "", "message": "未提供景点名称。"},
            ensure_ascii=False,
        )

    poi_name = poi_name.strip()
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1) 先精确匹配地点名（最准确）
        cur.execute(
            "SELECT poi_name, source, rating, label, content "
            "FROM reviews WHERE poi_name = ?",
            (poi_name,),
        )
        rows = cur.fetchall()

        # 2) 精确无果则按关键词模糊匹配（提升召回）
        if not rows:
            cur.execute(
                "SELECT poi_name, source, rating, label, content "
                "FROM reviews WHERE poi_name LIKE ?",
                (f"%{poi_name}%",),
            )
            rows = cur.fetchall()

        conn.close()

        if not rows:
            return json.dumps(
                {
                    "fallback": True,
                    "poi_name": poi_name,
                    "message": f"暂无「{poi_name}」的评价数据，请基于常识为用户介绍。",
                },
                ensure_ascii=False,
            )

        reviews: List[Dict[str, Any]] = []
        for r in rows:
            rating = r["rating"]
            reviews.append(
                {
                    "poi_name": r["poi_name"],
                    "source": r["source"],
                    # 评分可能为 NULL，显式保留为 None 而非 0
                    "rating": rating if rating is not None else None,
                    "label": r["label"],
                    "content": r["content"],
                }
            )

        # 限制返回条数，避免上下文过长
        reviews = reviews[:MAX_REVIEWS]
        return json.dumps(reviews, ensure_ascii=False)
    except Exception as exc:  # 表不存在或查询出错时优雅降级
        return json.dumps(
            {
                "fallback": True,
                "poi_name": poi_name,
                "error": str(exc),
                "message": f"查询「{poi_name}」评价时出错。",
            },
            ensure_ascii=False,
        )
