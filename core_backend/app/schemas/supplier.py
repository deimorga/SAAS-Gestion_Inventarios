from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SupplierCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9\-_]+$",
                      description="Código único del proveedor en el tenant")
    name: str = Field(..., min_length=1, max_length=255, description="Nombre o razón social")
    tax_id: str | None = Field(None, max_length=50, description="RFC o identificación fiscal")
    email: EmailStr | None = Field(None, description="Correo de contacto")
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=1000)
    contact_name: str | None = Field(None, max_length=255)
    currency: str = Field("MXN", max_length=10, description="Moneda de negociación (ISO 4217)")
    payment_terms_days: int = Field(30, ge=0, le=365, description="Días de plazo de pago")
    notes: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    tax_id: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    address: str | None = None
    contact_name: str | None = None
    currency: str | None = Field(None, max_length=10)
    payment_terms_days: int | None = Field(None, ge=0, le=365)
    is_active: bool | None = None
    notes: str | None = None


class SupplierResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    tax_id: str | None
    email: str | None
    phone: str | None
    address: str | None
    contact_name: str | None
    currency: str
    payment_terms_days: int
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierSummary(BaseModel):
    id: UUID
    code: str
    name: str

    model_config = {"from_attributes": True}


# ── SupplierProduct (RF-012 Costos Reposición) ────────────────────────────────

class SupplierProductCreate(BaseModel):
    product_id: UUID = Field(..., description="ID del producto a asociar")
    supplier_sku: str | None = Field(None, max_length=100, description="SKU del proveedor para este producto")
    unit_cost: Decimal = Field(..., gt=0, description="Costo unitario de compra")
    currency: str = Field("MXN", max_length=10)
    lead_time_days: int = Field(0, ge=0, le=365, description="Días de tiempo de entrega")
    moq: Decimal = Field(Decimal("1"), gt=0, description="Cantidad mínima de pedido")
    is_preferred: bool = Field(False, description="Proveedor preferido para este producto")


class SupplierProductUpdate(BaseModel):
    supplier_sku: str | None = Field(None, max_length=100)
    unit_cost: Decimal | None = Field(None, gt=0)
    currency: str | None = Field(None, max_length=10)
    lead_time_days: int | None = Field(None, ge=0, le=365)
    moq: Decimal | None = Field(None, gt=0)
    is_preferred: bool | None = None


class SupplierProductResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    product_id: UUID
    supplier_sku: str | None
    unit_cost: Decimal
    currency: str
    lead_time_days: int
    moq: Decimal
    is_preferred: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
