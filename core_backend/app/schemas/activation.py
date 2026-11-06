from pydantic import BaseModel, Field

from app.core.security import PASSWORD_MIN_LENGTH


class ActivateRequest(BaseModel):
    token: str = Field(..., description="Token de activación recibido por email")
    password: str = Field(
        ..., min_length=PASSWORD_MIN_LENGTH, description=f"Contraseña inicial (mínimo {PASSWORD_MIN_LENGTH} caracteres)"
    )


class ResendActivationRequest(BaseModel):
    user_id: str = Field(..., description="ID del usuario al que se le reenvía la activación")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(
        ..., min_length=PASSWORD_MIN_LENGTH, description=f"Nueva contraseña (mínimo {PASSWORD_MIN_LENGTH} caracteres)"
    )


class ActivationResponse(BaseModel):
    message: str = "Cuenta activada exitosamente"
    # Solo al activar con éxito: el portal lleva al login con el email prellenado (RF-046).
    # Lo recibe únicamente quien tiene el token válido, es decir, el destinatario del email.
    email: str | None = None


class ChangePasswordResponse(BaseModel):
    message: str = "Contraseña actualizada exitosamente"
