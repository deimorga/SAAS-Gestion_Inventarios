from pydantic import BaseModel, Field


class ActivateRequest(BaseModel):
    token: str = Field(..., description="Token de activación recibido por email")
    password: str = Field(..., min_length=8, description="Contraseña inicial (mínimo 8 caracteres)")


class ResendActivationRequest(BaseModel):
    user_id: str = Field(..., description="ID del usuario al que se le reenvía la activación")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, description="Nueva contraseña (mínimo 8 caracteres)")


class ActivationResponse(BaseModel):
    message: str = "Cuenta activada exitosamente"


class ChangePasswordResponse(BaseModel):
    message: str = "Contraseña actualizada exitosamente"
