from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_admin
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse
from app.schemas.common import PaginatedResponse
from app.services.api_key import create_api_key, list_api_keys, revoke_api_key
from app.services.api_key_rotation import rotate_api_key
from app.services.audit import log_action

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="Listar API Keys del tenant",
    description="Retorna las API Keys del tenant con su estado y scopes. El secreto nunca se retorna tras la creación.",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Solo tenant_admin o super_admin"},
    },
)
async def get_api_keys(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Registros por página"),
    is_active: bool | None = Query(None, description="Filtrar por estado activo/inactivo"),
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    return await list_api_keys(db, auth.tenant_id, page, page_size, is_active)


@router.post(
    "",
    response_model=ApiKeyCreateResponse,
    status_code=201,
    summary="Crear API Key",
    description=(
        "Genera una nueva API Key con los scopes indicados. "
        "**El secreto (`key_secret`) solo se muestra una vez en la respuesta de creación.** "
        "Enviarlo como cabecera `X-API-Key: <key_secret>` en requests subsiguientes."
    ),
    responses={
        201: {"description": "API Key creada. El secreto solo se expone en esta respuesta."},
        401: {"description": "No autenticado"},
        403: {"description": "Solo tenant_admin o super_admin"},
    },
)
async def add_api_key(
    body: ApiKeyCreate,
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    result = await create_api_key(body, db, auth.tenant_id)
    await log_action(
        db=db,
        tenant_id=auth.tenant_id,
        entity="api_keys",
        entity_id=str(result.id),
        action="CREATE",
        new_values={"name": result.name, "scopes": [s.value for s in result.scopes]},
        performed_by={"type": "user", "id": auth.user_id},
    )
    return result


@router.delete(
    "/{key_id}",
    status_code=204,
    summary="Revocar API Key",
    description="Desactiva permanentemente la API Key. Las requests futuras con esa key serán rechazadas.",
    responses={
        204: {"description": "API Key revocada"},
        404: {"description": "API Key no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Solo tenant_admin o super_admin"},
    },
)
async def delete_api_key(
    key_id: str,
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    await revoke_api_key(key_id, db, auth.tenant_id)
    await log_action(
        db=db,
        tenant_id=auth.tenant_id,
        entity="api_keys",
        entity_id=key_id,
        action="DELETE",
        new_values={"is_active": False},
        performed_by={"type": "user", "id": auth.user_id},
    )


@router.post(
    "/{key_uuid}/rotate",
    response_model=ApiKeyCreateResponse,
    status_code=201,
    summary="Rotar API Key",
    description=(
        "Genera una nueva API Key con los mismos atributos (scopes, nombre, IP whitelist) "
        "que la existente. La fecha de expiración se calcula con staggering para evitar "
        "colisiones entre tenants (±14 días desde hoy + API_KEY_EXPIRY_DAYS). "
        "Con `immediate=true` la clave anterior se revoca al instante; "
        "con `immediate=false` (default) permanece activa durante el período de gracia "
        "configurado por el tenant (default 30 días)."
    ),
    responses={
        201: {"description": "Nueva API Key generada. El secreto solo se expone en esta respuesta."},
        404: {"description": "API Key no encontrada"},
        409: {"description": "La API Key ya está inactiva"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def rotate_key(
    key_uuid: str,
    immediate: bool = Query(False, description="Revocar la clave anterior inmediatamente"),
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    return await rotate_api_key(key_uuid, auth.tenant_id, immediate, db)
