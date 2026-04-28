from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyScope(str, Enum):
    READ_INVENTORY = "READ_INVENTORY"
    WRITE_INVENTORY = "WRITE_INVENTORY"
    READ_CATALOG = "READ_CATALOG"
    WRITE_CATALOG = "WRITE_CATALOG"
    MANAGE_WAREHOUSES = "MANAGE_WAREHOUSES"
    MANAGE_RESERVATIONS = "MANAGE_RESERVATIONS"
    ADMIN = "ADMIN"


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    scopes: list[ApiKeyScope]
    ip_whitelist: list[str] | None = None
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: UUID
    key_id: str
    name: str
    scopes: list[ApiKeyScope]
    ip_whitelist: list[str] | None
    is_active: bool
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(ApiKeyResponse):
    key_secret: str
