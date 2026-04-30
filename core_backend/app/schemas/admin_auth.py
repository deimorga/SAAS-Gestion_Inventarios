from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import UserSummary


class AdminRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, description="Mínimo 12 caracteres")
    full_name: str = Field(..., min_length=2, max_length=255)


class AdminLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary
