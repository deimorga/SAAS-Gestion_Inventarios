from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReservationItem(Base):
    __tablename__ = "reservation_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    reservation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("zones.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    confirmed_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    # Lo que pidió el cliente (opcional). Lo que se apartó de verdad va en ReservationAllocation.
    lot_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bin_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("bins.id"), nullable=True)
    supplier_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("suppliers.id"), nullable=True)


class ReservationAllocation(Base):
    """Parte de un ítem de reserva apartada de un saldo concreto (lote + bin + proveedor).

    Un ítem se reparte en varias asignaciones cuando un solo lote no alcanza; `seq`
    conserva el orden FEFO/FIFO en que se eligieron, que es el orden de consumo.
    """

    __tablename__ = "reservation_allocations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    reservation_item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("reservation_items.id", ondelete="CASCADE"), nullable=False
    )
    stock_balance_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("stock_balances.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bin_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("bins.id"), nullable=True)
    supplier_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("suppliers.id"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    confirmed_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
