from pydantic import BaseModel, Field


class AdminUser(BaseModel):
    id: str
    email: str
    display_name: str
    is_admin: bool
    is_active: bool
    totp_enabled: bool
    has_password: bool
    oidc_linked: bool
    created_at: int
    last_active_at: int | None


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class InviteCreate(BaseModel):
    email: str | None = Field(default=None, max_length=320)


class CreatedLink(BaseModel):
    """A one-time link. The URL is only available in this response; the server keeps a hash."""

    id: str
    url: str
    expires_at: int


class PendingInvite(BaseModel):
    id: str
    email: str | None
    created_by: str | None
    created_at: int
    expires_at: int


class InstanceSettings(BaseModel):
    registration_enabled: bool


class InstanceSettingsUpdate(BaseModel):
    registration_enabled: bool | None = None


class InstanceStatus(BaseModel):
    version: str
    oidc_enabled: bool
    password_login_enabled: bool
    user_count: int
