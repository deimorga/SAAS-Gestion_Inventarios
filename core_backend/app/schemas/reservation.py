from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReservationItemInput(BaseModel):
    product_id: str = Field(..., description="UUID del producto a reservar", examples=["550e8400-e29b-41d4-a716-446655440000"])
    warehouse_id: str = Field(..., description="UUID del almacén origen")
    zone_id: str = Field(..., description="UUID de la zona origen")
    quantity: Decimal = Field(..., gt=0, description="Cantidad a reservar (mayor que 0)", examples=[2.0])


class ReservationCreate(BaseModel):
    reference_type: str = Field(..., max_length=50, description="Tipo de origen (ej. ECOMMERCE_CART, SALES_QUOTE)", examples=["ECOMMERCE_CART"])
    reference_id: str = Field(..., max_length=100, description="ID del documento de referencia", examples=["CART-12345"])
    expires_at: datetime | None = Field(None, description="Expiración explícita. Si se omite, usa RESERVATION_TTL_MINUTES del tenant")
    items: list[ReservationItemInput] = Field(..., min_length=1, description="Items a reservar")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reference_type": "ECOMMERCE_CART",
                "reference_id": "CART-12345",
                "expires_at": "2026-04-30T10:30:00Z",
                "items": [
                    {"product_id": "550e8400-e29b-41d4-a716-446655440000", "warehouse_id": "wh-uuid", "zone_id": "zone-uuid", "quantity": 2.0}
                ],
            }
        }
    )


class ReservationItemResponse(BaseModel):
    id: str
    product_id: str
    warehouse_id: str
    zone_id: str
    quantity: Decimal
    confirmed_qty: Decimal

    model_config = ConfigDict(from_attributes=True)


class ReservationResponse(BaseModel):
    id: str
    reference_type: str
    reference_id: str
    status: str = Field(..., description="ACTIVE | COMPLETED | CANCELLED | EXPIRED")
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    items: list[ReservationItemResponse]

    model_config = ConfigDict(from_attributes=True)


class ReservationConfirm(BaseModel):
    actual_quantity_to_issue: Decimal = Field(..., gt=0, description="Cantidad real a despachar (puede ser ≤ cantidad reservada)")
    issue_reference: str = Field(..., description="ID del documento de salida (ej. factura, orden de despacho)", examples=["INVOICE-999"])

    model_config = ConfigDict(
        json_schema_extra={"example": {"actual_quantity_to_issue": 2.0, "issue_reference": "INVOICE-999"}}
    )
