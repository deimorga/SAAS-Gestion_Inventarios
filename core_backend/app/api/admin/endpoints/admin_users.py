"""Gestión de usuarios de un tenant desde el portal de super_admin.

Existe porque `/v1/auth/resend-activation` exige rol `tenant_admin` y resuelve el
usuario contra el tenant de quien llama: un `super_admin` recibe 403 y no hay
forma de reenviar la activación. Sin estos endpoints, un tenant recién creado
cuyo email de bienvenida no llegó queda inaccesible sin tocar la base de datos.
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_super_admin
from app.core.database import AsyncSessionLocal, set_tenant_context
from app.core.redis_client import get_redis
from app.schemas.activation import ActivationResponse
from app.schemas.user_management import UserListResponse
from app.services import user_management as user_service
from app.services.activation import resend_activation

router = APIRouter(tags=["Admin — Usuarios"])


async def _tenant_session(tenant_id: str) -> AsyncSession:
    """Sesión con el RLS del tenant indicado, no con el bypass de super_admin.

    Operar bajo las políticas del tenant hace que un `tenant_id` equivocado
    devuelva vacío en lugar de tocar datos de otro cliente.
    """
    session = AsyncSessionLocal()
    await set_tenant_context(session, tenant_id)
    return session


@router.get(
    "/tenants/{tenant_id}/users",
    response_model=UserListResponse,
    summary="Listar usuarios de un tenant",
    description=(
        "Devuelve los usuarios del tenant indicado. Permite identificar cuáles "
        "siguen pendientes de activación (`is_active=false`)."
    ),
)
async def admin_list_users(
    tenant_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    _auth: AuthContext = Depends(require_super_admin),
) -> UserListResponse:
    session = await _tenant_session(tenant_id)
    async with session:
        return await user_service.list_users(
            tenant_id=tenant_id,
            db=session,
            page=page,
            size=size,
        )


@router.post(
    "/tenants/{tenant_id}/users/{user_id}/resend-activation",
    response_model=ActivationResponse,
    summary="Reenviar activación a un usuario de un tenant",
    description=(
        "Genera un nuevo token de activación (TTL 48h) y encola el email. "
        "El token anterior no se invalida: expira por su cuenta."
    ),
    responses={
        200: {"description": "Token regenerado y email encolado"},
        404: {"description": "Usuario no encontrado o no pertenece al tenant"},
        409: {"description": "La cuenta ya está activada"},
        503: {"description": "No se pudo encolar el email"},
    },
)
async def admin_resend_activation(
    tenant_id: str,
    user_id: str,
    _auth: AuthContext = Depends(require_super_admin),
    redis: aioredis.Redis = Depends(get_redis),
) -> ActivationResponse:
    session = await _tenant_session(tenant_id)
    async with session:
        await resend_activation(user_id, tenant_id, session, redis)
    return ActivationResponse(message="Email de activación reenviado")
