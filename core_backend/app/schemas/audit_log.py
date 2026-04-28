from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PerformerInfo(BaseModel):
    type: Literal["user", "api_key"]
    id: UUID
    email: str | None = None


class AuditLogEntry(BaseModel):
    id: UUID
    entity: str
    entity_id: UUID
    action: Literal["CREATE", "UPDATE", "DELETE"]
    old_values: dict | None
    new_values: dict
    performed_by: PerformerInfo
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
