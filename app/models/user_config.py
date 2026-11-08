from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserConfig(Base):
    """每个用户独立的服务配置（BYOK）。

    用户通过前端「个人信息 / 服务配置」页填写自己的大模型 / 高德 / Tavily 等 Key，
    未填写的字段在解析时回退到项目根 `.env` 的全局默认值（见 app.services.user_config）。

    一个用户最多一条记录：user_id 唯一。
    """

    __tablename__ = 'user_configs'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    openai_api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    openai_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    openai_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    openai_temperature: Mapped[str | None] = mapped_column(String(32), nullable=True)

    amap_web_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amap_js_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    tavily_api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tavily_mcp_command: Mapped[str | None] = mapped_column(String(256), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
