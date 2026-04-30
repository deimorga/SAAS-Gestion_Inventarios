"""
Fixtures de prueba para MicroNuba Inventory SaaS.

Estrategia: todos los tests comparten un único event loop (session scope).
Se usa NullPool para evitar contaminación de conexiones entre tests.
Cada test crea tenants/usuarios únicos y los elimina en teardown.
"""
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import hash_password
from app.main import app

# Engine sin pool para tests — cada operación abre/cierra su propia conexión
_test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
_TestSession = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)

# Engine con usuario sin BYPASSRLS para validar RLS de PostgreSQL directamente
_RLS_URL = settings.DATABASE_URL.replace(
    settings.DATABASE_URL.split("//")[1].split("@")[0],
    "inventory_app:apppassword123",
)
_rls_engine = create_async_engine(_RLS_URL, poolclass=NullPool)
_RlsSession = async_sessionmaker(_rls_engine, class_=AsyncSession, expire_on_commit=False)


# ── Event loop único para toda la sesión de tests ──────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Un único event loop compartido por todos los tests y fixtures de sesión."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Helpers ────────────────────────────────────────────────────────────────

def uid() -> str:
    return str(uuid.uuid4())


async def _create_tenant(session: AsyncSession, name: str, tier: str = "PROFESSIONAL") -> dict:
    tid = uid()
    slug = name.lower().replace(" ", "-") + "-" + tid[:8]
    await session.execute(
        text(
            "INSERT INTO tenants (id, name, slug, subscription_tier, config, is_active, created_at, updated_at) "
            "VALUES (:id, :name, :slug, :tier, '{}', true, now(), now())"
        ),
        {"id": tid, "name": name, "slug": slug, "tier": tier},
    )
    await session.commit()
    return {"id": tid, "name": name, "tier": tier}


async def _create_user(session: AsyncSession, tenant_id: str, email: str, role: str = "tenant_admin") -> dict:
    uid_ = uid()
    await session.execute(
        text(
            "INSERT INTO users (id, tenant_id, email, password_hash, full_name, role, is_active, created_at) "
            "VALUES (:id, :tid, :email, :pw, 'Test User', :role, true, now())"
        ),
        {"id": uid_, "tid": tenant_id, "email": email, "pw": hash_password("Password123!"), "role": role},
    )
    await session.commit()
    return {"id": uid_, "email": email, "role": role, "tenant_id": tenant_id}


async def _delete_tenant(session: AsyncSession, tenant_id: str) -> None:
    await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
    await session.commit()


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db():
    async with _TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def rls_db():
    """Sesión conectada como inventory_app (no superuser) — RLS se aplica realmente."""
    async with _RlsSession() as session:
        yield session


@pytest_asyncio.fixture
async def tenant_a(db):
    t = await _create_tenant(db, "Tenant Alpha")
    yield t
    await _delete_tenant(db, t["id"])


@pytest_asyncio.fixture
async def tenant_b(db):
    t = await _create_tenant(db, "Tenant Beta")
    yield t
    await _delete_tenant(db, t["id"])


@pytest_asyncio.fixture
async def user_a(db, tenant_a):
    return await _create_user(db, tenant_a["id"], f"admin-{tenant_a['id'][:8]}@alpha.com")


@pytest_asyncio.fixture
async def user_b(db, tenant_b):
    return await _create_user(db, tenant_b["id"], f"admin-{tenant_b['id'][:8]}@beta.com")


@pytest_asyncio.fixture
async def auth_headers_a(client, user_a):
    resp = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    assert resp.status_code == 200, f"Login A falló: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth_headers_b(client, user_b):
    resp = await client.post("/v1/auth/login", json={"email": user_b["email"], "password": "Password123!"})
    assert resp.status_code == 200, f"Login B falló: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Sprint 6: Super admin helpers ──────────────────────────────────────────

MICRONUBA_TENANT_ID = "00000000-0000-0000-0000-000000000001"
_SA_PASSWORD = "AdminPass123!XYZ"


