from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    phone: str | None = None
    email: str | None = None
    real_name: str | None = None
    preference: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserProfile(BaseModel):
    id: int
    username: str
    phone: str | None = None
    email: str | None = None
    real_name: str | None = None
    preference: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserProfile
