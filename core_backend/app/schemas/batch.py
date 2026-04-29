from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BatchCreate(BaseModel):
    product_id: UUID = Field(..., description="Producto al que pertenece el lote")
    batch_number: str = Field(..., min_length=1, max_length=100, description="Número/código de lote")
    manufactured_date: date | None = Field(None, description="Fecha de fabricación")
    expiry_date: date | None = Field(None, description="Fecha de vencimiento")
    initial_qty: Decimal = Field(..., gt=0, description="Cantidad inicial del lote")
    notes: str | None = None


class BatchResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    product_id: UUID
    batch_number: str
    manufactured_date: date | None
    expiry_date: date | None
    initial_qty: Decimal
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Serial Numbers ─────────────────────────────────────────────────────────────

class SerialNumberCreate(BaseModel):
    serial_number: str = Field(..., min_length=1, max_length=200, description="Número de serie único en el tenant")
    notes: str | None = None


class SerialNumberBulkCreate(BaseModel):
    serials: list[SerialNumberCreate] = Field(..., min_length=1, max_length=500)


class SerialNumberResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    product_id: UUID
    batch_id: UUID | None
    serial_number: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SerialStatusResponse(BaseModel):
    serial_number: str
    product_id: UUID
    batch_id: UUID | None
    status: str
    is_available: bool
