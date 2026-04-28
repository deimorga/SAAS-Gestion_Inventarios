from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductUom(Base):
    __tablename__ = "product_uom"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    product_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    uom_code: Mapped[str] = mapped_column(String(20), nullable=False)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    is_purchase_uom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_sale_uom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
