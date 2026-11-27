from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.admin import CAPTCHA_TOKEN_MAX

Theme = Literal["system", "light", "dark"]
View = Literal["grid", "list"]
TimeFormat = Literal["24h", "12h"]


class SetupRequest(BaseModel):
    email: str = Field(max_length=320)
    display_name: str = Field(max_length=100)
    password: str = Field(max_length=1024)


CaptchaToken = Field(default=None, max_length=CAPTCHA_TOKEN_MAX)


class RegisterRequest(SetupRequest):
    captcha_token: str | None = CaptchaToken


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)
    captcha_token: str | None = CaptchaToken


class Me(BaseModel):
    id: str
    email: str
    display_name: str
    is_admin: bool
    locale: str
    theme: Theme
    default_view: View
    time_format: TimeFormat
    totp_enabled: bool
    has_password: bool
    oidc_linked: bool


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    locale: str | None = Field(default=None, pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    theme: Theme | None = None
    default_view: View | None = None
    time_format: TimeFormat | None = None


class AccountDelete(BaseModel):
    """The password, or for an account without one, its e-mail address."""

    password: str | None = Field(default=None, max_length=1024)
    email: str | None = Field(default=None, max_length=320)


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
    captcha_token: str | None = CaptchaToken


class PasswordReset(TokenRequest):
    password: str = Field(max_length=1024)


class TotpChallenge(BaseModel):
    """The password was right; a TOTP or recovery code is still needed to sign in."""

    totp_required: Literal[True] = True
    pending_token: str


class TotpLogin(BaseModel):
    pending_token: str = Field(max_length=200)
    code: str = Field(max_length=32)


class TotpSetup(BaseModel):
    secret: str
    uri: str


class TotpCode(BaseModel):
    code: str = Field(max_length=32)


class TotpDisable(TotpCode):
    password: str = Field(max_length=1024)


class TotpStatus(BaseModel):
    enabled: bool
    recovery_codes_left: int


class RecoveryCodes(BaseModel):
    codes: list[str]


TokenScope = Literal["read", "write"]


class ApiTokenCreate(BaseModel):
    name: str = Field(max_length=100)
    scope: TokenScope
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiTokenInfo(BaseModel):
    id: str
    name: str
    prefix: str
    scope: TokenScope
    created_at: int
    last_used_at: int | None
    expires_at: int | None


class CreatedApiToken(ApiTokenInfo):
    """Includes the token itself, which is never shown again."""

    token: str


class StorageStatus(BaseModel):
    used_bytes: int
    limit_bytes: int | None = Field(description="None when unlimited")
    full: bool = Field(description="At or over the limit: no new notes or images")
