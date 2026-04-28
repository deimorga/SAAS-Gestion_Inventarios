from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ZoneType(str, Enum):
    RECEIVING = "RECEIVING"
    STORAGE = "STORAGE"
    PICKING = "PICKING"
    DISPATCH = "DISPATCH"
    QUARANTINE = "QUARANTINE"
    TRANSIT = "TRANSIT"


# ── Warehouse ─────────────────────────────────────────────────────────────────

class WarehouseCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=20, pattern=r"^[A-Za-z0-9\-_]+$")
    name: str = Field(..., min_length=1, max_length=100)
    location_address: str | None = None
    is_virtual: bool = False
    timezone: str | None = None


class WarehouseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    location_address: str | None = None
    is_active: bool | None = None
    timezone: str | None = None


class WarehouseListItem(BaseModel):
    id: UUID
    code: str
    name: str
    is_virtual: bool
    is_active: bool

    model_config = {"from_attributes": True}


class WarehouseResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    location_address: str | None
    is_virtual: bool
    is_active: bool
    timezone: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Zone ──────────────────────────────────────────────────────────────────────

class ZoneCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    zone_type: ZoneType
    capacity_volume: Decimal | None = Field(None, gt=0)
    capacity_weight: Decimal | None = Field(None, gt=0)
    parent_zone_id: UUID | None = None


class ZoneUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    zone_type: ZoneType | None = None
    is_active: bool | None = None
    capacity_volume: Decimal | None = Field(None, gt=0)
    capacity_weight: Decimal | None = Field(None, gt=0)


class ZoneResponse(BaseModel):
    id: UUID
    warehouse_id: UUID
    tenant_id: UUID
    code: str
    name: str
    zone_type: ZoneType
    path: str
    is_active: bool
    capacity_volume: Decimal | None
    capacity_weight: Decimal | None
    parent_zone_id: UUID | None

    model_config = {"from_attributes": True}
