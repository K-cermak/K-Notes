from typing import Annotated, Literal

from pydantic import BaseModel, Field

# A user's quota: the instance default, unlimited, or a size in bytes.
StorageLimit = Literal["default", "unlimited"] | int


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
    storage_limit: StorageLimit
    storage_used_bytes: int
    storage_limit_bytes: int | None = Field(description="The limit that applies; None when unlimited")


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
    storage_limit: Literal["default", "unlimited"] | Annotated[int, Field(ge=0)] | None = None


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
    default_storage_limit_bytes: int | None = Field(description="None when unlimited")


class InstanceSettingsUpdate(BaseModel):
    registration_enabled: bool | None = None
    # Sent as null, it makes the default unlimited; left out, it stays as it is.
    default_storage_limit_bytes: Annotated[int, Field(ge=0)] | None = None


class InstanceStatus(BaseModel):
    version: str
    oidc_enabled: bool
    password_login_enabled: bool
    user_count: int
