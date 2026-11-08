"""按用户的运行时配置解析与保存（BYOK）。

设计要点：
- 每个登录用户拥有独立一套服务配置（大模型 / 高德 / Tavily 的 Key 等），
  保存在 `user_configs` 表（见 app.models.user_config.UserConfig），一个用户一条记录。
- 解析时「用户自己填写的值优先，未填写字段回退到项目根 `.env` 的全局默认值」，
  因此未配置任何 Key 的新用户开箱即用（沿用部署方的默认配置），
  填了 Key 的用户则使用自己的 Key。
- 供对话图（LLM / 高德 / Tavily 工具）与配置接口共同消费，保证口径一致。
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from app.core.runtime_config import get_runtime_config

# 字段名 -> 从 .env 兜底读取时使用的 RuntimeConfig 属性名（两者命名一致，这里显式列出）。
_FIELDS: tuple[str, ...] = (
    "openai_api_key",
    "openai_base_url",
    "openai_model",
    "openai_temperature",
    "amap_web_key",
    "amap_js_key",
    "tavily_api_key",
    "tavily_mcp_command",
)


def _db_config(user_id: Optional[int]) -> Dict[str, Optional[str]]:
    """读取用户自己的配置记录；不存在或读库失败时返回全空（后续走 .env 兜底）。"""
    empty: Dict[str, Optional[str]] = {f: None for f in _FIELDS}
    if user_id is None:
        return empty
    try:
        from app.db.session import SessionLocal
        from app.models.user_config import UserConfig

        with SessionLocal() as session:
            row = (
                session.query(UserConfig)
                .filter(UserConfig.user_id == user_id)
                .first()
            )
        if row is None:
            return empty
        return {f: getattr(row, f, None) for f in _FIELDS}
    except Exception:  # noqa: BLE001 表未建/连接异常等：降级为 .env 兜底
        return empty


def resolve_user_config(user_id: Optional[int] = None) -> Dict[str, str]:
    """返回合并后的完整配置：用户自填值优先，缺失字段回退到 `.env`。

    返回的字典键与 `_FIELDS` 一致，值为非空字符串（未配置时为空串）。
    """
    defaults = get_runtime_config()
    db = _db_config(user_id)
    merged: Dict[str, str] = {}
    for field in _FIELDS:
        own = (db.get(field) or "").strip()
        fallback = str(getattr(defaults, field, "") or "").strip()
        merged[field] = own or fallback
    return merged


def get_user_config(user_id: Optional[int] = None) -> Dict[str, str]:
    """别名：按用户返回合并后的完整配置。"""
    return resolve_user_config(user_id)


def save_user_config(
    user_id: int, updates: Mapping[str, Optional[str]]
) -> Dict[str, str]:
    """保存用户自己的配置（只更新传入的字段），返回合并后的完整配置。

    :param updates: 字段名 -> 新值；值为 None 表示「不修改」。
    """
    from app.db.session import SessionLocal
    from app.models.user_config import UserConfig

    allowed = {f: (str(v).strip() if v is not None else None) for f, v in updates.items()}
    allowed = {k: v for k, v in allowed.items() if k in _FIELDS}

    with SessionLocal() as session:
        row = (
            session.query(UserConfig)
            .filter(UserConfig.user_id == user_id)
            .first()
        )
        if row is None:
            row = UserConfig(user_id=user_id)
            session.add(row)
        for field, value in allowed.items():
            if value is None:
                continue
            setattr(row, field, value)
        session.commit()

    return resolve_user_config(user_id)
