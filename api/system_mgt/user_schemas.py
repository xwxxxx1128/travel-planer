from app.schemas.auth import RegisterRequest as CreateOrUpdateUserSchema
from app.schemas.auth import RegisterRequest as UpdateUserSchema
from app.schemas.auth import LoginRequest as UserLoginSchema
from app.schemas.auth import TokenResponse as UserLoginRspSchema
from app.schemas.auth import UserProfile as UserSchema
from pydantic import BaseModel, Field


class BaseUserSchema(BaseModel):
    username: str | None = Field(default=None)
    phone: str | None = None
    email: str | None = None
    real_name: str | None = None
    icon: str | None = None


class GetUserList(BaseModel):
    username: str
    id: int
