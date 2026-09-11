"""
Tests de `/v1/platform/*` — aprovisionamiento de sedes desde una plataforma externa (Appits).

  POST   /v1/platform/tenants                                 tenant + almacén + API key en una llamada
  GET    /v1/platform/tenants/{id}
  GET    /v1/platform/tenants/by-external/{provider}/{external_id}
  DELETE /v1/platform/tenants/{id}                             baja lógica + revocación de keys

Y los límites de la credencial de plataforma:
  - solo API key del tenant interno con scope PLATFORM
  - PLATFORM no se puede emitir en otro tenant
  - una key PLATFORM no lee datos de ningún tenant
  - la key de la sede no puede llevar ADMIN ni PLATFORM
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import MICRONUBA_TENANT_ID
from tests.conftest import _TestSession


# ── Helpers ────────────────────────────────────────────────────────────────

def _sede_payload(**overrides) -> dict:
    suffix = uuid.uuid4().hex[:8]
    base = {
        "name": f"Sede Norte {suffix}",
        "tax_id": "900123456-7",
        "admin_email": f"sede-{suffix}@tallerdemo.com",
        "admin_full_name": "Admin Sede Norte",
        "external_id": f"shop_{suffix}",
        "external_provider": "appits",
    }
    return {**base, **overrides}


async def _delete_tenant(tenant_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
        await session.commit()


async def _delete_api_key(key_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM api_keys WHERE id = :id"), {"id": key_id})
        await session.commit()


async def _mint_key(client: AsyncClient, admin_headers: dict, tenant_id: str, scopes: list[str]) -> dict:
    resp = await client.post(
        f"/admin/tenants/{tenant_id}/api-keys",
        json={"name": f"key-{uuid.uuid4().hex[:6]}", "scopes": scopes},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def platform_headers(client: AsyncClient, admin_auth_headers):
    """API key PLATFORM del tenant interno, emitida por un super_admin."""
    key = await _mint_key(client, admin_auth_headers, MICRONUBA_TENANT_ID, ["PLATFORM"])
    yield {"Authorization": f"Bearer {key['key_secret']}"}
    await _delete_api_key(key["id"])


# ── Alta de sede ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provisionar_sede_devuelve_tenant_almacen_y_key(client: AsyncClient, platform_headers):
    """201: una llamada crea tenant aislado + almacén con zonas + API key operativa."""
    payload = _sede_payload()
    resp = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()

    try:
        assert body["external_id"] == payload["external_id"]
        assert body["external_provider"] == "appits"
        assert body["admin_email"] == payload["admin_email"]

        wh = body["warehouse"]
        assert wh["code"] == "PRINCIPAL"
        assert {z["zone_type"] for z in wh["zones"]} >= {"RECEIVING", "DISPATCH", "QUARANTINE"}

        key = body["api_key"]
        assert key["key_secret"].startswith("mk_secret_")
        assert "ADMIN" not in key["scopes"] and "PLATFORM" not in key["scopes"]
        assert "WRITE_INVENTORY" in key["scopes"]

        # La key de la sede opera sobre SU tenant: ve su almacén y nada más
        sede_headers = {"Authorization": f"Bearer {key['key_secret']}"}
        whs = await client.get("/v1/warehouses", headers=sede_headers)
        assert whs.status_code == 200, whs.text
        ids = {w["id"] for w in whs.json()["data"]}
        assert ids == {wh["id"]}
    finally:
        await _delete_tenant(body["tenant_id"])


@pytest.mark.asyncio
async def test_provisionar_sede_respeta_almacen_y_padre(client: AsyncClient, platform_headers, tenant_a):
    """201: acepta código/nombre de almacén propios y referencia al taller principal."""
    payload = _sede_payload(
        parent_tenant_id=tenant_a["id"],
        warehouse={"code": "SEDE-NORTE", "name": "Bodega Norte", "location_address": "Calle 80 # 45-23"},
    )
    resp = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    try:
        assert body["parent_tenant_id"] == tenant_a["id"]
        assert body["warehouse"]["code"] == "SEDE-NORTE"
        assert body["warehouse"]["name"] == "Bodega Norte"
    finally:
        await _delete_tenant(body["tenant_id"])


@pytest.mark.asyncio
async def test_provisionar_sede_external_id_duplicado(client: AsyncClient, platform_headers):
    """409: el mismo external_id no crea un segundo tenant y el detail trae el existente."""
    payload = _sede_payload()
    first = await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)
    assert first.status_code == 201, first.text
    tenant_id = first.json()["tenant_id"]
    try:
        again = await client.post(
            "/v1/platform/tenants",
            json={**payload, "admin_email": f"otro-{uuid.uuid4().hex[:6]}@tallerdemo.com"},
            headers=platform_headers,
        )
        assert again.status_code == 409, again.text
        assert tenant_id in again.json()["detail"]
    finally:
        await _delete_tenant(tenant_id)


@pytest.mark.asyncio
async def test_provisionar_sede_padre_inexistente(client: AsyncClient, platform_headers):
    """404: parent_tenant_id debe existir."""
    resp = await client.post(
        "/v1/platform/tenants",
        json=_sede_payload(parent_tenant_id=str(uuid.uuid4())),
        headers=platform_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_key_de_sede_no_admite_admin_ni_platform(client: AsyncClient, platform_headers):
    """422: la key que recibe la sede nunca puede ser ADMIN ni PLATFORM."""
    for scope in ("ADMIN", "PLATFORM"):
        resp = await client.post(
            "/v1/platform/tenants",
            json=_sede_payload(api_key_scopes=["READ_CATALOG", scope]),
            headers=platform_headers,
        )
        assert resp.status_code == 422, f"{scope}: {resp.text}"


# ── Consulta ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consultar_sede_por_id_y_por_external(client: AsyncClient, platform_headers):
    """200: la sede se encuentra por tenant_id y por (provider, external_id), con sus almacenes."""
    payload = _sede_payload()
    created = (await client.post("/v1/platform/tenants", json=payload, headers=platform_headers)).json()
    tenant_id = created["tenant_id"]
    try:
        by_id = await client.get(f"/v1/platform/tenants/{tenant_id}", headers=platform_headers)
        assert by_id.status_code == 200, by_id.text
        info = by_id.json()
        assert info["external_id"] == payload["external_id"]
        assert info["is_active"] is True
        assert [w["code"] for w in info["warehouses"]] == ["PRINCIPAL"]

        by_ext = await client.get(
            f"/v1/platform/tenants/by-external/appits/{payload['external_id']}",
            headers=platform_headers,
        )
        assert by_ext.status_code == 200
        assert by_ext.json()["tenant_id"] == tenant_id
    finally:
        await _delete_tenant(tenant_id)


@pytest.mark.asyncio
async def test_plataforma_no_ve_tenants_creados_a_mano(client: AsyncClient, platform_headers, tenant_a):
    """404: un tenant sin external_provider no existe para la plataforma."""
    resp = await client.get(f"/v1/platform/tenants/{tenant_a['id']}", headers=platform_headers)
    assert resp.status_code == 404


# ── Baja ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dar_de_baja_sede_suspende_y_revoca_keys(client: AsyncClient, platform_headers):
    """200: la sede queda inactiva y su API key deja de autenticar."""
    created = (await client.post("/v1/platform/tenants", json=_sede_payload(), headers=platform_headers)).json()
    tenant_id = created["tenant_id"]
    sede_headers = {"Authorization": f"Bearer {created['api_key']['key_secret']}"}
    try:
        assert (await client.get("/v1/warehouses", headers=sede_headers)).status_code == 200

        resp = await client.delete(f"/v1/platform/tenants/{tenant_id}", headers=platform_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"tenant_id": tenant_id, "is_active": False, "api_keys_revoked": 1}

        assert (await client.get("/v1/warehouses", headers=sede_headers)).status_code == 401

        info = await client.get(f"/v1/platform/tenants/{tenant_id}", headers=platform_headers)
        assert info.json()["is_active"] is False
    finally:
        await _delete_tenant(tenant_id)


# ── Límites de la credencial de plataforma ─────────────────────────────────

@pytest.mark.asyncio
async def test_platform_exige_scope_platform(client: AsyncClient, admin_auth_headers):
    """403: una key del tenant interno sin PLATFORM no aprovisiona."""
    key = await _mint_key(client, admin_auth_headers, MICRONUBA_TENANT_ID, ["ADMIN"])
    try:
        resp = await client.post(
            "/v1/platform/tenants",
            json=_sede_payload(),
            headers={"Authorization": f"Bearer {key['key_secret']}"},
        )
        assert resp.status_code == 403
    finally:
        await _delete_api_key(key["id"])


@pytest.mark.asyncio
async def test_platform_no_se_emite_fuera_del_tenant_interno(client: AsyncClient, admin_auth_headers, tenant_a):
    """403: ni un super_admin puede emitir PLATFORM en un tenant de cliente."""
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/api-keys",
        json={"name": "intento", "scopes": ["PLATFORM"]},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_platform_rechaza_jwt_de_super_admin(client: AsyncClient, admin_auth_headers):
    """403: el JWT humano de super_admin no sirve; la plataforma usa API key."""
    resp = await client.post("/v1/platform/tenants", json=_sede_payload(), headers=admin_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_key_platform_no_lee_datos_de_tenant(client: AsyncClient, platform_headers):
    """403: PLATFORM no otorga ningún rol efectivo sobre datos."""
    for path in ("/v1/products", "/v1/warehouses", "/v1/stock/balances"):
        resp = await client.get(path, headers=platform_headers)
        assert resp.status_code == 403, f"{path}: {resp.status_code}"
