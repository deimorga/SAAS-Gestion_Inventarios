import os
from typing import Any

import httpx

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8002")
_TIMEOUT = 15.0


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def admin_login(email: str, password: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.post("/admin/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        return r.json()


async def list_tenants(token: str, page: int = 1, size: int = 50) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.get(
            "/admin/tenants",
            params={"page": page, "size": size},
            headers=_headers(token),
        )
        r.raise_for_status()
        return r.json()


async def create_tenant(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.post("/admin/tenants", json=payload, headers=_headers(token))
        r.raise_for_status()
        return r.json()


async def get_tenant(token: str, tenant_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.get(f"/admin/tenants/{tenant_id}", headers=_headers(token))
        r.raise_for_status()
        return r.json()


async def update_tenant(token: str, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.patch(f"/admin/tenants/{tenant_id}", json=payload, headers=_headers(token))
        r.raise_for_status()
        return r.json()


async def get_tenant_keys(token: str, tenant_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.get(f"/admin/tenants/{tenant_id}/api-keys", headers=_headers(token))
        r.raise_for_status()
        return r.json()


async def create_tenant_api_key(token: str, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.post(
            f"/admin/tenants/{tenant_id}/api-keys",
            json=payload,
            headers=_headers(token),
        )
        r.raise_for_status()
        return r.json()


async def revoke_key(token: str, tenant_id: str, key_id: str) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.delete(
            f"/admin/tenants/{tenant_id}/api-keys/{key_id}",
            headers=_headers(token),
        )
        r.raise_for_status()
