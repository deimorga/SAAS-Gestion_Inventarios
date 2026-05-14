from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class MovementType(str, Enum):
    """Tipo de movimiento registrado en el ledger de inventario.

    - `RECEIPT`: Entrada de mercancía al inventario (compra, recepción inicial).
    - `ISSUE`: Salida de mercancía del inventario (venta, consumo interno).
    - `TRANSFER_OUT`: Salida del almacén origen en una transferencia entre almacenes.
    - `TRANSFER_IN`: Entrada al almacén destino en una transferencia entre almacenes.
    - `ADJUSTMENT`: Ajuste contable por diferencia de conteo físico (puede ser positivo o negativo).
    - `SCRAP`: Baja definitiva por daño, pérdida o vencimiento. No genera reversa.
    - `RETURN_IN`: Devolución de cliente que regresa al inventario disponible.
    """

    RECEIPT = "RECEIPT"
    ISSUE = "ISSUE"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    ADJUSTMENT = "ADJUSTMENT"
    SCRAP = "SCRAP"
    RETURN_IN = "RETURN_IN"


class TransactionType(str, Enum):
    RECEIPT = "RECEIPT"
    ISSUE = "ISSUE"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"
    SCRAP = "SCRAP"
    RETURN_IN = "RETURN_IN"


# ── Shared item input ─────────────────────────────────────────────────────────

class TransactionItemInput(BaseModel):
    product_id: UUID = Field(
        ...,
        description="UUID del producto a mover. Debe existir en el catálogo del tenant.",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Cantidad del producto en la unidad base del producto (base_uom). Debe ser mayor que cero.",
        examples=[10],
    )
    unit_cost: Decimal | None = Field(
        None,
        ge=0,
        description=(
            "Costo unitario en la moneda del tenant. "
            "Requerido en entradas (RECEIPT) para calcular el costo promedio ponderado (CPP). "
            "Opcional en salidas — el sistema usa el CPP vigente."
        ),
        examples=[15500.00],
    )
    lot_number: str | None = Field(
        None,
        description="Número de lote. Requerido si el producto tiene track_lots=true.",
        examples=["LOTE-2026-001"],
    )
    serial_number: str | None = Field(
        None,
        description="Serial único de la unidad. Requerido si el producto tiene track_serials=true. Implica quantity=1.",
        examples=["SN-ABC-123456"],
    )
    expiry_date: date | None = Field(
        None,
        description="Fecha de vencimiento en formato YYYY-MM-DD. Requerida si el producto tiene track_expiry=true.",
        examples=["2027-06-30"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "quantity": 10,
                "unit_cost": 15500.00,
                "lot_number": None,
                "serial_number": None,
                "expiry_date": None,
            }
        }
    }


# ── Receipts (RF-016: PURCHASE_ORDER, INITIAL_STOCK; RF-020: RETURN_IN) ──────

class ReceiptRequest(BaseModel):
    reference_type: str = Field(
        ...,
        max_length=50,
        description=(
            "Tipo del documento origen. Valores comunes: "
            "PURCHASE_ORDER (orden de compra), INITIAL_STOCK (carga inicial), RETURN_IN (devolución de cliente)."
        ),
        examples=["PURCHASE_ORDER"],
    )
    reference_id: str = Field(
        ...,
        max_length=100,
        description="Número o identificador del documento origen en el sistema externo (ej: número de OC, número de factura).",
        examples=["OC-2026-00145"],
    )
    reason_code: str = Field(
        ...,
        max_length=50,
        description="Código de razón del movimiento. Valores comunes: COMPRA, CARGA_INICIAL, DEVOLUCION_CLIENTE.",
        examples=["COMPRA"],
    )
    warehouse_id: UUID = Field(
        ...,
        description="UUID del almacén destino donde ingresa la mercancía.",
        examples=["b1c2d3e4-f5a6-7890-bcde-f01234567891"],
    )
    zone_id: UUID = Field(
        ...,
        description="UUID de la zona dentro del almacén destino. Debe pertenecer al warehouse_id indicado.",
        examples=["c2d3e4f5-a6b7-8901-cdef-012345678902"],
    )
    items: list[TransactionItemInput] = Field(
        ...,
        min_length=1,
        description="Lista de productos a recibir. Mínimo 1 item. Todos los items se procesan en una sola transacción atómica.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "reference_type": "PURCHASE_ORDER",
                "reference_id": "OC-2026-00145",
                "reason_code": "COMPRA",
                "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
                "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
                "items": [
                    {
                        "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "quantity": 10,
                        "unit_cost": 15500.00,
                        "lot_number": None,
                        "serial_number": None,
                        "expiry_date": None,
                    }
                ],
            }
        }
    }


# ── Issues (RF-017: SALES_ORDER; RF-022: SCRAP_LOSS) ─────────────────────────

