"""
El rol de conexión debe estar sujeto a RLS.

Contexto: la imagen oficial de PostgreSQL crea POSTGRES_USER como superusuario de
bootstrap, y un superusuario ignora las políticas RLS incluso declaradas FORCE.
Producción y staging corrían así: las 26 políticas de aislamiento por tenant
estaban inertes y nada lo delataba. `assert_rls_enforced` convierte ese fallo
silencioso en un arranque abortado.

Complementa a test_rls_isolation.py: allí se comprueba que las políticas aíslan;
aquí, que la app no pueda saltárselas ni arrancar mal configurada.
"""
import pytest
from sqlalchemy import text

from app.core import database as db_module
from app.core.database import assert_rls_enforced, set_system_context, set_tenant_context
from tests.conftest import _RlsSession, _TestSession


# ── El guard de arranque ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_guard_aborta_en_produccion_con_rol_privilegiado(monkeypatch):
    """Con un rol que ignora RLS y APP_ENV=production, la app no debe arrancar."""
    monkeypatch.setattr(db_module.settings, "APP_ENV", "production")

    with pytest.raises(RuntimeError) as exc:
        await assert_rls_enforced()

    mensaje = str(exc.value)
    assert "puede saltarse RLS" in mensaje
    assert "create_app_role.sh" in mensaje, "el error debe decir cómo arreglarlo"


@pytest.mark.asyncio
async def test_guard_solo_avisa_en_desarrollo(monkeypatch):
    """En desarrollo se tolera: la suite necesita un rol con privilegios."""
    monkeypatch.setattr(db_module.settings, "APP_ENV", "development")
    await assert_rls_enforced()  # no debe lanzar


@pytest.mark.asyncio
async def test_guard_pasa_con_rol_restringido(monkeypatch):
    """Con el rol de aplicación real, el guard aprueba incluso en producción."""
    monkeypatch.setattr(db_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(db_module, "AsyncSessionLocal", _RlsSession)

    await assert_rls_enforced()  # no debe lanzar


@pytest.mark.asyncio
async def test_rol_de_aplicacion_no_puede_ignorar_rls():
    """El rol con el que corre la app no tiene superuser ni BYPASSRLS."""
    async with _RlsSession() as session:
        row = (
            await session.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            )
        ).one()

    assert row.rolsuper is False
    assert row.rolbypassrls is False


# ── El sentinel bajo un rol sin privilegios ────────────────────────────────


@pytest.mark.asyncio
async def test_sin_contexto_el_rol_restringido_no_ve_usuarios(tenant_a, user_a):
    """Sin `app.current_tenant`, las políticas no dejan ver nada.

    Es la razón por la que login y la búsqueda de API key necesitan el sentinel:
    deben localizar al usuario antes de saber su tenant.
    """
    async with _RlsSession() as session:
        count = (
            await session.execute(text("SELECT count(*) FROM users"))
        ).scalar_one()

    assert count == 0


@pytest.mark.asyncio
async def test_el_sentinel_permite_resolver_credenciales(tenant_a, user_a):
    """Con el sentinel, el rol restringido sí encuentra al usuario por email."""
    async with _RlsSession() as session:
        await set_system_context(session)
        found = (
            await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": user_a["email"]},
            )
        ).scalar_one_or_none()

    assert found == user_a["id"]


@pytest.mark.asyncio
async def test_el_contexto_de_tenant_acota_lo_visible(tenant_a, tenant_b, user_a, user_b):
    """Fijado un tenant, el rol restringido solo ve a los suyos."""
    async with _RlsSession() as session:
        await set_tenant_context(session, tenant_a["id"])
        visibles = (
            await session.execute(text("SELECT id FROM users"))
        ).scalars().all()

    assert user_a["id"] in visibles
    assert user_b["id"] not in visibles


# ── Las api_keys, que es donde estalló ─────────────────────────────────────


@pytest.mark.asyncio
async def test_busqueda_de_api_key_requiere_sentinel(tenant_a, user_a):
    """Sin sentinel no se encuentra la key; con él, sí.

    Reproduce en pequeño el 401 de producción: la búsqueda de la API key ocurre
    antes de conocer el tenant, así que necesita el bypass explícito.
    """
    key_id = "mk_live_test_rls"
    key_hash = "hash-de-prueba-rls"

    async with _TestSession() as session:
        await session.execute(
            text(
                "INSERT INTO api_keys "
                "(id, tenant_id, key_id, key_hash, name, scopes, is_active, created_at) "
                "VALUES (gen_random_uuid(), :tid, :kid, :kh, 'RLS probe', "
                "        '[\"READ_INVENTORY\"]', true, now())"
            ),
            {"tid": tenant_a["id"], "kid": key_id, "kh": key_hash},
        )
        await session.commit()

    try:
        async with _RlsSession() as session:
            sin_contexto = (
                await session.execute(
                    text("SELECT count(*) FROM api_keys WHERE key_hash = :kh"),
                    {"kh": key_hash},
                )
            ).scalar_one()

            await set_system_context(session)
            con_sentinel = (
                await session.execute(
                    text("SELECT count(*) FROM api_keys WHERE key_hash = :kh"),
                    {"kh": key_hash},
                )
            ).scalar_one()

        assert sin_contexto == 0
        assert con_sentinel == 1
    finally:
        async with _TestSession() as session:
            await session.execute(
                text("DELETE FROM api_keys WHERE key_hash = :kh"), {"kh": key_hash}
            )
            await session.commit()
