from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CycleCountCreate(BaseModel):
    warehouse_id: str = Field(..., description="UUID del almacén a contar")
    label: str = Field(..., max_length=100, description="Nombre del conteo (ej. 'Conteo mensual Abril 2026')")
    apply_adjustments: bool = Field(
        False,
        description="Si true, al cerrar la sesión se generan ajustes automáticos por cada varianza ≠ 0",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "warehouse_id": "wh-uuid",
                "label": "Conteo mensual Abril 2026",
                "apply_adjustments": True,
            }
        }
    )


class CycleCountItemUpdate(BaseModel):
    counted_qty: Decimal = Field(..., ge=0, description="Cantidad contada físicamente en el almacén")

    model_config = ConfigDict(json_schema_extra={"example": {"counted_qty": 45.0}})


class CycleCountClose(BaseModel):
    reference_id: str = Field(
        ...,
        max_length=100,
        description="ID de referencia para las transacciones de ajuste generadas al cerrar",
    )

    model_config = ConfigDict(json_schema_extra={"example": {"reference_id": "CIERRE-ABRIL-2026"}})


class CycleCountItemResponse(BaseModel):
    id: str
    product_id: str
    zone_id: str
    expected_qty: Decimal = Field(..., description="Cantidad esperada según el snapshot al abrir la sesión")
    counted_qty: Decimal | None = Field(None, description="Cantidad contada físicamente. None si aún no se registró")
    variance: Decimal | None = Field(
        None,
        description="counted_qty − expected_qty. Positivo = sobrante, negativo = faltante. None si no se contó aún",
    )


class CycleCountSessionResponse(BaseModel):
    id: str
    warehouse_id: str
    label: str
    status: str = Field(..., description="OPEN | CLOSED")
    apply_adjustments: bool
    created_at: datetime
    closed_at: datetime | None
    items: list[CycleCountItemResponse]
