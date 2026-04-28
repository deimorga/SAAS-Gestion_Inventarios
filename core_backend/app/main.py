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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # startup
    async for _ in get_redis():
        break
    yield
    # shutdown
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="MicroNuba Inventory SaaS API",
    description="Motor de inventarios transaccional Multi-Tenant.",
    version="1.0.0",
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

    # Agregar headers de rate limit si están disponibles
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


@app.get("/health", tags=["System"])
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
