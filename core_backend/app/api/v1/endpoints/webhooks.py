from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_auth_db, require_admin, require_inventory_read
from app.schemas.webhook import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookEndpointResponse,
    WebhookTestResponse,
    WebhookUpdate,
)
from app.services import webhook as svc

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "",
    response_model=WebhookEndpointResponse,
    status_code=201,
    summary="Registrar webhook endpoint",
    description=(
        "Registra una URL de destino a la que el sistema enviará eventos HTTP POST cuando ocurran "
        "los eventos suscritos. Cada envío incluye el header `X-Webhook-Signature: sha256=<hmac>` "
        "para verificar autenticidad. Requiere rol de administrador del tenant."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes (requiere tenant_admin)"},
        422: {"description": "URL inválida, secret demasiado corto o lista de eventos vacía"},
    },
)
async def create_webhook(
    body: WebhookCreate,
    auth: AuthContext = Depends(require_admin),
    db=Depends(get_auth_db),
):
    return await svc.create_endpoint(db, auth.tenant_id, body)


@router.get(
    "",
    response_model=list[WebhookEndpointResponse],
    summary="Listar webhook endpoints",
    description="Retorna todos los endpoints registrados del tenant, ordenados por fecha de creación descendente.",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def list_webhooks(
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.list_endpoints(db, auth.tenant_id)


@router.get(
    "/{webhook_id}",
    response_model=WebhookEndpointResponse,
    summary="Obtener detalle de un webhook endpoint",
    description="Retorna la configuración completa de un endpoint registrado (sin el secreto de firma).",
    responses={
        404: {"description": "Webhook endpoint no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def get_webhook(
    webhook_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.get_endpoint(db, auth.tenant_id, webhook_id)


@router.patch(
    "/{webhook_id}",
    response_model=WebhookEndpointResponse,
    summary="Actualizar webhook endpoint",
    description=(
        "Actualiza parcialmente un endpoint registrado. Solo se modifican los campos enviados. "
        "Útil para rotar el secreto de firma, cambiar la URL o activar/desactivar el endpoint."
    ),
    responses={
        404: {"description": "Webhook endpoint no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes (requiere tenant_admin)"},
    },
)
async def update_webhook(
    webhook_id: str,
    body: WebhookUpdate,
    auth: AuthContext = Depends(require_admin),
    db=Depends(get_auth_db),
):
    return await svc.update_endpoint(db, auth.tenant_id, webhook_id, body)


@router.delete(
    "/{webhook_id}",
    status_code=204,
    summary="Eliminar webhook endpoint",
    description="Elimina el endpoint y su historial de entregas. La operación es irreversible.",
    responses={
        204: {"description": "Eliminado exitosamente"},
        404: {"description": "Webhook endpoint no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes (requiere tenant_admin)"},
    },
)
async def delete_webhook(
    webhook_id: str,
    auth: AuthContext = Depends(require_admin),
    db=Depends(get_auth_db),
):
    await svc.delete_endpoint(db, auth.tenant_id, webhook_id)


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Enviar ping de prueba al endpoint",
    description=(
        "Envía un payload de tipo `ping` al endpoint registrado para verificar la conectividad "
        "y la firma HMAC. La respuesta indica si el servidor de destino respondió con HTTP 2xx. "
        "No lanza error si el destino no responde — devuelve `delivered: false` con el detalle."
    ),
    responses={
        404: {"description": "Webhook endpoint no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes (requiere tenant_admin)"},
    },
)
async def test_webhook(
    webhook_id: str,
    auth: AuthContext = Depends(require_admin),
    db=Depends(get_auth_db),
):
    return await svc.test_endpoint_ping(db, auth.tenant_id, webhook_id)


@router.get(
    "/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
    summary="Historial de entregas de un endpoint",
    description=(
        "Retorna los últimos 100 registros de entrega del endpoint, con su estado "
        "(PENDING / DELIVERED / FAILED), intentos realizados y código de respuesta HTTP. "
        "Útil para depurar fallos de integración."
    ),
    responses={
        404: {"description": "Webhook endpoint no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def get_deliveries(
    webhook_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.get_deliveries(db, auth.tenant_id, webhook_id)
