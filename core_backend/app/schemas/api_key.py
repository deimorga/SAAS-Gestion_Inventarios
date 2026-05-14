from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyScope(str, Enum):
    """Scope de acceso de una API Key.

    - `READ_INVENTORY`: Consulta de saldos disponibles, movimientos y ledger histórico.
    - `WRITE_INVENTORY`: Registrar entradas, salidas y transferencias de mercancía.
    - `READ_CATALOG`: Consulta de productos, categorías, UOM y kits.
    - `WRITE_CATALOG`: Crear y editar productos, categorías y unidades de medida.
    - `MANAGE_WAREHOUSES`: Crear y administrar almacenes, zonas y bins.
    - `MANAGE_RESERVATIONS`: Crear, confirmar y liberar reservas de stock.
    - `ADMIN`: Acceso completo — incluye gestión de usuarios y API Keys del tenant.
    """

    READ_INVENTORY = "READ_INVENTORY"
    WRITE_INVENTORY = "WRITE_INVENTORY"
    READ_CATALOG = "READ_CATALOG"
    WRITE_CATALOG = "WRITE_CATALOG"
    MANAGE_WAREHOUSES = "MANAGE_WAREHOUSES"
    MANAGE_RESERVATIONS = "MANAGE_RESERVATIONS"
    ADMIN = "ADMIN"


class ApiKeyCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Nombre descriptivo para identificar el uso de esta API Key (ej: sistema POS, app móvil).",
        examples=["Integración POS Taller Principal"],
    )
    scopes: list[ApiKeyScope] = Field(
        ...,
        description=(
            "Lista de scopes otorgados. Use el mínimo necesario. "
            "Ej: solo lectura de inventario → ['READ_INVENTORY', 'READ_CATALOG']. "
            "Registrar ventas → ['WRITE_INVENTORY', 'READ_CATALOG', 'READ_INVENTORY']."
        ),
        examples=[["READ_INVENTORY", "WRITE_INVENTORY", "READ_CATALOG"]],
    )
    ip_whitelist: list[str] | None = Field(
        None,
        description="Lista de IPs o rangos CIDR desde los que se permite usar esta key. Nulo = sin restricción de IP.",
        examples=[["192.168.1.100", "10.0.0.0/24"]],
    )
    expires_at: datetime | None = Field(
        None,
        description="Fecha y hora de expiración en formato ISO 8601 UTC. Nulo = sin expiración automática.",
        examples=["2026-12-31T23:59:59Z"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Integración POS Taller Principal",
                "scopes": ["READ_INVENTORY", "WRITE_INVENTORY", "READ_CATALOG"],
                "ip_whitelist": None,
                "expires_at": "2027-01-01T00:00:00Z",
            }
        }
    }


class ApiKeyResponse(BaseModel):
    id: UUID
    key_id: str
    name: str
    scopes: list[ApiKeyScope]
    ip_whitelist: list[str] | None
    is_active: bool
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(ApiKeyResponse):
    key_secret: str
