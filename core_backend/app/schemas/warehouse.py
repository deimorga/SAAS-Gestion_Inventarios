from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ZoneType(str, Enum):
    """Tipo funcional de una zona dentro del almacén.

    - `RECEIVING`: Zona de recepción — donde llega la mercancía antes de ser inspeccionada.
    - `STORAGE`: Almacenamiento general — stock disponible para despacho.
    - `PICKING`: Alistamiento — productos separados listos para armar pedidos.
    - `DISPATCH`: Despacho — productos empacados esperando salir del almacén.
    - `QUARANTINE`: Cuarentena — mercancía pendiente de inspección, devolución o destrucción.
    - `TRANSIT`: Tránsito — stock en movimiento entre almacenes (estado IN_TRANSIT).
    """

    RECEIVING = "RECEIVING"
    STORAGE = "STORAGE"
    PICKING = "PICKING"
    DISPATCH = "DISPATCH"
    QUARANTINE = "QUARANTINE"
    TRANSIT = "TRANSIT"


# ── Warehouse ─────────────────────────────────────────────────────────────────

class WarehouseCreate(BaseModel):
    code: str = Field(
        ...,
        min_length=2,
        max_length=20,
        pattern=r"^[A-Za-z0-9\-_]+$",
        description="Código único del almacén dentro del tenant. Solo letras, dígitos, guiones y guiones bajos. Inmutable.",
        examples=["TALLER-BOG-01"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre descriptivo del almacén.",
        examples=["Bodega Principal Bogotá"],
    )
    location_address: str | None = Field(
        None,
        description="Dirección física del almacén. Opcional.",
        examples=["Calle 80 # 45-23, Bogotá, Colombia"],
    )
    is_virtual: bool = Field(
        False,
        description="Si true, es un almacén lógico sin ubicación física (ej: stock en tránsito, consignación). No permite movimientos de recepción.",
        examples=[False],
    )
    timezone: str | None = Field(
        None,
        description="Zona horaria del almacén en formato IANA (ej: America/Bogota). Nulo = usa la zona del tenant.",
        examples=["America/Bogota"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "TALLER-BOG-01",
                "name": "Bodega Principal Bogotá",
                "location_address": "Calle 80 # 45-23, Bogotá, Colombia",
                "is_virtual": False,
                "timezone": "America/Bogota",
            }
        }
    }


class WarehouseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    location_address: str | None = None
    is_active: bool | None = None
    timezone: str | None = None


class WarehouseListItem(BaseModel):
    id: UUID
    code: str
    name: str
    is_virtual: bool
    is_active: bool

    model_config = {"from_attributes": True}


class WarehouseResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    location_address: str | None
    is_virtual: bool
    is_active: bool
    timezone: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Zone ──────────────────────────────────────────────────────────────────────

class ZoneCreate(BaseModel):
    code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Código único de la zona dentro del almacén. Ej: ZONA-A, PICKING-01.",
        examples=["ZONA-ALMACEN"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre descriptivo de la zona.",
        examples=["Zona de Almacenamiento General"],
    )
    zone_type: ZoneType = Field(
        ...,
        description="Tipo funcional de la zona. Determina qué movimientos se permiten en ella.",
        examples=["STORAGE"],
    )
    capacity_volume: Decimal | None = Field(
        None,
        gt=0,
        description="Capacidad máxima en metros cúbicos (m³). Nulo = sin límite de volumen.",
        examples=[50.5],
    )
    capacity_weight: Decimal | None = Field(
        None,
        gt=0,
        description="Capacidad máxima en kilogramos (kg). Nulo = sin límite de peso.",
        examples=[2000],
    )
    parent_zone_id: UUID | None = Field(
        None,
        description="UUID de la zona padre para crear sub-zonas. Nulo = zona de nivel raíz en el almacén.",
        examples=[None],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "ZONA-ALMACEN",
                "name": "Zona de Almacenamiento General",
                "zone_type": "STORAGE",
                "capacity_volume": 50.5,
                "capacity_weight": 2000,
                "parent_zone_id": None,
            }
        }
    }


class ZoneUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    zone_type: ZoneType | None = None
    is_active: bool | None = None
    capacity_volume: Decimal | None = Field(None, gt=0)
    capacity_weight: Decimal | None = Field(None, gt=0)


class ZoneResponse(BaseModel):
    id: UUID
    warehouse_id: UUID
    tenant_id: UUID
    code: str
    name: str
    zone_type: ZoneType
    path: str
    is_active: bool
    capacity_volume: Decimal | None
    capacity_weight: Decimal | None
    parent_zone_id: UUID | None

    model_config = {"from_attributes": True}
