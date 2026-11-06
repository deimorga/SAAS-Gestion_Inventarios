"""Gestión de usuarios de un tenant (RF-047, RF-048, RF-052).

Lo usan dos superficies con el mismo código: `/v1/users` (tenant_admin sobre su propio
tenant) y `/admin/tenants/{id}/users` (super_admin sobre cualquier tenant). Las reglas de
quién puede hacer qué viven en un solo sitio, `ensure_can_manage`, y se llaman antes de
tocar nada: ocultar un botón en el portal no protege si el endpoint acepta la petición.
"""
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, set_system_context
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user_management import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services import activation as activation_service
from app.services.activation import dispatch_activation_email, generate_activation_token
from app.services.audit import log_action
from app.services.password_reset import dispatch_reset_email, issue_reset_token
from app.services.sessions import revoke_all_sessions

logger = logging.getLogger(__name__)

# Quién puede asignar qué rol (RN-047-1, RN-048-1). Nadie asigna `super_admin` por aquí (RF-049).
ASSIGNABLE_ROLES: dict[str, set[str]] = {
    "super_admin": {"tenant_admin", "inventory_manager", "viewer"},
    "tenant_admin": {"inventory_manager", "viewer"},
}

EMAIL_TAKEN = "El email ya está registrado"


@dataclass
class Actor:
    """Quien ejecuta la acción: define los permisos y se anota en la auditoría."""

    user_id: str
    role: str  # "super_admin" | "tenant_admin"
    ip: str | None = None
    kind: Literal["user", "api_key"] = "user"

    def performed_by(self) -> dict:
        return {"type": self.kind, "id": self.user_id, "role": self.role}


# ── Estado y permisos ──────────────────────────────────────────────────────


def is_pending(user: User) -> bool:
    """Creado, aún sin fijar su contraseña con el enlace de activación."""
    return not user.is_active and user.must_change_password


def ensure_can_manage(actor: Actor, target: User, *, deactivating: bool = False) -> None:
    """Decide si `actor` puede modificar a `target`. Se llama antes de cualquier escritura."""
    if target.is_protected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cuenta raíz protegida")  # L-1, RN-049-5
    if actor.role == "tenant_admin":
        if target.role == "tenant_admin" and target.id != actor.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No puedes gestionar a otro tenant_admin")  # RN-048-2
        if deactivating and target.id == actor.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No puedes desactivarte a ti mismo")  # RN-048-3
    if target.role == "super_admin":
        # Los super_admins se gestionan en /admin/super-admins (RN-049-4)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")


async def email_exists(email: str) -> bool:
    """¿Hay un usuario con ese email en CUALQUIER tenant? (RN-052-1)

    La sesión del endpoint tiene el RLS de su tenant y no ve usuarios de otros, así que la
    comprobación va con una sesión de sistema. Solo responde sí/no: no devuelve datos.
    """
    async with AsyncSessionLocal() as session:
        await set_system_context(session)
        row = await session.execute(
            text("SELECT 1 FROM users WHERE lower(email) = :email LIMIT 1"), {"email": email.strip().lower()}
        )
        return row.first() is not None


