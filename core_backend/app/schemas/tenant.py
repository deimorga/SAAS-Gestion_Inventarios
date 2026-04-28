from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TenantConfigUpdate(BaseModel):
    allow_negative_stock: bool | None = None
    valuation_method: Literal["CPP", "PEPS"] | None = None
    auto_reserve_on_order: bool | None = None
    reservation_ttl_minutes: int | None = Field(None, ge=1, le=1440)
    low_stock_alert_enabled: bool | None = None
    require_reason_code: bool | None = None
    default_currency: str | None = Field(None, max_length=3)
    timezone: str | None = None


class TenantConfigResponse(BaseModel):
    tenant_id: UUID
    config: dict
    subscription_tier: str
    updated_at: datetime
