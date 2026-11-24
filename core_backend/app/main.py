import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin.router import router as admin_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import assert_rls_enforced, engine
from app.core.exceptions import http_exception_handler, validation_exception_handler
from app.core.redis_client import close_redis, get_redis


async def _expire_reservations_loop() -> None:
    """Tarea de fondo: expira reservas vencidas cada 60 segundos.

    La tabla reservations tiene RLS FORCE, por lo que no se puede consultar
    sin tenant context. Se itera sobre la tabla tenants (sin RLS) y se
    procesa cada tenant con su contexto.
    """
    from app.services.reservation import expire_due_reservations

    while True:
        await asyncio.sleep(60)
        try:
            await expire_due_reservations()
        except Exception:
            # Un fallo general (p. ej. la base caída) no debe matar el bucle, pero tampoco callarse
            logging.getLogger(__name__).exception("Fallo en el bucle de expiración de reservas")


async def _dispatch_webhooks_loop() -> None:
    """Tarea de fondo: entrega los webhooks pendientes cada WEBHOOK_POLL_SECONDS.

    Toda la lógica vive en `app.services.webhook.dispatch_pending_webhooks` (una transacción por
    entrega, con reintentos y backoff). Aquí solo se evita que un fallo general mate el bucle.
    """
    from app.services.webhook import dispatch_pending_webhooks

    while True:
        await asyncio.sleep(settings.WEBHOOK_POLL_SECONDS)
        try:
            await dispatch_pending_webhooks()
        except Exception:
            logging.getLogger(__name__).exception("Fallo en el bucle de despacho de webhooks")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Falla rápido si la app corre con un rol capaz de ignorar RLS
    await assert_rls_enforced()
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
    redoc_url=None,
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

app.mount("/static", StaticFiles(directory="/app/static"), name="static")


@app.get("/redoc", include_in_schema=False)
async def redoc_html() -> HTMLResponse:
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="MicroNuba Inventory API — ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )


app.include_router(admin_router)
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
