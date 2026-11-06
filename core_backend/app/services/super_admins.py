"""Gestión de super_admins (RF-049).

Los super_admins viven en el tenant interno `micronuba-internal` y NO aparecen en la gestión
de usuarios de tenants (RN-049-4). La cuenta raíz de cada ambiente (`is_protected`) no se
puede desactivar, editar ni resetear a la fuerza: la comprobación va aquí, en el servicio,
y no solo en el portal (L-1, RN-049-5).
"""
import secrets
from datetime import datetime, timezone
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MICRONUBA_TENANT_ID
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user_management import SuperAdminCreate, SuperAdminUpdate, UserResponse
from app.services.activation import dispatch_activation_email, generate_activation_token
from app.services.password_reset import dispatch_reset_email, issue_reset_token
from app.services.sessions import revoke_all_sessions
from app.services.user_management import EMAIL_TAKEN, Actor, audit_user, email_exists, is_pending

PROTECTED_DETAIL = "Cuenta raíz protegida"


async def _get_super_admin(db: AsyncSession, user_id: str, *, lock: bool = False) -> User:
    query = select(User).where(User.id == user_id, User.role == "super_admin")
    if lock:
        query = query.with_for_update()
    user = (await db.execute(query)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Super admin no encontrado")
    return user


async def _lock_active_super_admin_ids(db: AsyncSession) -> list[str]:
    """Bloquea y devuelve los ids de los super_admins activos (para la cuenta atómica de RN-049-2)."""
    return list(
        (
            await db.execute(
                select(User.id).where(User.role == "super_admin", User.is_active.is_(True)).with_for_update()
            )
        ).scalars().all()
    )


async def list_super_admins(db: AsyncSession) -> list[UserResponse]:
    users = (
        await db.execute(select(User).where(User.role == "super_admin").order_by(User.created_at))
    ).scalars().all()
    return [UserResponse.model_validate(u) for u in users]


async def create_super_admin(
    request: SuperAdminCreate,
    actor: Actor,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> UserResponse:
    if await email_exists(request.email):
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)

    user = User(
        id=str(uuid4()),
        tenant_id=MICRONUBA_TENANT_ID,
        email=request.email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        full_name=request.full_name,
        role="super_admin",
        is_active=False,
        must_change_password=True,
        # Los creados desde el portal NO son cuenta raíz (RN-049-6): proteger otra cuenta es
        # una decisión del responsable del producto y se aplica en base de datos.
        is_protected=False,
        created_by=actor.user_id if actor.kind == "user" else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from None

    await audit_user(db, user, "CREATE", actor, new_values={"email": user.email, "role": user.role})
    await db.refresh(user)

    token = await generate_activation_token(user.id, redis)
    dispatch_activation_email(user.email, user.full_name, token, template="account_activation")
    return UserResponse.model_validate(user)


async def update_super_admin(
    user_id: str,
    request: SuperAdminUpdate,
    actor: Actor,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> UserResponse:
    # Bloqueo de la fila: dos desactivaciones simultáneas no pueden dejar el sistema sin super_admin
    target = await _get_super_admin(db, user_id, lock=True)

    if target.is_protected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, PROTECTED_DETAIL)  # incluye al propio dueño (RN-049-5)

    deactivating = request.is_active is False
    if deactivating and target.id == actor.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No puedes desactivarte a ti mismo")  # RN-049-1
    if request.is_active is True and is_pending(target):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "El super admin está pendiente de activación: debe activarse con su enlace"
        )

    if deactivating and target.is_active:
        # RN-049-2: siempre queda al menos un super_admin activo. Se bloquean todos los activos
        # dentro de la misma transacción para que la cuenta sea atómica.
        activos = await _lock_active_super_admin_ids(db)
        if not [uid for uid in activos if uid != target.id]:
            raise HTTPException(status.HTTP_409_CONFLICT, "Siempre debe quedar al menos un super_admin activo")

    old_values: dict = {}
    new_values: dict = {}
    if request.full_name is not None and request.full_name != target.full_name:
        old_values["full_name"], new_values["full_name"] = target.full_name, request.full_name
        target.full_name = request.full_name

    deactivated = reactivated = False
    if deactivating and target.is_active:
        target.is_active = False
        deactivated = True
    elif request.is_active is True and not target.is_active:
        target.is_active = True
        reactivated = True

    if new_values:
        await audit_user(db, target, "UPDATE", actor, old_values=old_values, new_values=new_values)
    if deactivated:
        await audit_user(db, target, "DEACTIVATE", actor)
        await revoke_all_sessions(target.id, redis)
    if reactivated:
        await audit_user(db, target, "REACTIVATE", actor)
    if not (new_values or deactivated or reactivated):
        await db.commit()

    await db.refresh(target)
    return UserResponse.model_validate(target)


async def force_super_admin_reset(
    user_id: str,
    actor: Actor,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> None:
    """Envía el email de reseteo y cierra las sesiones. Nunca se ve ni se fija la contraseña (L-5)."""
    target = await _get_super_admin(db, user_id)
    if target.is_protected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, PROTECTED_DETAIL)
    if is_pending(target):
        raise HTTPException(status.HTTP_409_CONFLICT, "El super admin está pendiente de activación")
    if not target.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "El super admin está desactivado")

    token = await issue_reset_token(target.id, redis)
    if not dispatch_reset_email(target.email, target.full_name, token):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No se pudo encolar el email de reseteo")
    await revoke_all_sessions(target.id, redis)
    await audit_user(db, target, "FORCE_PASSWORD_RESET", actor)
