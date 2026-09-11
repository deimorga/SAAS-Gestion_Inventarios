"""Schemas de `/v1/platform/*` — aprovisionamiento de tenants por una plataforma externa.

El caso de uso es Appits (Gestión-Talleres): cuando un taller crea una sede,
Appits pide a Inventarios un tenant nuevo, aislado, listo para operar. Una sola
llamada devuelve todo lo que Appits necesita guardar para conectar esa sede.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.api_key import ApiKeyScope

# Lo que una sede necesita para operar su inventario desde Appits. Excluye a
# propósito ADMIN (gestión de usuarios/keys) y PLATFORM (aprovisionamiento).
DEFAULT_SEDE_SCOPES: list[ApiKeyScope] = [
    ApiKeyScope.READ_CATALOG,
    ApiKeyScope.WRITE_CATALOG,
    ApiKeyScope.READ_INVENTORY,
    ApiKeyScope.WRITE_INVENTORY,
    ApiKeyScope.MANAGE_WAREHOUSES,
    ApiKeyScope.MANAGE_RESERVATIONS,
]


class PlatformWarehouseSpec(BaseModel):
    code: str = Field(
        "PRINCIPAL",
        min_length=2,
        max_length=20,
        pattern=r"^[A-Za-z0-9\-_]+$",
        description="Código del almacén inicial. Solo letras, dígitos, guiones y guiones bajos.",
    )
    name: str = Field("Bodega Principal", min_length=1, max_length=100)
    location_address: str | None = Field(None, description="Dirección física de la sede.")


class PlatformTenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Nombre de la sede.")
    tax_id: str | None = Field(None, max_length=50, description="NIT de la sede.")
    admin_email: EmailStr = Field(..., description="Correo del administrador de la sede. Recibe el email de activación.")
    admin_full_name: str = Field(..., min_length=2, max_length=255)

    external_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Id de la sede en la plataforma (p. ej. el shop_id de Appits). Único por proveedor.",
    )
    external_provider: str = Field(
        "appits",
        max_length=50,
        pattern=r"^[a-z0-9_-]+$",
        description="Plataforma que aprovisiona el tenant.",
    )
    parent_tenant_id: UUID | None = Field(
        None,
        description="Tenant de Inventarios del taller principal del que depende la sede. Solo referencia.",
    )
    subscription_tier: str = Field("STARTER", pattern=r"^(STARTER|PROFESSIONAL|ENTERPRISE)$")

    warehouse: PlatformWarehouseSpec = Field(default_factory=PlatformWarehouseSpec)
    api_key_name: str = Field("Appits", min_length=3, max_length=100)
    api_key_scopes: list[ApiKeyScope] = Field(
        default_factory=lambda: list(DEFAULT_SEDE_SCOPES),
        description="Scopes de la API key de la sede. No admite ADMIN ni PLATFORM.",
    )

    @field_validator("api_key_scopes")
    @classmethod
    def _sede_scopes_only(cls, scopes: list[ApiKeyScope]) -> list[ApiKeyScope]:
        if not scopes:
            raise ValueError("La API key necesita al menos un scope")
        prohibidos = {ApiKeyScope.ADMIN, ApiKeyScope.PLATFORM} & set(scopes)
        if prohibidos:
            raise ValueError(f"Scopes no permitidos para una sede: {sorted(s.value for s in prohibidos)}")
        return scopes

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Taller Demo — Sede Norte",
                "tax_id": "900123456-7",
                "admin_email": "sede.norte@tallerdemo.com",
                "admin_full_name": "Administrador Sede Norte",
                "external_id": "shop_42",
                "external_provider": "appits",
                "parent_tenant_id": "bd944e9b-2eb6-40d1-87b0-a91d94f04c64",
                "warehouse": {"code": "PRINCIPAL", "name": "Bodega Sede Norte"},
                "api_key_name": "Appits — Sede Norte",
            }
        }
    }


class PlatformZone(BaseModel):
    id: UUID
    code: str
    zone_type: str


class PlatformWarehouse(BaseModel):
    id: UUID
    code: str
    name: str
    zones: list[PlatformZone]


class PlatformApiKey(BaseModel):
    id: UUID
    key_id: str
    key_secret: str = Field(..., description="Se muestra una sola vez. Guardarlo cifrado.")
    scopes: list[str]
    expires_at: datetime | None


class PlatformTenantCreated(BaseModel):
    tenant_id: UUID
    slug: str
    name: str
    external_provider: str
    external_id: str
    parent_tenant_id: UUID | None
    admin_user_id: UUID
    admin_email: str
    warehouse: PlatformWarehouse
    api_key: PlatformApiKey


class PlatformTenantInfo(BaseModel):
    tenant_id: UUID
    slug: str
    name: str
    is_active: bool
    tax_id: str | None
    external_provider: str | None
    external_id: str | None
    parent_tenant_id: UUID | None
    warehouses: list[PlatformWarehouse]
    created_at: datetime


class PlatformTenantDeactivated(BaseModel):
    tenant_id: UUID
    is_active: bool
    api_keys_revoked: int
