"""
Revisión 2026-11-19 — R-10 (enlaces de los emails en desarrollo).

R-10: `ACTIVATION_BASE_URL` valía por defecto la URL del API (`http://api.inventarios.local:8090`), pero los
      enlaces `/activate` y `/reset-password` los sirve el PORTAL. Sin configurarlo, en desarrollo el enlace
      del email de activación y el de recuperación de contraseña daban 404.
"""
from urllib.parse import urlparse

from app.core.config import Settings
from app.services import activation as activation_service
from app.services import password_reset as password_reset_service

# Puerto del portal en desarrollo (docker-compose.dev.yml: 8081 -> 8080).
PORTAL_DEV_URL = "http://localhost:8081"


def _settings_por_defecto(monkeypatch) -> Settings:
    """Settings con el valor por defecto del código: sin variable de entorno ni .env que lo pisen."""
    monkeypatch.delenv("ACTIVATION_BASE_URL", raising=False)
    return Settings(_env_file=None)


def test_r10_el_valor_por_defecto_es_el_portal_no_el_api(monkeypatch):
    base = _settings_por_defecto(monkeypatch).ACTIVATION_BASE_URL
    assert base == PORTAL_DEV_URL
    assert urlparse(base).port != 8090, "8090 es el API: ahí no existen /activate ni /reset-password"


def test_r10_los_enlaces_de_activacion_y_de_reseteo_apuntan_al_portal(monkeypatch):
    por_defecto = _settings_por_defecto(monkeypatch)
    monkeypatch.setattr(activation_service, "settings", por_defecto)
    monkeypatch.setattr(password_reset_service, "settings", por_defecto)

    assert activation_service.activation_url("tok") == f"{PORTAL_DEV_URL}/activate?token=tok"
    assert password_reset_service.reset_url("tok") == f"{PORTAL_DEV_URL}/reset-password?token=tok"


def test_r10_el_ambiente_sigue_mandando_si_define_su_propia_url(monkeypatch):
    monkeypatch.setenv("ACTIVATION_BASE_URL", "https://staging-admin.inventarios.micronuba.net")
    configurada = Settings(_env_file=None)
    assert configurada.ACTIVATION_BASE_URL == "https://staging-admin.inventarios.micronuba.net"
