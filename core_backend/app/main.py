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
    """Tarea de fondo: expira reservas vencidas cada 60 segundos."""
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal

    while True:
        await asyncio.sleep(60)
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text(
                        "SELECT id, tenant_id FROM reservations "
                        "WHERE status = 'ACTIVE' AND expires_at <= now()"
                    )
                )
                rows = result.fetchall()
                for row in rows:
                    await session.execute(
                        text("SET LOCAL app.current_tenant = :tid"),
                        {"tid": row.tenant_id},
                    )
                    # Devolver stock reservado
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
                        {"rid": row.id},
                    )
                    await session.execute(
                        text("UPDATE reservations SET status = 'EXPIRED', updated_at = now() WHERE id = :id"),
                        {"id": row.id},
                    )
                if rows:
                    await session.commit()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async for _ in get_redis():
        break
    task = asyncio.create_task(_expire_reservations_loop())
    yield
    task.cancel()
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
