from pydantic import BaseModel, EmailStr, Field

from app.core.security import PASSWORD_MIN_LENGTH


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Token recibido por email (un solo uso, 60 min)")
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        description=f"Nueva contraseña (mínimo {PASSWORD_MIN_LENGTH} caracteres)",
    )
