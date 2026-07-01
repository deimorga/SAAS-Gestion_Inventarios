from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Category ──────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre de la categoría. Debe ser único entre los hijos del mismo padre.",
        examples=["Repuestos Mecánicos"],
    )
    parent_id: UUID | None = Field(
        None,
        description="UUID de la categoría padre para crear jerarquías. Nulo = categoría raíz.",
        examples=["550e8400-e29b-41d4-a716-446655440001"],
    )
    sort_order: int = Field(
        0,
        description="Orden de presentación dentro del mismo nivel (menor número aparece primero).",
        examples=[10],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Filtros",
                "parent_id": "550e8400-e29b-41d4-a716-446655440001",
                "sort_order": 10,
            }
        }
    }


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
    sku: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9\-_]+$",
        description="Código único del producto (SKU). Solo letras, dígitos, guiones y guiones bajos. Inmutable tras la creación.",
        examples=["FILTRO-ACEITE-001"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre descriptivo del producto.",
        examples=["Filtro de aceite motor 2.0L"],
    )
    description: str | None = Field(
        None,
        max_length=2000,
        description="Descripción detallada del producto. Opcional.",
        examples=["Compatible con motores Chevrolet 2.0L y 2.4L — modelos 2015–2024."],
    )
    category_id: UUID | None = Field(
        None,
        description="UUID de la categoría a la que pertenece el producto. Opcional.",
        examples=["550e8400-e29b-41d4-a716-446655440010"],
    )
    base_uom: str = Field(
        ...,
        max_length=20,
        description="Unidad de medida base del producto. Valores comunes: UND, KG, LT, PAR, MTS, CAJA.",
        examples=["UND"],
    )
    sale_price: Decimal | None = Field(
        None,
        ge=0,
        description="Precio de venta del producto. Opcional, solo referencial.",
        examples=[Decimal("45000.00")],
    )
    reorder_point: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Stock mínimo antes de disparar alerta de reabastecimiento. 0 = sin alerta.",
        examples=[5],
    )
    track_lots: bool = Field(
        False,
        description="Si true, cada movimiento debe especificar número de lote (lot_number). Requerido para trazabilidad por lote.",
        examples=[False],
    )
    track_serials: bool = Field(
        False,
        description="Si true, cada unidad debe registrar un serial único. Implica track_lots=true.",
        examples=[False],
    )
    track_expiry: bool = Field(
        False,
        description="Si true, se requiere fecha de vencimiento (expiry_date) en cada movimiento. Recomendado para productos perecederos.",
        examples=[False],
    )
    low_stock_alert_enabled: bool = Field(
        True,
        description="Habilitar alertas automáticas cuando el stock cae por debajo de reorder_point.",
        examples=[True],
    )
    metadata: dict | None = Field(
        None,
        description="Metadatos adicionales en formato JSON libre (marca, referencia OEM, proveedor, etc.).",
        examples=[{"marca": "Bosch", "referencia_oem": "1457429618"}],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "sku": "FILTRO-ACEITE-001",
                "name": "Filtro de aceite motor 2.0L",
                "description": "Compatible con motores Chevrolet 2.0L y 2.4L — modelos 2015–2024.",
                "category_id": "550e8400-e29b-41d4-a716-446655440010",
                "base_uom": "UND",
                "sale_price": 45000.00,
                "reorder_point": 5,
                "track_lots": False,
                "track_serials": False,
                "track_expiry": False,
                "low_stock_alert_enabled": True,
                "metadata": {"marca": "Bosch", "referencia_oem": "1457429618"},
            }
        }
    }


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    category_id: UUID | None = None
    sale_price: Decimal | None = Field(None, ge=0)
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
    sale_price: Decimal | None
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
    sale_price: Decimal | None
    current_cpp: Decimal
    reorder_point: Decimal
    is_active: bool
    is_kit: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── UOM ───────────────────────────────────────────────────────────────────

class ProductUomCreate(BaseModel):
    uom_code: str = Field(
        ...,
        max_length=20,
        description="Código de la unidad de medida alternativa (ej: CAJA, DOCENA, PAR). Debe existir en el catálogo de UOMs del tenant.",
        examples=["CAJA"],
    )
    conversion_factor: Decimal = Field(
        ...,
        gt=0,
        description="Factor de conversión respecto a la unidad base del producto. Ej: si base=UND y uom_code=CAJA con factor=12, 1 CAJA = 12 UND.",
        examples=[12],
    )
    is_purchase_uom: bool = Field(
        False,
        description="Marcar como unidad preferida para órdenes de compra (solo referencial).",
        examples=[True],
    )
    is_sale_uom: bool = Field(
        False,
        description="Marcar como unidad preferida para ventas (solo referencial).",
        examples=[False],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "uom_code": "CAJA",
                "conversion_factor": 12,
                "is_purchase_uom": True,
                "is_sale_uom": False,
            }
        }
    }


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
