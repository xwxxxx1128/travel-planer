from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services.user_config import get_user_config, save_user_config

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
    openai_model: str = ''
    openai_temperature: str = ''
    amap_web_key: str = ''
    amap_js_key: str = ''
    tavily_api_key: str = ''
    tavily_mcp_command: str = 'tavily-mcp'


class RuntimeConfigUpdate(BaseModel):
    openai_api_key: str = Field(default='')
    openai_base_url: str = Field(default='')
    openai_model: str = Field(default='')
    openai_temperature: str = Field(default='')
    amap_web_key: str = Field(default='')
    amap_js_key: str = Field(default='')
    tavily_api_key: str = Field(default='')
    tavily_mcp_command: str = Field(default='tavily-mcp')


def _to_response(cfg: dict[str, str]) -> RuntimeConfigResponse:
    """构造响应：敏感字段脱敏，但 amap_js_key 必须明文（前端浏览器加载地图要用）。"""
    return RuntimeConfigResponse(
        openai_api_key=mask_secret(cfg.get('openai_api_key', '')),
        openai_base_url=cfg.get('openai_base_url', ''),
        openai_model=cfg.get('openai_model', ''),
        openai_temperature=cfg.get('openai_temperature', ''),
        amap_web_key=mask_secret(cfg.get('amap_web_key', '')),
        # 高德 JS Key 设计上就是暴露在网页里的（非机密），且前端地图脚本需要明文加载
        amap_js_key=cfg.get('amap_js_key', ''),
        tavily_api_key=mask_secret(cfg.get('tavily_api_key', '')),
        tavily_mcp_command=cfg.get('tavily_mcp_command', '') or 'tavily-mcp',
    )


def _is_masked(value: str) -> bool:
    """判断是否为脱敏占位符（含 ****），此类值不应覆盖真实配置。"""
    return bool(value) and '****' in value


@router.get('/runtime', response_model=RuntimeConfigResponse)
def read_runtime_config(
    current: dict = Depends(get_current_user),
) -> RuntimeConfigResponse:
    """返回当前登录用户自己的配置（未填写字段已回退为全局默认值）。"""
    cfg = get_user_config(current.get('id'))
    return _to_response(cfg)


@router.post('/runtime', response_model=RuntimeConfigResponse)
def update_runtime_config(
    payload: RuntimeConfigUpdate,
    current: dict = Depends(get_current_user),
) -> RuntimeConfigResponse:
    """保存当前登录用户自己的配置；脱敏占位符或空值视为「不修改」。"""
    updates: dict[str, Any] = {
        'openai_api_key': payload.openai_api_key if payload.openai_api_key and not _is_masked(payload.openai_api_key) else None,
        'openai_base_url': payload.openai_base_url if payload.openai_base_url else None,
        'openai_model': payload.openai_model if payload.openai_model else None,
        'openai_temperature': payload.openai_temperature if payload.openai_temperature else None,
        'amap_web_key': payload.amap_web_key if payload.amap_web_key and not _is_masked(payload.amap_web_key) else None,
        'amap_js_key': payload.amap_js_key if payload.amap_js_key and not _is_masked(payload.amap_js_key) else None,
        'tavily_api_key': payload.tavily_api_key if payload.tavily_api_key and not _is_masked(payload.tavily_api_key) else None,
        'tavily_mcp_command': payload.tavily_mcp_command if payload.tavily_mcp_command else None,
    }
    cfg = save_user_config(current.get('id'), updates)
    return _to_response(cfg)
