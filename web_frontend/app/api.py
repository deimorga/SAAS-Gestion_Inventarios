import os
from typing import Any

# pyrefly: ignore [missing-import]
import httpx
# pyrefly: ignore [missing-import]
from nicegui import app, ui

BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
_TIMEOUT = 15.0


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Token refresh ────────────────────────────────────────────────────────────

class SessionExpiredError(Exception):
    """Raised when both access and refresh tokens are expired/invalid."""


async def refresh_tokens(refresh_token: str) -> dict[str, Any]:
    """Exchange a refresh_token for a new access_token + refresh_token.

    Uses POST /v1/auth/refresh (universal endpoint, works for all roles).
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
        r.raise_for_status()
        return r.json()


async def _ensure_valid_token() -> str:
    """Return a valid access token, refreshing if needed.

    If the refresh also fails, raises SessionExpiredError so the caller
    can redirect to the login page.
    """
    token = app.storage.user.get("token", "")
    if not token:
        raise SessionExpiredError()
    return token


async def _handle_401_refresh() -> str:
    """Attempt to refresh the session after a 401 response.

    Returns the new access_token on success.
    Raises SessionExpiredError if the refresh_token is also invalid.
    """
    rt = app.storage.user.get("refresh_token", "")
    if not rt:
        app.storage.user.clear()
        try:
            ui.navigate.to("/login")
        except Exception:
            pass
        raise SessionExpiredError()

    try:
        data = await refresh_tokens(rt)
        # Persist the new tokens in the user storage
        app.storage.user["token"] = data["access_token"]
        app.storage.user["refresh_token"] = data["refresh_token"]
        return data["access_token"]
    except httpx.HTTPStatusError:
        # Refresh token also expired/invalid → force re-login
        app.storage.user.clear()
        try:
            ui.navigate.to("/login")
        except Exception:
            pass
        raise SessionExpiredError()


async def _authed_request(
    method: str,
    path: str,
    token: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    """Execute an authenticated request with automatic 401 retry.

    On the first 401, attempts to refresh the session and retries once.
    If the refresh also fails, raises SessionExpiredError.
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.request(method, path, headers=_headers(token), params=params, json=json)

        if r.status_code == 401:
            # Try to refresh
            new_token = await _handle_401_refresh()
            # Retry with the fresh token
            r = await c.request(method, path, headers=_headers(new_token), params=params, json=json)

        r.raise_for_status()
        return r


# ── Auth (no auto-refresh needed) ────────────────────────────────────────────

async def admin_login(email: str, password: str) -> dict[str, Any]:
    """Autenticación en cascada: intenta /admin/auth/login (super_admin).

    Si el backend responde con 403 (rol no permitido en superficie admin),
    reintenta en /v1/auth/login (tenant_admin).
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=_TIMEOUT) as c:
        r = await c.post("/admin/auth/login", json={"email": email, "password": password})
        if r.status_code == 403:
            # Cascada: tenant_admin usa la superficie de cliente
            r = await c.post("/v1/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        return r.json()


# ── Tenants ──────────────────────────────────────────────────────────────────

async def list_tenants(token: str, page: int = 1, size: int = 50) -> dict[str, Any]:
    r = await _authed_request("GET", "/admin/tenants", token, params={"page": page, "size": size})
    return r.json()


async def create_tenant(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request("POST", "/admin/tenants", token, json=payload)
    return r.json()


async def get_tenant(token: str, tenant_id: str) -> dict[str, Any]:
    r = await _authed_request("GET", f"/admin/tenants/{tenant_id}", token)
    return r.json()


async def update_tenant(token: str, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request("PATCH", f"/admin/tenants/{tenant_id}", token, json=payload)
    return r.json()


async def get_tenant_keys(token: str, tenant_id: str) -> dict[str, Any]:
    r = await _authed_request("GET", f"/admin/tenants/{tenant_id}/api-keys", token)
    return r.json()


async def create_tenant_api_key(token: str, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request("POST", f"/admin/tenants/{tenant_id}/api-keys", token, json=payload)
    return r.json()


async def revoke_key(token: str, tenant_id: str, key_id: str) -> None:
    await _authed_request("DELETE", f"/admin/tenants/{tenant_id}/api-keys/{key_id}", token)


# ── Products ─────────────────────────────────────────────────────────────────

async def list_products(token: str, tenant_id: str, page: int = 1, search: str | None = None, **kwargs: Any) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "page_size": kwargs.get("page_size", 50)}
    if search:
        params["search"] = search
    r = await _authed_request("GET", f"/admin/tenants/{tenant_id}/products", token, params=params)
    return r.json()


async def create_product(token: str, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request("POST", f"/admin/tenants/{tenant_id}/products", token, json=payload)
    return r.json()


async def update_product(token: str, tenant_id: str, product_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request("PATCH", f"/admin/tenants/{tenant_id}/products/{product_id}", token, json=payload)
    return r.json()


async def delete_product(token: str, tenant_id: str, product_id: str) -> None:
    await _authed_request("DELETE", f"/admin/tenants/{tenant_id}/products/{product_id}", token)


# ── Categories ──────────────────────────────────────────────────────────────

async def list_categories(token: str, tenant_id: str) -> list[dict[str, Any]]:
    r = await _authed_request("GET", f"/admin/tenants/{tenant_id}/categories", token)
    return r.json()


# ── Stock ────────────────────────────────────────────────────────────────────

async def list_stock(token: str, tenant_id: str, warehouse_id: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"page_size": 100}
    if warehouse_id:
        params["warehouse_id"] = warehouse_id
    r = await _authed_request("GET", f"/admin/tenants/{tenant_id}/stock", token, params=params)
    return r.json()


async def stock_receipt(token: str, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request("POST", f"/admin/tenants/{tenant_id}/stock/receipts", token, json=payload)
    return r.json()


async def stock_adjustment(token: str, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request("POST", f"/admin/tenants/{tenant_id}/stock/adjustments", token, json=payload)
    return r.json()


# ── Warehouses & Zones ───────────────────────────────────────────────────────

async def list_warehouses(token: str, tenant_id: str) -> list[dict[str, Any]]:
    r = await _authed_request("GET", f"/admin/tenants/{tenant_id}/warehouses", token)
    return r.json()


async def list_zones(token: str, tenant_id: str, warehouse_id: str) -> list[dict[str, Any]]:
    r = await _authed_request("GET", f"/admin/tenants/{tenant_id}/warehouses/{warehouse_id}/zones", token)
    return r.json()


async def create_warehouse(token: str, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request("POST", f"/admin/tenants/{tenant_id}/warehouses", token, json=payload)
    return r.json()


async def create_zone(token: str, tenant_id: str, warehouse_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = await _authed_request(
        "POST", f"/admin/tenants/{tenant_id}/warehouses/{warehouse_id}/zones", token, json=payload
    )
    return r.json()
