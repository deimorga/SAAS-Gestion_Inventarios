"""
Celery application — punto de entrada para inv-worker e inv-beat.

Tasks registradas:
  - send_email           : envío de email vía Resend SDK (retry x3 backoff exponencial)
  - check_expiring_api_keys : tarea Beat diaria — detecta keys próximas a vencer (T-30, T-7, T-1, T-0)
  - revoke_grace_period_key : revoca una API Key al expirar su período de gracia
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import resend
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)

# ── Celery app ─────────────────────────────────────────────────────────────

celery_app = Celery(
    "micronuba",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BROKER_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "check-expiring-api-keys-daily": {
        "task": "app.tasks.check_expiring_api_keys",
        "schedule": crontab(hour=8, minute=0),
    },
}


# ── Email templates ────────────────────────────────────────────────────────

_TEMPLATES: dict[str, dict[str, str]] = {
    "account_activation": {
        "subject": "Activa tu cuenta en MicroNuba",
        "text": (
            "Hola {full_name},\n\n"
            "Tu cuenta ha sido creada en MicroNuba. Actívala en el siguiente enlace (válido 48h):\n\n"
            "{activation_url}\n\n"
            "Si no solicitaste esta cuenta, ignora este mensaje.\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p>Tu cuenta ha sido creada en MicroNuba. Actívala en el siguiente enlace (válido 48h):</p>"
            "<p><a href='{activation_url}'>{activation_url}</a></p>"
            "<p>Si no solicitaste esta cuenta, ignora este mensaje.</p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
    "activation_resent": {
        "subject": "Nuevo enlace de activación — MicroNuba",
        "text": (
            "Hola {full_name},\n\n"
            "Se ha generado un nuevo enlace de activación para tu cuenta (válido 48h):\n\n"
            "{activation_url}\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p>Se ha generado un nuevo enlace de activación (válido 48h):</p>"
            "<p><a href='{activation_url}'>{activation_url}</a></p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
    "password_changed": {
        "subject": "Tu contraseña fue cambiada — MicroNuba",
        "text": (
            "Hola {full_name},\n\n"
            "Tu contraseña en MicroNuba fue cambiada exitosamente.\n\n"
            "Si no realizaste este cambio, contacta soporte de inmediato.\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p>Tu contraseña en MicroNuba fue cambiada exitosamente.</p>"
            "<p>Si no realizaste este cambio, contacta soporte de inmediato.</p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
    "api_key_expiring_30d": {
        "subject": "Tu API Key vence en 30 días — MicroNuba",
        "text": (
            "Hola {full_name},\n\n"
            "La API Key '{key_name}' de tu cuenta vence el {expires_at}.\n"
            "Rótala desde el panel o vía API para evitar interrupciones.\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p>La API Key <code>{key_name}</code> vence el <strong>{expires_at}</strong>.</p>"
            "<p>Rótala desde el panel o vía API para evitar interrupciones.</p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
    "api_key_expiring_7d": {
        "subject": "Tu API Key vence en 7 días — MicroNuba",
        "text": (
            "Hola {full_name},\n\n"
            "AVISO: La API Key '{key_name}' vence el {expires_at} (en 7 días).\n"
            "Rótala lo antes posible.\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p><strong>AVISO:</strong> La API Key <code>{key_name}</code> vence el "
            "<strong>{expires_at}</strong> (en 7 días).</p>"
            "<p>Rótala lo antes posible.</p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
    "api_key_expiring_1d": {
        "subject": "Tu API Key vence MAÑANA — MicroNuba",
        "text": (
            "Hola {full_name},\n\n"
            "URGENTE: La API Key '{key_name}' vence MAÑANA ({expires_at}).\n"
            "Rótala ahora para evitar interrupciones en tus integraciones.\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p><strong>URGENTE:</strong> La API Key <code>{key_name}</code> vence "
            "<strong>MAÑANA ({expires_at})</strong>.</p>"
            "<p>Rótala ahora para evitar interrupciones en tus integraciones.</p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
    "api_key_expired": {
        "subject": "Tu API Key ha vencido — MicroNuba",
        "text": (
            "Hola {full_name},\n\n"
            "La API Key '{key_name}' venció hoy ({expires_at}) y ha sido desactivada.\n"
            "Crea una nueva key desde el panel para restaurar tus integraciones.\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p>La API Key <code>{key_name}</code> venció hoy (<strong>{expires_at}</strong>) "
            "y ha sido desactivada.</p>"
            "<p>Crea una nueva key desde el panel para restaurar tus integraciones.</p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
    "api_key_rotated": {
        "subject": "API Key rotada exitosamente — MicroNuba",
        "text": (
            "Hola {full_name},\n\n"
            "La API Key '{key_name}' fue rotada. Una nueva key ha sido generada.\n"
            "Actualiza tu integración con las nuevas credenciales.\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p>La API Key <code>{key_name}</code> fue rotada. Una nueva key ha sido generada.</p>"
            "<p>Actualiza tu integración con las nuevas credenciales.</p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
    "tenant_created": {
        "subject": "Bienvenido a MicroNuba — Activa tu cuenta",
        "text": (
            "Hola {full_name},\n\n"
            "Tu empresa ha sido registrada en MicroNuba. Como administrador, activa tu cuenta:\n\n"
            "{activation_url}\n\n"
            "Este enlace es válido por 48 horas.\n\n"
            "— Equipo MicroNuba"
        ),
        "html": (
            "<p>Hola <strong>{full_name}</strong>,</p>"
            "<p>Tu empresa ha sido registrada en MicroNuba. Como administrador, activa tu cuenta:</p>"
            "<p><a href='{activation_url}'>{activation_url}</a></p>"
            "<p>Este enlace es válido por 48 horas.</p>"
            "<p>— Equipo MicroNuba</p>"
        ),
    },
}


# ── Tasks ──────────────────────────────────────────────────────────────────


@celery_app.task(
    name="app.tasks.send_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def send_email(
    self,
    to_email: str,
    template: str,
    context: dict,
) -> None:
    """Envía un email usando Resend SDK.

    Soporta 9 templates predefinidos. Retry automático x3 con backoff exponencial.
    """
    tpl = _TEMPLATES.get(template)
    if tpl is None:
        raise ValueError(f"Template desconocido: {template}")

    resend.api_key = settings.RESEND_API_KEY

    # "from" es keyword en Python; se pasa como clave de dict literal
    params: resend.Emails.SendParams = {  # type: ignore[assignment]
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": [to_email],
        "subject": tpl["subject"].format(**context),
        "text": tpl["text"].format(**context),
        "html": tpl["html"].format(**context),
    }
    response = resend.Emails.send(params)
    logger.info("Email enviado a %s (template=%s, id=%s)", to_email, template, response["id"])


@celery_app.task(name="app.tasks.check_expiring_api_keys")
def check_expiring_api_keys() -> dict:
    """Detecta API Keys próximas a vencer y encola notificaciones.

    Hitos: T-30, T-7, T-1 (pre-vencimiento) y T-0 (vence hoy → desactiva).
    """
    return asyncio.run(_async_check_expiring_api_keys())


async def _async_check_expiring_api_keys() -> dict:
    now = datetime.now(timezone.utc)
    today = now.date()
    milestones = {30: "api_key_expiring_30d", 7: "api_key_expiring_7d", 1: "api_key_expiring_1d"}
    queued = 0
    expired = 0

    async with AsyncSessionLocal() as db:
        for days_ahead, template in milestones.items():
            target_date = today + timedelta(days=days_ahead)
            result = await db.execute(
                select(ApiKey).where(
                    ApiKey.is_active,
                    ApiKey.expires_at.isnot(None),
                )
            )
            keys = result.scalars().all()
            for key in keys:
                if key.expires_at and key.expires_at.date() == target_date:
                    send_email.delay(
                        to_email="",
                        template=template,
                        context={
                            "full_name": "Administrador",
                            "key_name": key.name,
                            "expires_at": key.expires_at.strftime("%Y-%m-%d"),
                        },
                    )
                    queued += 1

        # T-0: desactivar keys vencidas hoy
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.is_active,
                ApiKey.expires_at.isnot(None),
            )
        )
        for key in result.scalars().all():
            if key.expires_at and key.expires_at.date() <= today:
                key.is_active = False
                expired += 1
        if expired:
            await db.commit()

    logger.info("check_expiring_api_keys: %d notificaciones encoladas, %d keys vencidas", queued, expired)
    return {"queued": queued, "expired": expired}


@celery_app.task(name="app.tasks.revoke_grace_period_key")
def revoke_grace_period_key(key_id: str) -> dict:
    """Revoca la API Key anterior al terminar el período de gracia."""
    return asyncio.run(_async_revoke_grace_period_key(key_id))


async def _async_revoke_grace_period_key(key_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        key = result.scalar_one_or_none()
        if key is None:
            logger.warning("revoke_grace_period_key: key %s no encontrada", key_id)
            return {"revoked": False, "reason": "not_found"}
        if not key.is_active:
            return {"revoked": False, "reason": "already_inactive"}
        key.is_active = False
        await db.commit()
        logger.info("revoke_grace_period_key: key %s revocada", key_id)
        return {"revoked": True, "key_id": key_id}
