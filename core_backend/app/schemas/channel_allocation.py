from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


VALID_CHANNELS = {"WEB", "POS", "B2B", "MOBILE", "MARKETPLACE", "WHOLESALE", "INTERNAL"}


class ChannelAllocationCreate(BaseModel):
    product_id: UUID = Field(..., description="Producto al que aplica la cuota")
    zone_id: UUID = Field(..., description="Zona del almacén de donde se reserva la cuota")
    channel: str = Field(..., min_length=1, max_length=50, description="Canal de venta: WEB, POS, B2B, MOBILE, MARKETPLACE, WHOLESALE, INTERNAL")
    allocated_qty: Decimal = Field(..., gt=0, description="Cantidad reservada exclusivamente para este canal")
    notes: str | None = None


class ChannelAllocationUpdate(BaseModel):
    allocated_qty: Decimal | None = Field(None, gt=0)
    notes: str | None = None
    is_active: bool | None = None


class ChannelAllocationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    product_id: UUID
    zone_id: UUID
    channel: str
    allocated_qty: Decimal
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