class IssueRequest(BaseModel):
    reference_type: str = Field(
        ...,
        max_length=50,
        description=(
            "Tipo del documento origen. Valores comunes: "
            "SALES_ORDER (orden de venta), WORK_ORDER (orden de trabajo taller), SCRAP_LOSS (baja por pérdida)."
        ),
        examples=["SALES_ORDER"],
    )
    reference_id: str = Field(
        ...,
        max_length=100,
        description="Número o identificador del documento origen en el sistema externo (ej: número de venta, número de OT).",
        examples=["OT-2026-00892"],
    )
    reason_code: str = Field(
        ...,
        max_length=50,
        description="Código de razón del movimiento. Valores comunes: VENTA, CONSUMO_TALLER, BAJA_DAÑO.",
        examples=["CONSUMO_TALLER"],
    )
    warehouse_id: UUID = Field(
        ...,
        description="UUID del almacén origen del que sale la mercancía.",
        examples=["b1c2d3e4-f5a6-7890-bcde-f01234567891"],
    )
    zone_id: UUID = Field(
        ...,
        description="UUID de la zona dentro del almacén origen. Debe pertenecer al warehouse_id indicado.",
        examples=["c2d3e4f5-a6b7-8901-cdef-012345678902"],
    )
    items: list[TransactionItemInput] = Field(
        ...,
        min_length=1,
        description="Lista de productos a despachar. El sistema valida que haya stock disponible (physical_qty - reserved_qty) antes de procesar.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "reference_type": "SALES_ORDER",
                "reference_id": "OT-2026-00892",
                "reason_code": "CONSUMO_TALLER",
                "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
                "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
                "items": [
                    {
                        "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "quantity": 2,
                        "unit_cost": None,
                        "lot_number": None,
                        "serial_number": None,
                        "expiry_date": None,
                    }
                ],
            }
        }
    }


# ── Transfers (RF-018) ────────────────────────────────────────────────────────

class TransferRequest(BaseModel):
    reference_type: str = Field(
        "INTERNAL_TRANSFER",
        max_length=50,
        description="Tipo del documento origen. Por defecto INTERNAL_TRANSFER.",
        examples=["INTERNAL_TRANSFER"],
    )
    reference_id: str = Field(
        ...,
        max_length=100,
        description="Identificador único de la transferencia en el sistema externo o interno.",
        examples=["TRF-2026-00034"],
    )
    reason_code: str = Field(
        "TRASLADO_INTERNO",
        max_length=50,
        description="Código de razón. Por defecto TRASLADO_INTERNO.",
        examples=["TRASLADO_INTERNO"],
    )
    source_warehouse_id: UUID = Field(
        ...,
        description="UUID del almacén origen del que sale la mercancía.",
        examples=["b1c2d3e4-f5a6-7890-bcde-f01234567891"],
    )
    source_zone_id: UUID = Field(
        ...,
        description="UUID de la zona dentro del almacén origen.",
        examples=["c2d3e4f5-a6b7-8901-cdef-012345678902"],
    )
    target_warehouse_id: UUID = Field(
        ...,
        description="UUID del almacén destino. Puede ser igual al origen (transferencia entre zonas).",
        examples=["d3e4f5a6-b7c8-9012-defa-123456789013"],
    )
    target_zone_id: UUID = Field(
        ...,
        description="UUID de la zona dentro del almacén destino.",
        examples=["e4f5a6b7-c8d9-0123-efab-234567890124"],
    )
    items: list[TransactionItemInput] = Field(
        ...,
        min_length=1,
        description="Productos a transferir. El campo unit_cost es ignorado — se conserva el CPP del origen.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "reference_type": "INTERNAL_TRANSFER",
                "reference_id": "TRF-2026-00034",
                "reason_code": "TRASLADO_INTERNO",
                "source_warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
                "source_zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
                "target_warehouse_id": "d3e4f5a6-b7c8-9012-defa-123456789013",
                "target_zone_id": "e4f5a6b7-c8d9-0123-efab-234567890124",
                "items": [
                    {
                        "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "quantity": 5,
                        "unit_cost": None,
                        "lot_number": None,
                        "serial_number": None,
                        "expiry_date": None,
                    }
                ],
            }
        }
    }


# ── Adjustments (RF-019) ──────────────────────────────────────────────────────

class AdjustmentItem(BaseModel):
    product_id: UUID
    new_qty: Decimal = Field(..., ge=0)
    lot_number: str | None = None
    reason: str | None = None


class AdjustmentRequest(BaseModel):
    reference_id: str = Field(..., max_length=100)
    reason_code: str = Field("CONTEO_FISICO", max_length=50)
    warehouse_id: UUID
    zone_id: UUID
    items: list[AdjustmentItem] = Field(..., min_length=1)


# ── Responses ─────────────────────────────────────────────────────────────────

class TransactionResponse(BaseModel):
    transaction_id: UUID
    transaction_type: TransactionType
    timestamp: datetime
    status: str
    items_processed: int

    model_config = {"from_attributes": True}


class StockBalanceResponse(BaseModel):
    id: UUID
    product_id: UUID
    warehouse_id: UUID
    zone_id: UUID
    lot_number: str | None
    physical_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal

    model_config = {"from_attributes": True}


class LedgerEntryResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    product_id: UUID
    warehouse_id: UUID
    zone_id: UUID
    movement_type: MovementType
    qty_change: Decimal
    unit_cost: Decimal | None
    lot_number: str | None
    reference_type: str
    reference_id: str
    reason_code: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Repack (RF-021) ───────────────────────────────────────────────────────────

class RepackItem(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)
    lot_number: str | None = None


class RepackRequest(BaseModel):
    reference_id: str = Field(..., max_length=100)
    warehouse_id: UUID
    zone_id: UUID
    source_items: list[RepackItem] = Field(..., min_length=1, description="Productos que se consumen en el re-empaque")
    target_items: list[RepackItem] = Field(..., min_length=1, description="Productos que se generan tras el re-empaque")
