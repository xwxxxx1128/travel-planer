from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv

from app.core.config import BASE_DIR, get_settings

ENV_PATH = BASE_DIR / '.env'


@dataclass
class RuntimeConfig:
    openai_api_key: str = ''
    openai_base_url: str = ''
    amap_web_key: str = ''
    amap_js_key: str = ''

    def to_env_dict(self) -> dict[str, str]:
        return {
            'OPENAI_API_KEY': self.openai_api_key,
            'OPENAI_BASE_URL': self.openai_base_url,
            'AMAP_WEB_API_KEY': self.amap_web_key,
            'AMAP_JS_API_KEY': self.amap_js_key,
            'VITE_AMAP_JS_API_KEY': self.amap_js_key,
        }


def _refresh_environment() -> None:
    load_dotenv(ENV_PATH, override=True)


def _current_config() -> RuntimeConfig:
    _refresh_environment()
    return RuntimeConfig(
        openai_api_key=os.getenv('OPENAI_API_KEY', ''),
        openai_base_url=os.getenv('OPENAI_BASE_URL', ''),
        amap_web_key=os.getenv('AMAP_WEB_API_KEY', ''),
        amap_js_key=os.getenv('AMAP_JS_API_KEY', '') or os.getenv('VITE_AMAP_JS_API_KEY', ''),
    )


def get_runtime_config() -> RuntimeConfig:
    return _current_config()


def save_runtime_config(updates: Mapping[str, str | None]) -> RuntimeConfig:
    current = _current_config()
    env_values = current.to_env_dict()

    alias_map = {
        'openai_api_key': 'OPENAI_API_KEY',
        'openai_base_url': 'OPENAI_BASE_URL',
        'amap_web_key': 'AMAP_WEB_API_KEY',
        'amap_js_key': 'AMAP_JS_API_KEY',
    }

    for field_name, raw_value in updates.items():
        key = alias_map.get(field_name)
        if not key or raw_value is None:
            continue
        value = str(raw_value).strip()
        env_values[key] = value
        if field_name == 'amap_js_key':
            env_values['VITE_AMAP_JS_API_KEY'] = value

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
