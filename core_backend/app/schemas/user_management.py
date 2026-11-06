from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator

# Estado derivado de `is_active` y `must_change_password`; no es una columna (RF-047).
UserStatus = Literal["pending", "active", "disabled"]

# `api_consumer` deja de ser un rol asignable (RN-052-3): ningún permiso lo reconoce.
_ASSIGNABLE_ROLE_PATTERN = r"^(tenant_admin|inventory_manager|viewer)$"


def _normalize_email(value: str) -> str:
    """El email se guarda y se compara en minúsculas y sin espacios (RN-052-2)."""
    return value.strip().lower()


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(
        "viewer",
        pattern=_ASSIGNABLE_ROLE_PATTERN,
        description=(
            "`tenant_admin`, `inventory_manager` o `viewer`. Por defecto `viewer`. "
            "Un `tenant_admin` solo puede asignar `inventory_manager` o `viewer`."
        ),
    )

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return _normalize_email(value)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    role: str | None = Field(None, pattern=_ASSIGNABLE_ROLE_PATTERN)
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool
    is_protected: bool = False
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[misc]
    @property
    def status(self) -> UserStatus:
        if self.is_active:
            return "active"
        return "pending" if self.must_change_password else "disabled"


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int


class SuperAdminCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return _normalize_email(value)


class SuperAdminUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    is_active: bool | None = None


class MessageResponse(BaseModel):
    message: str
