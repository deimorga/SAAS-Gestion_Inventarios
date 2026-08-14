from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    ENABLE_SWAGGER: bool = True  # False en producción

    # Conexión de la aplicación. Fuera de desarrollo DEBE apuntar a un rol sin
    # superuser ni BYPASSRLS: de lo contrario las políticas RLS quedan inertes y
    # el aislamiento entre tenants deja de estar garantizado por la base de datos.
    # `assert_rls_enforced` lo comprueba al arrancar.
    DATABASE_URL: str = "postgresql+asyncpg://inventory_user:devpassword123@inv-postgres:5432/inventory_db"
    # Conexión con privilegios de owner, usada solo por Alembic (DDL y políticas).
    # Si se deja vacía, Alembic cae en DATABASE_URL.
    MIGRATION_DATABASE_URL: str = ""
    REDIS_URL: str = "redis://inv-redis:6379/0"
    CELERY_BROKER_URL: str = "redis://inv-redis:6379/1"

    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Expiración por defecto de reservas (minutos) cuando el cliente no envía expires_at
    RESERVATION_TTL_MINUTES: int = 30

    # Webhook dispatcher
    WEBHOOK_MAX_ATTEMPTS: int = 3
    WEBHOOK_TIMEOUT_SECONDS: int = 10
    WEBHOOK_POLL_SECONDS: int = 10

    # Admin bootstrap — protege el endpoint POST /admin/auth/register
    # Dejar vacío en producción una vez creado el primer super_admin
    ADMIN_BOOTSTRAP_SECRET: str = ""

    # Resend — proveedor de email transaccional
    RESEND_API_KEY: str = "re_test_placeholder"
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"
    RESEND_FROM_NAME: str = "MicroNuba"

    # URL base para enlaces de activación de usuario en emails
    # En prod: https://portal.micronuba.com  |  En dev: http://api.inventarios.local:8090
    ACTIVATION_BASE_URL: str = "http://api.inventarios.local:8090"

    # TTL del token de activación de usuario (horas)
    ACTIVATION_TOKEN_TTL_HOURS: int = 48

    # API Keys — política de expiración y rotación
    API_KEY_EXPIRY_DAYS: int = 365
    API_KEY_ROTATION_GRACE_DAYS: int = 30  # mín 7, máx 90 (por tenant vía config JSONB)

    # SMTP — solo usado en APP_ENV=staging (Mailpit). En producción se usa Resend SDK.
    SMTP_HOST: str = "inv-mailpit-staging"
    SMTP_PORT: int = 1025

    model_config = {"env_file": ".env", "case_sensitive": True}

    @property
    def migration_url(self) -> str:
        """URL que usa Alembic: la de owner si está definida, si no la de la app."""
        return self.MIGRATION_DATABASE_URL or self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
