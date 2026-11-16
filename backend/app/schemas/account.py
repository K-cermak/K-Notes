from typing import Literal

from pydantic import BaseModel, Field

Theme = Literal["system", "light", "dark"]
View = Literal["grid", "list"]


class SetupRequest(BaseModel):
    email: str = Field(max_length=320)
    display_name: str = Field(max_length=100)
    password: str = Field(max_length=1024)


class RegisterRequest(SetupRequest):
    pass


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class Me(BaseModel):
    id: str
    email: str
    display_name: str
    is_admin: bool
    locale: str
    theme: Theme
    default_view: View
    totp_enabled: bool
    has_password: bool
    oidc_linked: bool


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    locale: str | None = Field(default=None, pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    theme: Theme | None = None
    default_view: View | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


class SessionInfo(BaseModel):
    id: str
    auth_method: str
    created_at: int
    last_used_at: int
    expires_at: int
    user_agent: str | None
    ip: str | None
    current: bool


class TokenRequest(BaseModel):
    token: str = Field(max_length=200)


class LinkInfo(BaseModel):
    email: str | None


class InviteAccept(TokenRequest):
    email: str | None = Field(default=None, max_length=320)
    display_name: str = Field(max_length=100)
    password: str = Field(max_length=1024)


class PasswordReset(TokenRequest):
    password: str = Field(max_length=1024)
