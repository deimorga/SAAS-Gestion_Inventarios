from enum import Enum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """Rol del usuario dentro del sistema.

    - `super_admin`: Administrador MicroNuba — acceso total entre tenants.
    - `tenant_admin`: Administrador del tenant — gestiona usuarios y API Keys propios.
    - `inventory_manager`: Operador — puede registrar movimientos y consultar inventario.
    - `viewer`: Solo lectura — consulta reportes y saldos sin modificar datos.
    """

    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    INVENTORY_MANAGER = "inventory_manager"
    VIEWER = "viewer"


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        description="Correo electrónico del usuario registrado en el sistema.",
        examples=["admin@mi-taller.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Contraseña del usuario.",
        examples=["Mi$Passw0rd"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "admin@mi-taller.com",
                "password": "Mi$Passw0rd",
            }
        }
    }


class RefreshRequest(BaseModel):
    refresh_token: str = Field(
        ...,
        description="Token de actualización obtenido en el login. Válido por 7 días.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIuLi4ifQ.xxx"],
    )


class LogoutRequest(BaseModel):
    refresh_token: str = Field(
        ...,
        description="Token de actualización a invalidar. Después del logout el token queda en blacklist.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIuLi4ifQ.xxx"],
    )


class UserSummary(BaseModel):
    id: UUID = Field(..., description="UUID único del usuario.")
    email: str = Field(..., description="Correo electrónico del usuario.")
    full_name: str = Field(..., description="Nombre completo del usuario.")
    role: UserRole = Field(..., description="Rol asignado dentro del tenant.")
    tenant_id: UUID = Field(..., description="UUID del tenant al que pertenece el usuario.")


class TokenResponse(BaseModel):
    access_token: str = Field(
        ...,
        description="JWT de acceso. Incluir en el header: Authorization: Bearer <token>. Expira en 30 minutos.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIuLi4ifQ.sig"],
    )
    refresh_token: str = Field(
        ...,
        description="Token de actualización. Usar en POST /auth/refresh para obtener un nuevo access_token. Expira en 7 días.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIuLi4ifQ.ref"],
    )
    token_type: str = Field(
        "bearer",
        description="Esquema de autenticación. Siempre 'bearer'.",
        examples=["bearer"],
    )
    expires_in: int = Field(
        ...,
        description="Tiempo de vida del access_token en segundos (1800 = 30 minutos).",
        examples=[1800],
    )
    user: UserSummary = Field(..., description="Información básica del usuario autenticado.")


class RefreshResponse(BaseModel):
    access_token: str = Field(
        ...,
        description="Nuevo JWT de acceso. Reemplaza al access_token anterior.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIuLi4ifQ.new"],
    )
    refresh_token: str = Field(
        ...,
        description="Nuevo token de actualización (rotación automática por seguridad).",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIuLi4ifQ.rot"],
    )
    token_type: str = Field(
        "bearer",
        description="Esquema de autenticación. Siempre 'bearer'.",
        examples=["bearer"],
    )
    expires_in: int = Field(
        ...,
        description="Tiempo de vida del nuevo access_token en segundos.",
        examples=[1800],
    )
