from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="MicroNuba Inventory SaaS API",
    description="API Gateway para el motor de inventarios transaccional Multi-Tenant.",
    version="1.0.0",
)

@app.get("/health", tags=["System"])
async def health_check():
    """Endpoint de monitoreo (Healthcheck) para Docker/Traefik."""
    return JSONResponse(
        content={
            "status": "healthy",
            "db": "ok",    # TODO: Implementar verificación real
            "redis": "ok"  # TODO: Implementar verificación real
        }
    )

@app.get("/", tags=["System"])
async def root():
    return {"message": "MicroNuba Inventory API v1.0.0 is running"}
