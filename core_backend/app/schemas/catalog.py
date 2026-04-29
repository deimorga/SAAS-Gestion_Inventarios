from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Category ──────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: UUID | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    parent_id: UUID | None = None
    sort_order: int | None = None


class CategorySummary(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class CategoryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    parent_id: UUID | None
    path: str
    slug: str
    sort_order: int
    is_active: bool
    children_count: int = 0
    products_count: int = 0

    model_config = {"from_attributes": True}


class CategoryTreeNode(CategoryResponse):
    children: list["CategoryTreeNode"] = []


# ── Product ───────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9\-_]+$")
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    category_id: UUID | None = None
    base_uom: str = Field(..., max_length=20)
    reorder_point: Decimal = Field(default=Decimal("0"), ge=0)
    track_lots: bool = False
    track_serials: bool = False
    track_expiry: bool = False
    low_stock_alert_enabled: bool = True
    metadata: dict | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    category_id: UUID | None = None
    reorder_point: Decimal | None = Field(None, ge=0)
    track_lots: bool | None = None
    track_serials: bool | None = None
    track_expiry: bool | None = None
    low_stock_alert_enabled: bool | None = None
    metadata: dict | None = None


class ProductResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    sku: str
    name: str
    description: str | None
    category: CategorySummary | None
    base_uom: str
    current_cpp: Decimal
    reorder_point: Decimal
    track_lots: bool
    track_serials: bool
    track_expiry: bool
    is_kit: bool
    is_active: bool
    low_stock_alert_enabled: bool
    metadata: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListItem(BaseModel):
    id: UUID
    sku: str
    name: str
    category: CategorySummary | None
    base_uom: str
    current_cpp: Decimal
    reorder_point: Decimal
    is_active: bool
    is_kit: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── UOM ───────────────────────────────────────────────────────────────────

class ProductUomCreate(BaseModel):
    uom_code: str = Field(..., max_length=20)
    conversion_factor: Decimal = Field(..., gt=0)
    is_purchase_uom: bool = False
    is_sale_uom: bool = False


class ProductUomResponse(BaseModel):
    id: UUID
    product_id: UUID
    uom_code: str
    conversion_factor: Decimal
    is_purchase_uom: bool
    is_sale_uom: bool

    model_config = {"from_attributes": True}


# ── Kit / BOM (RF-009) ────────────────────────────────────────────────────────

class KitComponentCreate(BaseModel):
    component_product_id: UUID = Field(..., description="ID del producto componente")
    quantity: Decimal = Field(..., gt=0, description="Cantidad del componente por unidad de kit")


class KitComponentResponse(BaseModel):
    id: UUID
    kit_product_id: UUID
    component_product_id: UUID
    component_sku: str
    component_name: str
    component_uom: str
    quantity: Decimal
