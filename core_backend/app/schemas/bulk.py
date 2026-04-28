from pydantic import BaseModel, Field

from app.schemas.inventory import IssueRequest, ReceiptRequest, TransferRequest


class BulkItemResult(BaseModel):
    index: int = Field(..., description="Índice del ítem en el lote (0-based)")
    status: str = Field(..., description="'ok' si fue procesado exitosamente, 'error' si falló")
    transaction_id: str | None = Field(None, description="UUID de la transacción creada (solo cuando status='ok')")
    detail: str | None = Field(None, description="Descripción del error (solo cuando status='error')")


class BulkResult(BaseModel):
    total: int = Field(..., description="Total de ítems recibidos en el lote")
    succeeded: int = Field(..., description="Ítems procesados exitosamente")
    failed: int = Field(..., description="Ítems que fallaron")
    results: list[BulkItemResult] = Field(..., description="Resultado individual por ítem")


class BulkReceiptRequest(BaseModel):
    items: list[ReceiptRequest] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Lote de entradas de mercancía. Máximo 500 ítems por lote.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "warehouse_id": "wh-uuid-1",
                        "zone_id": "zone-uuid-1",
                        "reference_type": "PO",
                        "reference_id": "PO-001",
                        "reason_code": "COMPRA",
                        "items": [{"product_id": "prod-uuid", "quantity": 10, "unit_cost": 5000}],
                    }
                ]
            }
        }
    }


class BulkIssueRequest(BaseModel):
    items: list[IssueRequest] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Lote de salidas de mercancía. Máximo 500 ítems por lote.",
    )


class BulkTransferRequest(BaseModel):
    items: list[TransferRequest] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Lote de transferencias inter-almacén. Máximo 500 ítems por lote.",
    )
