from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    in_app_enabled: bool
    email_enabled: bool
    browser_enabled: bool
    mobile_enabled: bool
    digest_frequency: Literal["instant", "hourly", "daily", "off"]
    assignments_enabled: bool
    mentions_enabled: bool
    comments_enabled: bool
    deadlines_enabled: bool
    dependencies_enabled: bool
    created_at: datetime
    updated_at: datetime


class NotificationPreferencePatch(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    browser_enabled: bool | None = None
    mobile_enabled: bool | None = None
    digest_frequency: Literal["instant", "hourly", "daily", "off"] | None = None
    assignments_enabled: bool | None = None
    mentions_enabled: bool | None = None
    comments_enabled: bool | None = None
    deadlines_enabled: bool | None = None
    dependencies_enabled: bool | None = None


class PushSubscriptionCreate(BaseModel):
    channel: Literal["web_push", "fcm", "apns"]
    target: str = Field(min_length=10, max_length=4096)
    config: dict = Field(default_factory=dict)
    device_name: str | None = Field(default=None, max_length=160)
    platform: str | None = Field(default=None, max_length=40)


class PushSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel: str
    device_name: str | None
    platform: str | None
    last_used_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class ProviderConfigOut(BaseModel):
    web_push_enabled: bool
    web_push_public_key: str | None
    fcm_enabled: bool
    apns_enabled: bool
