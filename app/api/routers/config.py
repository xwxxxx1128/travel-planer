from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.runtime_config import get_runtime_config, save_runtime_config

router = APIRouter()

# 脱敏占位符：前端收到该值时表示"已有配置但未展示明文"，保存时不应覆盖
MASK = '******'


def mask_secret(value: str) -> str:
    """对密钥脱敏：保留后可识别前缀（如 sk-）与最后 4 位，其余打码。"""
    value = (value or '').strip()
    if not value:
        return ''
    if value.startswith('sk-'):
        return f'sk-****{value[-4:]}'
    if len(value) <= 8:
        return MASK
    return f'{value[:4]}****{value[-4:]}'


class RuntimeConfigResponse(BaseModel):
    openai_api_key: str = ''
    openai_base_url: str = ''
    amap_web_key: str = ''
    amap_js_key: str = ''


class RuntimeConfigUpdate(BaseModel):
    openai_api_key: str = Field(default='')
    openai_base_url: str = Field(default='')
    amap_web_key: str = Field(default='')
    amap_js_key: str = Field(default='')


@router.get('/runtime', response_model=RuntimeConfigResponse)
def read_runtime_config():
    runtime_config = get_runtime_config()
    return RuntimeConfigResponse(
        openai_api_key=mask_secret(runtime_config.openai_api_key),
        openai_base_url=runtime_config.openai_base_url,
        amap_web_key=mask_secret(runtime_config.amap_web_key),
        amap_js_key=mask_secret(runtime_config.amap_js_key),
    )


@router.post('/runtime', response_model=RuntimeConfigResponse)
def update_runtime_config(payload: RuntimeConfigUpdate):
    updates: dict[str, str | None] = {}

    # 仅当字段不是脱敏占位符且非空时才更新，避免误清空真实密钥
    def keep(value: str) -> bool:
        return bool(value) and value != MASK and not value.startswith('sk-****') and '****' not in value

    updates['openai_api_key'] = payload.openai_api_key if keep(payload.openai_api_key) else None
    updates['openai_base_url'] = payload.openai_base_url if payload.openai_base_url else None
    updates['amap_web_key'] = payload.amap_web_key if keep(payload.amap_web_key) else None
    updates['amap_js_key'] = payload.amap_js_key if keep(payload.amap_js_key) else None

    runtime_config = save_runtime_config(updates)
    return RuntimeConfigResponse(
        openai_api_key=mask_secret(runtime_config.openai_api_key),
        openai_base_url=runtime_config.openai_base_url,
        amap_web_key=mask_secret(runtime_config.amap_web_key),
        amap_js_key=mask_secret(runtime_config.amap_js_key),
    )
