from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

VALID_EVENTS = [
    "transaction.receipt",
    "transaction.issue",
    "transaction.transfer",
    "transaction.adjustment",
    "reservation.created",
    "reservation.confirmed",
    "reservation.cancelled",
    "reservation.expired",
    "stock.low",
]


class WebhookCreate(BaseModel):
    url: HttpUrl = Field(..., description="URL de destino. Se recomienda HTTPS.", examples=["https://myapp.com/hooks/inventory"])
    secret: str = Field(..., min_length=16, max_length=128, description="Secreto para firma HMAC-SHA256 (mín 16 caracteres)")
    events: list[str] = Field(
        ...,
        min_length=1,
        description=f"Lista de eventos a suscribir. Valores válidos: {', '.join(VALID_EVENTS)}",
        examples=[["transaction.receipt", "reservation.created"]],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://myapp.com/hooks/inventory",
                "secret": "mi-secreto-seguro-de-minimo-16chars",
                "events": ["transaction.receipt", "reservation.created"],
            }
        }
    )


class WebhookUpdate(BaseModel):
    url: HttpUrl | None = Field(None, description="Nueva URL de destino")
    secret: str | None = Field(None, min_length=16, max_length=128, description="Nuevo secreto de firma")
    events: list[str] | None = Field(None, min_length=1, description="Nueva lista de eventos")
    is_active: bool | None = Field(None, description="Activar o desactivar el endpoint")


class WebhookEndpointResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookDeliveryResponse(BaseModel):
    id: str
    event_type: str
    status: str = Field(..., description="PENDING | DELIVERED | FAILED")
    attempts: int
    last_response_code: int | None
    next_attempt_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookTestResponse(BaseModel):
    delivered: bool = Field(..., description="True si el servidor respondió con HTTP 2xx")
    response_code: int | None = Field(None, description="Código HTTP de respuesta del servidor de destino")
    error: str | None = Field(None, description="Descripción del error de red, si aplica")