async def _insert_super_admin(email: str) -> str:
    sa_uid = uid()
    async with _TestSession() as session:
        await session.execute(
            text(
                "INSERT INTO users "
                "(id, tenant_id, email, password_hash, full_name, role, "
                " is_active, must_change_password, created_at) "
                "VALUES (:id, :tid, :email, :pw, 'Super Admin', 'super_admin', "
                "        true, false, now())"
            ),
            {
                "id": sa_uid,
                "tid": MICRONUBA_TENANT_ID,
                "email": email,
                "pw": hash_password(_SA_PASSWORD),
            },
        )
        await session.commit()
    return sa_uid


async def _delete_user_by_id(user_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await session.commit()


@pytest_asyncio.fixture
async def super_admin_user():
    """Super admin pre-creado en DB; se elimina tras cada test."""
    email = f"sa-{uid()[:8]}@micronuba.com"
    sa_uid = await _insert_super_admin(email)
    yield {"id": sa_uid, "email": email, "password": _SA_PASSWORD}
    await _delete_user_by_id(sa_uid)


@pytest_asyncio.fixture
async def admin_auth_headers(client, super_admin_user):
    """Headers JWT de super_admin listos para usar en endpoints /admin/*."""
    resp = await client.post(
        "/admin/auth/login",
        json={"email": super_admin_user["email"], "password": super_admin_user["password"]},
    )
    assert resp.status_code == 200, f"Admin login falló: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Sprint 2: Warehouse + Inventory helpers ────────────────────────────────


async def _create_warehouse(session: AsyncSession, tenant_id: str, code: str, is_virtual: bool = False) -> dict:
    wid = uid()
    await session.execute(
        text(
            "INSERT INTO warehouses (id, tenant_id, code, name, is_virtual, is_active, timezone, created_at, updated_at) "
            "VALUES (:id, :tid, :code, :name, :virt, true, 'UTC', now(), now())"
        ),
        {"id": wid, "tid": tenant_id, "code": code, "name": f"Warehouse {code}", "virt": is_virtual},
    )
    await session.commit()
    return {"id": wid, "tenant_id": tenant_id, "code": code, "is_virtual": is_virtual}


async def _create_zone(session: AsyncSession, tenant_id: str, warehouse_id: str, code: str, zone_type: str = "STORAGE") -> dict:
    zid = uid()
    await session.execute(
        text(
            "INSERT INTO zones (id, tenant_id, warehouse_id, code, name, zone_type, path, is_active, created_at) "
            "VALUES (:id, :tid, :wid, :code, :name, :zt, :path, true, now())"
        ),
        {"id": zid, "tid": tenant_id, "wid": warehouse_id, "code": code, "name": f"Zone {code}", "zt": zone_type, "path": code},
    )
    await session.commit()
    return {"id": zid, "tenant_id": tenant_id, "warehouse_id": warehouse_id, "code": code, "zone_type": zone_type}


async def _create_product_simple(session: AsyncSession, tenant_id: str, sku: str) -> dict:
    pid = uid()
    await session.execute(
        text(
            "INSERT INTO products (id, tenant_id, sku, name, base_uom, current_cpp, reorder_point, "
            "track_serials, track_lots, track_expiry, is_kit, is_active, low_stock_alert_enabled, created_at, updated_at) "
            "VALUES (:id, :tid, :sku, :name, 'UNIT', 0, 0, false, false, false, false, true, true, now(), now())"
        ),
        {"id": pid, "tid": tenant_id, "sku": sku, "name": f"Product {sku}"},
    )
    await session.commit()
    return {"id": pid, "tenant_id": tenant_id, "sku": sku}


@pytest_asyncio.fixture
async def warehouse_a(db, tenant_a):
    wh = await _create_warehouse(db, tenant_a["id"], "WH-A-01")
    yield wh
    await db.execute(text("DELETE FROM warehouses WHERE id = :id"), {"id": wh["id"]})
    await db.commit()


@pytest_asyncio.fixture
async def warehouse_b(db, tenant_b):
    wh = await _create_warehouse(db, tenant_b["id"], "WH-B-01")
    yield wh
    await db.execute(text("DELETE FROM warehouses WHERE id = :id"), {"id": wh["id"]})
    await db.commit()


@pytest_asyncio.fixture
async def zone_a(db, warehouse_a):
    return await _create_zone(db, warehouse_a["tenant_id"], warehouse_a["id"], "ZONE-A-01")


@pytest_asyncio.fixture
async def product_a(db, tenant_a):
    return await _create_product_simple(db, tenant_a["id"], f"SKU-{uid()[:8]}")
