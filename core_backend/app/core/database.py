import logging
from contextvars import ContextVar
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session as SyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

# Sentinel que activa el bypass de RLS en las políticas de PostgreSQL.
# Debe coincidir con el valor usado en la migración 012.
SUPER_ADMIN_SENTINEL = "__super_admin__"

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Almacena el tenant_id activo por request (sin cruzar entre coroutines)
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)


# Clave bajo la que cada sesión recuerda su contexto RLS en `Session.info`
_RLS_CONTEXT_KEY = "rls_context"

_SET_CONTEXT_SQL = text("SELECT set_config('app.current_tenant', :value, true)")


def _session_info(session) -> dict:
    """`info` de la sesión, sea AsyncSession o Session síncrona."""
    return getattr(session, "sync_session", session).info


@event.listens_for(SyncSession, "after_begin")
def _reapply_rls_context(session, transaction, connection) -> None:
    """Reinstala `app.current_tenant` al empezar cada transacción.

    `set_config(..., true)` vive solo mientras dura la transacción: al hacer
    commit, PostgreSQL lo descarta. Cualquier lectura posterior en la misma
    sesión —un `refresh()` tras insertar una fila, o un segundo commit— saldría
    sin tenant y las políticas RLS la dejarían a ciegas. Con un rol superusuario
    el defecto era invisible porque RLS no llegaba a aplicarse.
    """
    value = session.info.get(_RLS_CONTEXT_KEY)
    if value is not None:
        connection.execute(_SET_CONTEXT_SQL, {"value": value})


async def _apply_rls_context(session: AsyncSession, value: str) -> None:
    # Se recuerda en `info` para que `_reapply_rls_context` lo reinstale en las
    # transacciones siguientes, y se aplica ya para la actual.
    _session_info(session)[_RLS_CONTEXT_KEY] = value
    await session.execute(_SET_CONTEXT_SQL, {"value": value})


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Fija el tenant de la sesión para que apliquen las políticas RLS."""
    await _apply_rls_context(session, tenant_id)


async def set_system_context(session: AsyncSession) -> None:
    """Activa el bypass de RLS para procesos legítimamente cross-tenant.

    Reservado para: resolución de credenciales antes de conocer el tenant (login,
    API key, token de activación) y tareas de sistema que barren todos los tenants
    (expiración de API keys, rotación). Nunca para atender datos de un tenant.
    """
    await _apply_rls_context(session, SUPER_ADMIN_SENTINEL)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Sesión sin contexto de tenant — solo para endpoints públicos (login)."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_system_db() -> AsyncGenerator[AsyncSession, None]:
    """Sesión con bypass de RLS — ver `set_system_context`."""
    async with AsyncSessionLocal() as session:
        await set_system_context(session)
        yield session


async def get_tenant_db(tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Sesión con RLS activo para el tenant indicado."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        yield session


async def assert_rls_enforced() -> None:
    """Verifica que el rol de conexión esté sujeto a RLS. Aborta el arranque si no.

    Un rol con `rolsuper` o `rolbypassrls` ignora todas las políticas, incluidas
    las declaradas FORCE. La app arrancaría con normalidad y el aislamiento entre
    tenants sería una ilusión: es un fallo silencioso, por eso se comprueba aquí
    y no se deja al despliegue.

    En desarrollo y en tests solo se avisa, porque la suite necesita un rol con
    privilegios para montar y limpiar los fixtures.
    """
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                text(
                    "SELECT current_user AS role, rolsuper OR rolbypassrls AS puede_saltarse_rls "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            )
        ).one_or_none()

    if row is None or not row.puede_saltarse_rls:
        return

    mensaje = (
        f"El rol de base de datos '{row.role}' puede saltarse RLS "
        f"(superuser o BYPASSRLS): el aislamiento entre tenants NO está garantizado. "
        f"Cree el rol restringido con infra/postgres/create_app_role.sh y apunte "
        f"DATABASE_URL a él, dejando MIGRATION_DATABASE_URL para Alembic."
    )

    if settings.APP_ENV in ("development", "test"):
        logger.warning("%s (tolerado en APP_ENV=%s)", mensaje, settings.APP_ENV)
        return

    raise RuntimeError(mensaje)
