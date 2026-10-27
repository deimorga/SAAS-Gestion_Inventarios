"""
Tests del límite de intentos fallidos de login (/v1/auth/login y /admin/auth/login).

Cada test usa su propia IP en X-Forwarded-For para no compartir contadores; el
cliente ASGI conecta desde 127.0.0.1, que aquí se declara proxy de confianza.
"""
import uuid

import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services.login_throttle import MAX_FAILURES_PER_ACCOUNT, MAX_FAILURES_PER_IP


@pytest.fixture(autouse=True)
def _cliente_de_tests_es_proxy_de_confianza(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOSTS", "127.0.0.1")


def _ip() -> dict[str, str]:
    n = uuid.uuid4().int
    return {"X-Forwarded-For": f"10.{n % 250}.{(n >> 8) % 250}.{(n >> 16) % 250}"}


async def _login(client: AsyncClient, email: str, password: str, headers: dict, ruta: str = "/v1/auth/login"):
    return await client.post(ruta, json={"email": email, "password": password}, headers=headers)


@pytest.mark.asyncio
async def test_bloquea_la_cuenta_tras_5_fallos_aunque_luego_acierte(client: AsyncClient, user_a):
    ip = _ip()
    for _ in range(MAX_FAILURES_PER_ACCOUNT):
        assert (await _login(client, user_a["email"], "Incorrecta1!", ip)).status_code == 401

    resp = await _login(client, user_a["email"], "Password123!", ip)
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0
    assert "intentos fallidos" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_el_bloqueo_no_alcanza_al_dueno_desde_otra_ip(client: AsyncClient, user_a):
    """Un atacante que agota los intentos no deja fuera al usuario legítimo."""
    atacante = _ip()
    for _ in range(MAX_FAILURES_PER_ACCOUNT):
        await _login(client, user_a["email"], "Incorrecta1!", atacante)
    assert (await _login(client, user_a["email"], "Password123!", atacante)).status_code == 429

    assert (await _login(client, user_a["email"], "Password123!", _ip())).status_code == 200


@pytest.mark.asyncio
async def test_un_login_correcto_reinicia_el_contador_de_la_cuenta(client: AsyncClient, user_a):
    ip = _ip()
    for _ in range(MAX_FAILURES_PER_ACCOUNT - 1):
        await _login(client, user_a["email"], "Incorrecta1!", ip)
    assert (await _login(client, user_a["email"], "Password123!", ip)).status_code == 200

    for _ in range(MAX_FAILURES_PER_ACCOUNT - 1):
        assert (await _login(client, user_a["email"], "Incorrecta1!", ip)).status_code == 401
    assert (await _login(client, user_a["email"], "Password123!", ip)).status_code == 200


@pytest.mark.asyncio
async def test_bloquea_la_ip_que_prueba_muchos_emails(client: AsyncClient, user_a):
    """Credential stuffing: muchos emails desde un origen agotan el contador de la IP."""
    ip = _ip()
    for i in range(MAX_FAILURES_PER_IP):
        await _login(client, f"nadie-{i}-{uuid.uuid4().hex[:6]}@example.com", "Incorrecta1!", ip)

    assert (await _login(client, user_a["email"], "Password123!", ip)).status_code == 429


@pytest.mark.asyncio
async def test_un_403_no_cuenta_como_fallo(client: AsyncClient, super_admin_user):
    """super_admin en /v1/auth/login da 403 con la contraseña correcta: no es fuerza bruta."""
    ip = _ip()
    for _ in range(MAX_FAILURES_PER_ACCOUNT + 1):
        resp = await _login(client, super_admin_user["email"], super_admin_user["password"], ip)
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_el_login_de_admin_tambien_esta_limitado(client: AsyncClient, super_admin_user):
    ip = _ip()
    for _ in range(MAX_FAILURES_PER_ACCOUNT):
        resp = await _login(client, super_admin_user["email"], "Incorrecta1!", ip, "/admin/auth/login")
        assert resp.status_code == 401

    resp = await _login(client, super_admin_user["email"], super_admin_user["password"], ip, "/admin/auth/login")
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_un_vecino_de_red_no_puede_falsear_su_ip(user_a):
    """inv-api está en la red compartida del gateway: un contenedor que lo llama
    directo con X-Forwarded-For inventado sigue contando con su IP real."""
    vecino = ASGITransport(app=app, client=("172.22.0.77", 40000))
    async with AsyncClient(transport=vecino, base_url="http://test") as c:
        for _ in range(MAX_FAILURES_PER_ACCOUNT):
            resp = await _login(c, user_a["email"], "Incorrecta1!", _ip())  # una IP falsa distinta cada vez
            assert resp.status_code == 401
        assert (await _login(c, user_a["email"], "Password123!", _ip())).status_code == 429

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    assert await r.exists("login_fail:ip:172.22.0.77")
    await r.aclose()


@pytest.mark.asyncio
async def test_confia_en_un_proxy_declarado_por_nombre(client: AsyncClient, user_a, monkeypatch):
    """El portal se declara por nombre de contenedor: se resuelve y su cabecera vale."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOSTS", "localhost")
    ip = _ip()
    for _ in range(MAX_FAILURES_PER_ACCOUNT):
        await _login(client, user_a["email"], "Incorrecta1!", ip)
    assert (await _login(client, user_a["email"], "Password123!", ip)).status_code == 429
    # Otra IP reenviada por el mismo proxy no hereda el bloqueo
    assert (await _login(client, user_a["email"], "Password123!", _ip())).status_code == 200
