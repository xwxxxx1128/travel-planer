from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.runtime_config import get_runtime_config, save_runtime_config

router = APIRouter()


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
    return RuntimeConfigResponse(**runtime_config.__dict__)


@router.post('/runtime', response_model=RuntimeConfigResponse)
def update_runtime_config(payload: RuntimeConfigUpdate):
    runtime_config = save_runtime_config(payload.model_dump())
    return RuntimeConfigResponse(**runtime_config.__dict__)
