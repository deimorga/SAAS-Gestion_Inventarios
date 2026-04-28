from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    ENABLE_SWAGGER: bool = True  # False en producción

    DATABASE_URL: str = "postgresql+asyncpg://inventory_user:devpassword123@inv-postgres:5432/inventory_db"
    REDIS_URL: str = "redis://inv-redis:6379/0"
    CELERY_BROKER_URL: str = "redis://inv-redis:6379/1"

    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Expiración por defecto de reservas (minutos) cuando el cliente no envía expires_at
    RESERVATION_TTL_MINUTES: int = 30

    model_config = {"env_file": ".env", "case_sensitive": True}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
