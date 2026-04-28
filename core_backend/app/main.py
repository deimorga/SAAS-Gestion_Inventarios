import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import http_exception_handler, validation_exception_handler
from app.core.redis_client import close_redis, get_redis


async def _expire_reservations_loop() -> None:
    """Tarea de fondo: expira reservas vencidas cada 60 segundos.

    La tabla reservations tiene RLS FORCE, por lo que no se puede consultar
    sin tenant context. Se itera sobre la tabla tenants (sin RLS) y se
    procesa cada tenant con su contexto.
    """
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal

    while True:
        await asyncio.sleep(60)
        try:
            async with AsyncSessionLocal() as session:
                tenant_rows = (
                    await session.execute(text("SELECT id FROM tenants"))
                ).fetchall()

                expired_any = False
                for tenant_row in tenant_rows:
                    tid = str(tenant_row.id)
                    await session.execute(
                        text("SET LOCAL app.current_tenant = :tid"), {"tid": tid}
                    )
                    expired_rows = (
                        await session.execute(
                            text(
                                "SELECT id FROM reservations "
                                "WHERE status = 'ACTIVE' AND expires_at <= now()"
                            )
                        )
                    ).fetchall()

                    for row in expired_rows:
                        await session.execute(
                            text(
                                "UPDATE stock_balances sb "
                                "SET reserved_qty = sb.reserved_qty - ri.quantity, "
                                "    available_qty = sb.available_qty + ri.quantity, "
                                "    version = sb.version + 1, "
                                "    updated_at = now() "
                                "FROM reservation_items ri "
                                "WHERE ri.reservation_id = :rid "
                                "  AND sb.product_id = ri.product_id "
                                "  AND sb.zone_id = ri.zone_id "
                                "  AND sb.tenant_id = ri.tenant_id"
                            ),
                            {"rid": str(row.id)},
                        )
                        await session.execute(
                            text("UPDATE reservations SET status = 'EXPIRED', updated_at = now() WHERE id = :id"),
                            {"id": str(row.id)},
                        )
                        expired_any = True

                if expired_any:
                    await session.commit()
        except Exception:
            pass


