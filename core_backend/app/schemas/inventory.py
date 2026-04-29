from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class MovementType(str, Enum):
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
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal | None = Field(None, ge=0)
    lot_number: str | None = None
    serial_number: str | None = None
    expiry_date: date | None = None


# ── Receipts (RF-016: PURCHASE_ORDER, INITIAL_STOCK; RF-020: RETURN_IN) ──────

class ReceiptRequest(BaseModel):
    reference_type: str = Field(..., max_length=50)
    reference_id: str = Field(..., max_length=100)
    reason_code: str = Field(..., max_length=50)
    warehouse_id: UUID
    zone_id: UUID
    items: list[TransactionItemInput] = Field(..., min_length=1)


# ── Issues (RF-017: SALES_ORDER; RF-022: SCRAP_LOSS) ─────────────────────────

class IssueRequest(BaseModel):
    reference_type: str = Field(..., max_length=50)
    reference_id: str = Field(..., max_length=100)
    reason_code: str = Field(..., max_length=50)
    warehouse_id: UUID
    zone_id: UUID
    items: list[TransactionItemInput] = Field(..., min_length=1)


# ── Transfers (RF-018) ────────────────────────────────────────────────────────

class TransferRequest(BaseModel):
    reference_type: str = Field("INTERNAL_TRANSFER", max_length=50)
    reference_id: str = Field(..., max_length=100)
    reason_code: str = Field("TRASLADO_INTERNO", max_length=50)
    source_warehouse_id: UUID
    source_zone_id: UUID
    target_warehouse_id: UUID
    target_zone_id: UUID
    items: list[TransactionItemInput] = Field(..., min_length=1)


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
