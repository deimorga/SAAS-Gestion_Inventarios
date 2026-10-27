"""
Tests del límite de intentos fallidos de login (/v1/auth/login y /admin/auth/login).

Cada test usa su propia IP en X-Forwarded-For para no compartir contadores.
"""
import uuid

import pytest
from httpx import AsyncClient

from app.services.login_throttle import MAX_FAILURES_PER_ACCOUNT, MAX_FAILURES_PER_IP


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