async def audit_user(
    db: AsyncSession,
    user: User,
    action: str,
    actor: Actor,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    """Anota la acción en `audit_logs` del tenant del usuario afectado (RN-052-5).

    Nunca recibe contraseñas, hashes ni tokens. `log_action` hace commit: confirma también
    los cambios pendientes de la sesión.
    """
    await log_action(
        db,
        tenant_id=user.tenant_id,
        entity="users",
        entity_id=user.id,
        action=action,
        new_values=new_values or {},
        old_values=old_values,
        performed_by=actor.performed_by(),
        ip_address=actor.ip,
    )


async def _get_user(db: AsyncSession, user_id: str, tenant_id: str) -> User:
    user = (
        await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return user


# ── Casos de uso ───────────────────────────────────────────────────────────


async def create_user(
    request: UserCreate,
    tenant_id: str,
    actor: Actor,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> UserResponse:
    if request.role not in ASSIGNABLE_ROLES.get(actor.role, set()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Un {actor.role} no puede crear usuarios con rol '{request.role}'",
        )

    if await email_exists(request.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)

    user = User(
        id=str(uuid4()),
        tenant_id=tenant_id,
        email=request.email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        full_name=request.full_name,
        role=request.role,
        is_active=False,
        must_change_password=True,
        created_by=actor.user_id if actor.kind == "user" else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # Carrera entre dos altas con el mismo email: el índice único de la 016 es la garantía final
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN) from None

    await audit_user(db, user, "CREATE", actor, new_values={"email": user.email, "role": user.role})
    await db.refresh(user)

    token = await generate_activation_token(user.id, redis)
    dispatch_activation_email(
        to_email=user.email,
        full_name=user.full_name,
        token=token,
        template="account_activation",
    )
    return UserResponse.model_validate(user)


async def list_users(
    tenant_id: str,
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    status_filter: str | None = None,
    q: str | None = None,
) -> UserListResponse:
    # Los super_admins no aparecen aquí, ni siquiera en el tenant interno (RN-049-4)
    conditions = [User.tenant_id == tenant_id, User.role != "super_admin"]
    if status_filter == "active":
        conditions.append(User.is_active.is_(True))
    elif status_filter == "pending":
        conditions.append(User.is_active.is_(False))
        conditions.append(User.must_change_password.is_(True))
    elif status_filter == "disabled":
        conditions.append(User.is_active.is_(False))
        conditions.append(User.must_change_password.is_(False))
    if q and q.strip():
        needle = q.strip().lower()
        conditions.append(
            func.lower(User.email).contains(needle, autoescape=True)
            | func.lower(User.full_name).contains(needle, autoescape=True)
        )

    total = (await db.execute(select(func.count()).select_from(User).where(*conditions))).scalar_one()
    users = (
        await db.execute(
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
    )


async def update_user(
    user_id: str,
    tenant_id: str,
    request: UserUpdate,
    actor: Actor,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> UserResponse:
    user = await _get_user(db, user_id, tenant_id)
    ensure_can_manage(actor, user, deactivating=request.is_active is False)

    # Validar todo antes de modificar nada
    if request.role is not None and request.role != user.role:
        if user.id == actor.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No puedes cambiar tu propio rol")
        if request.role not in ASSIGNABLE_ROLES.get(actor.role, set()):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Un {actor.role} no puede asignar el rol '{request.role}'"
            )
    if request.is_active is True and is_pending(user):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El usuario está pendiente de activación: debe activarse con su enlace (reenvía la activación)",
        )

    old_values: dict = {}
    new_values: dict = {}
    if request.full_name is not None and request.full_name != user.full_name:
        old_values["full_name"], new_values["full_name"] = user.full_name, request.full_name
        user.full_name = request.full_name
    if request.role is not None and request.role != user.role:
        old_values["role"], new_values["role"] = user.role, request.role
        user.role = request.role

    deactivated = reactivated = False
    if request.is_active is False and user.is_active:
        user.is_active = False
        deactivated = True
    elif request.is_active is True and not user.is_active:
        user.is_active = True
        reactivated = True

    if new_values:
        await audit_user(db, user, "UPDATE", actor, old_values=old_values, new_values=new_values)
    if deactivated:
        await audit_user(db, user, "DEACTIVATE", actor)
        await revoke_all_sessions(user.id, redis)  # RF-051: cierra sus sesiones al momento
    if reactivated:
        await audit_user(db, user, "REACTIVATE", actor)
    if not (new_values or deactivated or reactivated):
        await db.commit()

    await db.refresh(user)
    return UserResponse.model_validate(user)


async def resend_activation_for(
    user_id: str,
    tenant_id: str,
    actor: Actor,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> None:
    """Reenvía la activación a un usuario pendiente (RF-047/048)."""
    user = await _get_user(db, user_id, tenant_id)
    ensure_can_manage(actor, user)
    await activation_service.resend_activation(user_id, tenant_id, db, redis)
    await audit_user(db, user, "RESEND_ACTIVATION", actor)


async def request_password_reset_for(
    user_id: str,
    tenant_id: str,
    actor: Actor,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> None:
    """Fuerza el reseteo: envía el email de reseteo y cierra las sesiones (RF-047/048, L-5).

    El administrador nunca ve ni fija la contraseña: solo dispara el email.
    """
    user = await _get_user(db, user_id, tenant_id)
    ensure_can_manage(actor, user)
    if is_pending(user):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "El usuario está pendiente de activación: reenvía la activación"
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "El usuario está desactivado")

    token = await issue_reset_token(user.id, redis)
    if not dispatch_reset_email(user.email, user.full_name, token):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No se pudo encolar el email de reseteo")
    await revoke_all_sessions(user.id, redis)
    await audit_user(db, user, "FORCE_PASSWORD_RESET", actor)
