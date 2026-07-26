from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env', env_file_encoding='utf-8', extra='ignore')

    APP_NAME: str = '聚焦智能多景点旅行规划Agent系统'
    SECRET_KEY: str = Field(default='change-me')
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DATABASE_URL: str = Field(default=f'sqlite:///{BASE_DIR / "system.db"}')
    CHROMA_PERSIST_DIR: str = Field(default=str(BASE_DIR / 'chroma_db'))

    OPENAI_API_KEY: str = ''
    OPENAI_BASE_URL: str = ''
    OPENAI_MODEL: str = 'gpt-4o-mini'
    AMAP_WEB_KEY: str = ''
    AMAP_JS_KEY: str = ''

    HOST: str = '0.0.0.0'
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ['*']

    # 航班本地数据库（含 flights / airports_data 等表）
    TRAVEL_DB_PATH: str = Field(default=str(BASE_DIR / 'travel_new.sqlite'))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