async def _dispatch_webhooks_loop() -> None:
    """Tarea de fondo: entrega webhook_deliveries pendientes cada WEBHOOK_POLL_SECONDS.

    Itera por tenant (RLS FORCE) para poder consultar las tablas protegidas.
    Reintenta con backoff exponencial: 30s → 5min → 30min (máx 3 intentos).
    """
    import hashlib
    import hmac as hmac_module
    import json
    from datetime import datetime, timedelta, timezone

    import httpx
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal

    _backoff = [30, 300, 1800]

    while True:
        await asyncio.sleep(settings.WEBHOOK_POLL_SECONDS)
        try:
            async with AsyncSessionLocal() as session:
                tenant_rows = (
                    await session.execute(text("SELECT id FROM tenants"))
                ).fetchall()

                for tenant_row in tenant_rows:
                    tid = str(tenant_row.id)
                    await session.execute(
                        text("SET LOCAL app.current_tenant = :tid"), {"tid": tid}
                    )
                    pending = (
                        await session.execute(
                            text(
                                "SELECT wd.id, wd.event_type, wd.payload, wd.attempts, "
                                "       we.url, we.secret "
                                "FROM webhook_deliveries wd "
                                "JOIN webhook_endpoints we ON wd.endpoint_id = we.id "
                                "WHERE wd.tenant_id = :tid AND wd.status = 'PENDING' "
                                "AND (wd.next_attempt_at IS NULL OR wd.next_attempt_at <= now())"
                            ),
                            {"tid": tid},
                        )
                    ).fetchall()

                    for row in pending:
                        payload_bytes = json.dumps(row.payload).encode()
                        sig = "sha256=" + hmac_module.new(
                            row.secret.encode(), payload_bytes, hashlib.sha256
                        ).hexdigest()

                        try:
                            async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as http:
                                resp = await http.post(
                                    row.url,
                                    content=payload_bytes,
                                    headers={
                                        "Content-Type": "application/json",
                                        "X-Webhook-Signature": sig,
                                        "X-Webhook-Event": row.event_type,
                                    },
                                )
                            delivered = resp.status_code < 300
                            last_code = resp.status_code
                            last_body = resp.text[:1000]
                        except Exception as exc:
                            delivered = False
                            last_code = None
                            last_body = str(exc)[:1000]

                        new_attempts = row.attempts + 1
                        if delivered:
                            new_status = "DELIVERED"
                            next_attempt = None
                        elif new_attempts >= settings.WEBHOOK_MAX_ATTEMPTS:
                            new_status = "FAILED"
                            next_attempt = None
                        else:
                            new_status = "PENDING"
                            backoff = _backoff[min(new_attempts - 1, len(_backoff) - 1)]
                            next_attempt = datetime.now(timezone.utc) + timedelta(seconds=backoff)

                        await session.execute(
                            text(
                                "UPDATE webhook_deliveries "
                                "SET status = :s, attempts = :a, last_response_code = :lc, "
                                "    last_response_body = :lb, next_attempt_at = :na "
                                "WHERE id = :id"
                            ),
                            {
                                "s": new_status,
                                "a": new_attempts,
                                "lc": last_code,
                                "lb": last_body,
                                "na": next_attempt,
                                "id": str(row.id),
                            },
                        )

                await session.commit()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async for _ in get_redis():
        break
    task_reservations = asyncio.create_task(_expire_reservations_loop())
    task_webhooks = asyncio.create_task(_dispatch_webhooks_loop())
    yield
    task_reservations.cancel()
    task_webhooks.cancel()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="MicroNuba Inventory API",
    version="1.0.0",
    description=(
        "Motor de inventarios transaccional Multi-Tenant.\n\n"
        "## Autenticación\n"
        "Todos los endpoints (excepto `/v1/auth/login`) requieren `Authorization: Bearer <token>` "
        "o `X-API-Key: <key>`.\n\n"
        "## Multi-Tenant\n"
        "Cada request opera exclusivamente sobre los datos del tenant autenticado. "
        "El aislamiento está garantizado por RLS en PostgreSQL.\n\n"
        "## Rate Limiting\n"
        "Las cabeceras `X-RateLimit-Limit`, `X-RateLimit-Remaining` y `X-RateLimit-Reset` "
        "informan el consumo por minuto según el tier de suscripción."
    ),
    contact={"name": "MicroNuba Support", "email": "api@micronuba.com"},
    license_info={"name": "Propietario — Todos los derechos reservados"},
    docs_url="/docs" if settings.ENABLE_SWAGGER else None,
    redoc_url="/redoc" if settings.ENABLE_SWAGGER else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def inject_request_id(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id

    auth = getattr(request.state, "auth", None)
    if auth and auth.rate_limit_info:
        rl = auth.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(rl.get("limit", ""))
        response.headers["X-RateLimit-Remaining"] = str(rl.get("remaining", ""))
        response.headers["X-RateLimit-Reset"] = str(rl.get("reset", ""))

    return response


app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(v1_router)


@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    description="Verifica la conectividad con PostgreSQL y Redis.",
    responses={503: {"description": "Servicio degradado"}},
)
async def health_check():
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal
    from app.core.redis_client import get_redis as _get_redis

    db_status = "ok"
    redis_status = "ok"

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        async for r in _get_redis():
            await r.ping()
    except Exception:
        redis_status = "error"

    overall = "healthy" if db_status == "ok" and redis_status == "ok" else "degraded"
    return JSONResponse(
        status_code=200 if overall == "healthy" else 503,
        content={"status": overall, "db": db_status, "redis": redis_status},
    )


@app.get("/", tags=["System"], include_in_schema=False)
async def root():
    return {"message": "MicroNuba Inventory API v1.0.0 is running"}
