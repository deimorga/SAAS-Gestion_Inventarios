from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BinCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9\-_]+$",
                      description="Código del bin, único dentro de la zona")
    name: str | None = Field(None, max_length=255)
    max_weight_kg: Decimal | None = Field(None, gt=0, description="Capacidad máxima en kg")
    max_volume_m3: Decimal | None = Field(None, gt=0, description="Capacidad máxima en m³")


class BinUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    max_weight_kg: Decimal | None = Field(None, gt=0)
    max_volume_m3: Decimal | None = Field(None, gt=0)
    is_active: bool | None = None


class BinResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    zone_id: UUID
    code: str
    name: str | None
    max_weight_kg: Decimal | None
    max_volume_m3: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Location Lock (RF-015) ────────────────────────────────────────────────────

class LocationLockCreate(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500, description="Motivo del bloqueo")


class LocationLockResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    bin_id: UUID
    reason: str
    locked_by: str
    locked_at: datetime
    unlocked_at: datetime | None
    is_active: bool

    model_config = {"from_attributes": True}
