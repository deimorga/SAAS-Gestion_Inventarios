from contextvars import ContextVar
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Sesión sin contexto de tenant — solo para endpoints públicos (login)."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_tenant_db(tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Sesión con RLS activo para el tenant indicado."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": tenant_id},
        )
        yield session
