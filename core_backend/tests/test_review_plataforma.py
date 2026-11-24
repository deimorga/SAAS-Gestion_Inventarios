"""
Revisión 2026-11-19 — R-06, R-07 y R-08 (aprovisionamiento por plataforma).

R-06: la key de plataforma veía y daba de baja sedes creadas desde el panel (`external_provider='panel'`).
R-07: si fallaba un paso posterior al alta del tenant (almacén, API key), el tenant quedaba a medias y el
      reintento con el mismo `external_id` respondía 409 sin key.
R-08: dos altas simultáneas con el mismo `external_id` terminaban en 500 (IntegrityError sin capturar).
"""
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MICRONUBA_TENANT_ID
from app.models.tenant import Tenant
from tests.conftest import _TestSession


def _sede_payload(**overrides) -> dict:
    suffix = uuid.uuid4().hex[:8]
    base = {
        "name": f"Sede Review {suffix}",
        "admin_email": f"sede-rev-{suffix}@tallerdemo.com",
        "admin_full_name": "Admin Sede Review",
        "external_id": f"shop_rev_{suffix}",
        "external_provider": "appits",
    }
    return {**base, **overrides}


async def _delete_tenant(tenant_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
        await session.commit()


async def _tenant_ids_by_external(provider: str, external_id: str) -> list[str]:
    async with _TestSession() as session:
        rows = await session.execute(
            text("SELECT id FROM tenants WHERE external_provider = :p AND external_id = :e"),
            {"p": provider, "e": external_id},
        )
        return [str(r[0]) for r in rows]


async def _users_with_email(email: str) -> int:
    async with _TestSession() as session:
        return (
            await session.execute(text("SELECT count(*) FROM users WHERE lower(email) = lower(:e)"), {"e": email})
        ).scalar_one()


async def _tenant_row(tenant_id: str):
    async with _TestSession() as session:
        return (
            await session.execute(text("SELECT is_active FROM tenants WHERE id = :id"), {"id": tenant_id})
        ).first()


@pytest_asyncio.fixture
async def platform_headers(client: AsyncClient, admin_auth_headers):
    resp = await client.post(
        f"/admin/tenants/{MICRONUBA_TENANT_ID}/api-keys",
        json={"name": f"key-rev-{uuid.uuid4().hex[:6]}", "scopes": ["PLATFORM"]},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    key = resp.json()
    yield {"Authorization": f"Bearer {key['key_secret']}"}
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM api_keys WHERE id = :id"), {"id": key["id"]})
        await session.commit()


# ── R-06: la key de plataforma no toca sedes del panel ─────────────────────

@pytest.mark.asyncio
async def test_r06_plataforma_no_ve_ni_da_de_baja_una_sede_del_panel(
    client: AsyncClient, platform_headers, admin_auth_headers, tenant_a
):
    suffix = uuid.uuid4().hex[:8]
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/sedes",
        json={"name": f"Sede Panel {suffix}", "admin_email": f"panel-{suffix}@tallerdemo.com",
              "admin_full_name": "Admin Panel"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    sede = resp.json()
    try:
        assert sede["external_provider"] == "panel"
        tid = sede["tenant_id"]

        assert (await client.get(f"/v1/platform/tenants/{tid}", headers=platform_headers)).status_code == 404
        assert (
            await client.get(f"/v1/platform/tenants/by-external/panel/{sede['external_id']}", headers=platform_headers)
        ).status_code == 404

        baja = await client.delete(f"/v1/platform/tenants/{tid}", headers=platform_headers)
        assert baja.status_code == 404
        assert (await _tenant_row(tid))[0] is True, "la sede del panel sigue activa"
    finally:
        await _delete_tenant(sede["tenant_id"])


@pytest.mark.asyncio
async def test_r06_plataforma_no_puede_crear_tenants_como_panel(client: AsyncClient, platform_headers):
    payload = _sede_payload(external_provider="panel")
    resp = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
    try:
        assert resp.status_code == 422, resp.text
    finally:
        for tid in await _tenant_ids_by_external("panel", payload["external_id"]):
            await _delete_tenant(tid)


# ── R-07: aprovisionamiento a medias ───────────────────────────────────────

async def _falla_al_crear_la_key(*args, **kwargs):
    raise RuntimeError("fallo simulado al crear la API key")


async def _sin_almacen(*args, **kwargs):
    return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "objetivo, reemplazo",
    [
        ("app.services.platform.create_api_key", _falla_al_crear_la_key),
        ("app.services.admin_tenant.provision_default_warehouse", _sin_almacen),
    ],
    ids=["falla_la_key", "falla_el_almacen"],
)
async def test_r07_si_falla_un_paso_no_queda_nada_y_el_reintento_completa(
    client: AsyncClient, platform_headers, email_spy, monkeypatch, objetivo, reemplazo
):
    payload = _sede_payload()
    creados: list[str] = []
    try:
        with monkeypatch.context() as m:
            m.setattr(objetivo, reemplazo)
            try:
                resp = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
                status_code = resp.status_code
            except RuntimeError:
                status_code = None  # la excepción se escapó sin manejar
        creados += await _tenant_ids_by_external("appits", payload["external_id"])

        assert status_code == 500
        assert creados == [], "no queda un tenant a medias"
        assert await _users_with_email(payload["admin_email"]) == 0, "ni su admin"
        assert email_spy.of("tenant_created") == [], "ni se le manda un enlace de activación que no sirve"

        retry = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
        assert retry.status_code == 201, retry.text
        creados.append(retry.json()["tenant_id"])
        assert retry.json()["api_key"]["key_secret"].startswith("mk_secret_")
        assert retry.json()["warehouse"]["zones"]
        assert len(email_spy.of("tenant_created")) == 1
    finally:
        for tid in set(creados) | set(await _tenant_ids_by_external("appits", payload["external_id"])):
            await _delete_tenant(tid)


# ── R-08: altas simultáneas ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_r08_dos_altas_simultaneas_con_el_mismo_external_id_dan_201_y_409(
    client: AsyncClient, platform_headers, monkeypatch
):
    external_id = f"shop_rev_{uuid.uuid4().hex[:8]}"
    payloads = [_sede_payload(external_id=external_id) for _ in range(2)]

    # Carrera determinista: las dos altas pasan las comprobaciones previas y esperan juntas
    # antes del commit, que es lo que pasa cuando llegan a la vez.
    barrera = asyncio.Barrier(2)
    commit_original = AsyncSession.commit

    async def commit_sincronizado(self):
        if any(isinstance(o, Tenant) and o.external_id == external_id for o in self.new):
            await asyncio.wait_for(barrera.wait(), timeout=10)
        return await commit_original(self)

    monkeypatch.setattr(AsyncSession, "commit", commit_sincronizado)
    try:
        resps = await asyncio.gather(
            *(client.post("/v1/platform/tenants", json=p, headers=platform_headers) for p in payloads),
            return_exceptions=True,
        )
        codes = sorted((r.status_code if not isinstance(r, BaseException) else repr(r) for r in resps), key=str)
        assert codes == [201, 409], codes
        ganador = next(r for r in resps if r.status_code == 201).json()["tenant_id"]
        perdedor = next(r for r in resps if r.status_code == 409).json()["detail"]
        assert f"tenant_id={ganador}" in perdedor, "como el 409 de un reintento: dice qué tenant usar"
    finally:
        for tid in await _tenant_ids_by_external("appits", external_id):
            await _delete_tenant(tid)


# ── Ajustes tras la revisión independiente del grupo ───────────────────────

@pytest.mark.asyncio
async def test_r08_el_mismo_alta_enviada_dos_veces_a_la_vez_responde_409_con_el_tenant_existente(
    client: AsyncClient, platform_headers, monkeypatch
):
    """Appits reenvía el MISMO POST (mismo nombre → mismo slug): choca primero el índice del slug, no el
    del external_id, y aun así el 409 debe decir qué tenant usar."""
    payload = _sede_payload()
    barrera = asyncio.Barrier(2)
    commit_original = AsyncSession.commit

    async def commit_sincronizado(self):
        if any(isinstance(o, Tenant) and o.external_id == payload["external_id"] for o in self.new):
            await asyncio.wait_for(barrera.wait(), timeout=10)
        return await commit_original(self)

    monkeypatch.setattr(AsyncSession, "commit", commit_sincronizado)
    try:
        resps = await asyncio.gather(
            *(client.post("/v1/platform/tenants", json=payload, headers=platform_headers) for _ in range(2)),
            return_exceptions=True,
        )
        codes = sorted((r.status_code if not isinstance(r, BaseException) else repr(r) for r in resps), key=str)
        assert codes == [201, 409], codes
        ganador = next(r for r in resps if r.status_code == 201).json()["tenant_id"]
        perdedor = next(r for r in resps if r.status_code == 409).json()["detail"]
        assert f"tenant_id={ganador}" in perdedor
    finally:
        for tid in await _tenant_ids_by_external("appits", payload["external_id"]):
            await _delete_tenant(tid)


@pytest.mark.asyncio
async def test_r07_si_falla_el_ultimo_paso_se_deshace_aunque_ya_haya_key_y_almacen(
    client: AsyncClient, platform_headers, email_spy, monkeypatch
):
    """Falla la auditoría, que va DESPUÉS de crear la key y el almacén: el borrado en cascada tiene que
    llevarse también esas filas (con RLS forzado) y dejar el external_id libre."""
    payload = _sede_payload()

    async def falla(*args, **kwargs):
        raise RuntimeError("fallo simulado en la auditoría")

    try:
        with monkeypatch.context() as m:
            m.setattr("app.services.platform.log_action", falla)
            resp = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
        assert resp.status_code == 500
        assert await _tenant_ids_by_external("appits", payload["external_id"]) == []
        assert email_spy.of("tenant_created") == []

        retry = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
        assert retry.status_code == 201, retry.text
    finally:
        for tid in await _tenant_ids_by_external("appits", payload["external_id"]):
            await _delete_tenant(tid)


@pytest.mark.asyncio
async def test_r07_si_no_se_puede_deshacer_el_500_no_dice_que_no_se_creo_nada(
    client: AsyncClient, platform_headers, monkeypatch
):
    payload = _sede_payload()

    async def falla_la_key(*args, **kwargs):
        raise RuntimeError("fallo simulado al crear la API key")

    def falla_el_borrado(*args, **kwargs):
        raise RuntimeError("fallo simulado al borrar")

    try:
        with monkeypatch.context() as m:
            m.setattr("app.services.platform.create_api_key", falla_la_key)
            m.setattr("app.services.platform.delete", falla_el_borrado)
            resp = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "no se creó nada" not in detail, "el tenant quedó a medias: no se puede prometer eso"
        assert "tenant_id=" in detail
    finally:
        for tid in await _tenant_ids_by_external("appits", payload["external_id"]):
            await _delete_tenant(tid)


@pytest.mark.asyncio
async def test_r07_si_falla_solo_el_aviso_al_admin_la_sede_se_devuelve_completa(
    client: AsyncClient, platform_headers, monkeypatch
):
    """El enlace de activación (Redis/Celery) no puede tirar una sede que ya está completa: se perdería la
    key, que solo se devuelve una vez."""
    payload = _sede_payload()

    async def falla(*args, **kwargs):
        raise RuntimeError("Redis caído")

    created = []
    try:
        with monkeypatch.context() as m:
            m.setattr("app.services.platform.notify_tenant_admin", falla)
            resp = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
        assert resp.status_code == 201, resp.text
        created.append(resp.json()["tenant_id"])
        assert resp.json()["api_key"]["key_secret"].startswith("mk_secret_")
    finally:
        for tid in set(created) | set(await _tenant_ids_by_external("appits", payload["external_id"])):
            await _delete_tenant(tid)
