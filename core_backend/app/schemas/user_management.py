from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(
        "api_consumer",
        pattern=r'^(tenant_admin|inventory_manager|viewer|api_consumer)$',
        description="Solo tenant_admin puede crear usuarios. El rol api_consumer es el único creatable.",
    )


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int
