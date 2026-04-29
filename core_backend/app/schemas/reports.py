from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class KardexMovement(BaseModel):
    id: str = Field(..., description="UUID del registro en inventory_ledger")
    date: datetime = Field(..., description="Fecha y hora del movimiento (UTC)")
    movement_type: str = Field(..., description="Tipo: RECEIPT, ISSUE, TRANSFER_OUT, TRANSFER_IN, ADJUSTMENT, SCRAP, RETURN_IN")
    reason_code: str = Field(..., description="Código de razón del movimiento")
    reference_type: str = Field(..., description="Tipo de referencia (ej. PO, SO, TRANSFER)")
    reference_id: str = Field(..., description="ID del documento de referencia")
    qty_in: Decimal = Field(..., description="Cantidad entrante (0 si es salida)")
    qty_out: Decimal = Field(..., description="Cantidad saliente (0 si es entrada)")
    unit_cost: Decimal | None = Field(None, description="Costo unitario en el momento del movimiento")
    balance_after: Decimal = Field(..., description="Saldo acumulado tras este movimiento")
    warehouse_id: str = Field(..., description="UUID del almacén")
    zone_id: str = Field(..., description="UUID de la zona")

    model_config = ConfigDict(from_attributes=True)


class KardexProductSummary(BaseModel):
    id: str
    sku: str
    name: str
    current_cpp: Decimal


class KardexResponse(BaseModel):
    product: KardexProductSummary
    initial_balance: Decimal = Field(..., description="Saldo antes del primer movimiento en el rango")
    final_balance: Decimal = Field(..., description="Saldo tras el último movimiento en el rango")
    movements: list[KardexMovement]
    page: int
    page_size: int
    total: int


class ValuationDetail(BaseModel):
    product_id: str
    sku: str
    name: str
    total_qty: Decimal = Field(..., description="Cantidad física total en todos los almacenes")
    current_cpp: Decimal = Field(..., description="Costo promedio ponderado actual")
    total_value: Decimal = Field(..., description="Valoración total: total_qty × current_cpp")

    model_config = ConfigDict(from_attributes=True)


class ValuationResponse(BaseModel):
    total_valuation: Decimal = Field(..., description="Suma de valoración de todos los productos")
    currency: str = Field(default="COP", description="Moneda de valoración")
    details: list[ValuationDetail]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_valuation": 150000000.00,
                "currency": "COP",
                "details": [
                    {
                        "product_id": "550e8400-e29b-41d4-a716-446655440000",
                        "sku": "MON-24",
                        "name": "Monitor 24\"",
                        "total_qty": 50.0,
                        "current_cpp": 420000.00,
                        "total_value": 21000000.00,
                    }
                ],
            }
        }
    )


class SnapshotCreate(BaseModel):
    period: str = Field(..., description="Período contable en formato YYYY-MM", examples=["2026-04"])
    description: str | None = Field(None, description="Descripción del cierre", examples=["Cierre Contable Abril 2026"])

    model_config = ConfigDict(
        json_schema_extra={"example": {"period": "2026-04", "description": "Cierre Contable Abril 2026"}}
    )


class SnapshotResponse(BaseModel):
    id: str
    period: str
    product_id: str
    snapshot_qty: Decimal
    snapshot_cpp: Decimal
    total_value: Decimal
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LowStockItem(BaseModel):
    product_id: str
    sku: str
    name: str
    available_qty: Decimal = Field(..., description="Cantidad disponible actual")
    reorder_point: Decimal = Field(..., description="Punto de reorden configurado en el producto")
    deficit: Decimal = Field(..., description="Diferencia: reorder_point - available_qty")

    model_config = ConfigDict(from_attributes=True)


class LowStockResponse(BaseModel):
    data: list[LowStockItem]
    total: int
    page: int
    page_size: int


# ── Expiry Report (RF-023) ────────────────────────────────────────────────────

class ExpiringBatch(BaseModel):
    batch_id: str
    batch_number: str
    product_id: str
    product_sku: str
    product_name: str
    expiry_date: str
    days_remaining: int
    initial_qty: Decimal

    model_config = ConfigDict(from_attributes=True)


class ExpiringBatchesResponse(BaseModel):
    data: list[ExpiringBatch]
    total: int
    days_ahead: int
