from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv

from app.core.config import BASE_DIR, get_settings

ENV_PATH = BASE_DIR / '.env'


@dataclass
class RuntimeConfig:
    """运行时可由前端「个人信息 / 服务配置」页面维护的配置项。

    设计原则：
    - 与 `.env` 双向同步：前端保存时写入 `.env` 并立即更新 `os.environ`，
      保证当前进程及新启动的进程都能读取最新值。
    - 键名兼容：高德 Key 同时支持 `AMAP_WEB_KEY` / `AMAP_JS_KEY`（`.env.example`
      使用的命名）与 `AMAP_WEB_API_KEY` / `AMAP_JS_API_KEY`（旧代码命名）。
    - 敏感字段（API Key）以空字符串兜底，避免未配置时直接抛异常。
    """

    openai_api_key: str = ''
    openai_base_url: str = ''
    openai_model: str = ''
    openai_temperature: str = ''
    amap_web_key: str = ''
    amap_js_key: str = ''
    tavily_api_key: str = ''
    tavily_mcp_command: str = ''

    def to_env_dict(self) -> dict[str, str]:
        """导出为需要写入 `.env` / `os.environ` 的键值对。"""
        return {
            'OPENAI_API_KEY': self.openai_api_key,
            'OPENAI_BASE_URL': self.openai_base_url,
            'OPENAI_MODEL': self.openai_model,
            'OPENAI_TEMPERATURE': self.openai_temperature,
            # 同时写入两套 Key 名，保证 pydantic-settings 与旧代码都能读到。
            'AMAP_WEB_KEY': self.amap_web_key,
            'AMAP_WEB_API_KEY': self.amap_web_key,
            'AMAP_JS_KEY': self.amap_js_key,
            'AMAP_JS_API_KEY': self.amap_js_key,
            'VITE_AMAP_JS_API_KEY': self.amap_js_key,
            'TAVILY_API_KEY': self.tavily_api_key,
            'TAVILY_MCP_COMMAND': self.tavily_mcp_command,
        }


def _refresh_environment() -> None:
    load_dotenv(ENV_PATH, override=True)


def _get_env(*names: str, default: str = '') -> str:
    """按优先级读取多个环境变量名，返回第一个非空值。"""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _current_config() -> RuntimeConfig:
    _refresh_environment()
    return RuntimeConfig(
        openai_api_key=_get_env('OPENAI_API_KEY'),
        openai_base_url=_get_env('OPENAI_BASE_URL'),
        openai_model=_get_env('OPENAI_MODEL'),
        openai_temperature=_get_env('OPENAI_TEMPERATURE'),
        amap_web_key=_get_env('AMAP_WEB_KEY', 'AMAP_WEB_API_KEY'),
        amap_js_key=_get_env('AMAP_JS_KEY', 'AMAP_JS_API_KEY', 'VITE_AMAP_JS_API_KEY'),
        tavily_api_key=_get_env('TAVILY_API_KEY'),
        tavily_mcp_command=_get_env('TAVILY_MCP_COMMAND', default='tavily-mcp'),
    )


def get_runtime_config() -> RuntimeConfig:
    return _current_config()


def save_runtime_config(updates: Mapping[str, str | None]) -> RuntimeConfig:
    """保存运行时配置：合并前端提交项 → 写回 `.env` → 刷新 `os.environ`。"""
    current = _current_config()
    env_values = current.to_env_dict()

    alias_map = {
        'openai_api_key': 'OPENAI_API_KEY',
        'openai_base_url': 'OPENAI_BASE_URL',
        'openai_model': 'OPENAI_MODEL',
        'openai_temperature': 'OPENAI_TEMPERATURE',
        'amap_web_key': 'AMAP_WEB_KEY',
        'amap_js_key': 'AMAP_JS_KEY',
        'tavily_api_key': 'TAVILY_API_KEY',
        'tavily_mcp_command': 'TAVILY_MCP_COMMAND',
    }

    for field_name, raw_value in updates.items():
        key = alias_map.get(field_name)
        if not key or raw_value is None:
            continue
        value = str(raw_value).strip()
        env_values[key] = value
        # 高德 JS Key 需要同步给前端 Vite 构建变量
        if field_name == 'amap_js_key':
            env_values['VITE_AMAP_JS_API_KEY'] = value
            env_values['AMAP_JS_API_KEY'] = value
        # 高德 Web Key 同时维护旧命名
        if field_name == 'amap_web_key':
            env_values['AMAP_WEB_API_KEY'] = value

    lines: list[str] = []
    seen_keys: set[str] = set()
    if ENV_PATH.exists():
        for original_line in ENV_PATH.read_text(encoding='utf-8').splitlines():
            stripped = original_line.strip()
            if not stripped or stripped.startswith('#') or '=' not in original_line:
                lines.append(original_line)
                continue
            key, _ = original_line.split('=', 1)
            key = key.strip()
            if key in env_values:
                lines.append(f'{key}={env_values[key]}')
                seen_keys.add(key)
            else:
                lines.append(original_line)
    for key, value in env_values.items():
        if key not in seen_keys:
            lines.append(f'{key}={value}')

    ENV_PATH.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    os.environ.update(env_values)
    try:
        get_settings.cache_clear()
    except Exception:
        pass
    return _current_config()
