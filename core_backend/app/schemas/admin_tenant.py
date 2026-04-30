from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str | None = Field(
        None,
        pattern=r'^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$',
        max_length=100,
        description="Slug único. Si no se provee, se genera automáticamente desde el nombre.",
    )
    subscription_tier: str = Field(
        "STARTER",
        pattern=r'^(STARTER|PROFESSIONAL|ENTERPRISE)$',
    )
    admin_email: EmailStr
    admin_full_name: str = Field(..., min_length=2, max_length=255)


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    is_active: bool | None = None
    subscription_tier: str | None = Field(
        None,
        pattern=r'^(STARTER|PROFESSIONAL|ENTERPRISE)$',
    )


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    subscription_tier: str
    is_active: bool
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantCreateResponse(TenantResponse):
    admin_user_id: UUID
    admin_email: str


class TenantListResponse(BaseModel):
    items: list[TenantResponse]
    total: int
    page: int
    size: int
