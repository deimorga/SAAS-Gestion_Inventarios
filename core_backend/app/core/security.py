import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

REFRESH_TOKEN_PREFIX = "refresh:"
ACCESS_BLACKLIST_PREFIX = "blacklist:"

TIER_RPM: dict[str, int] = {
    "STARTER": 60,
    "PROFESSIONAL": 1_000,
    "ENTERPRISE": 10_000,
}


# ── Passwords ──────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, tenant_id: str, role: str) -> tuple[str, int]:
    """Retorna (token, expires_in_seconds)."""
    expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire_minutes * 60


def decode_access_token(token: str) -> dict:
    """Lanza JWTError si el token es inválido o expirado."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── Refresh tokens (opacos, almacenados en Redis) ──────────────────────────

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def refresh_key(token: str) -> str:
    return f"{REFRESH_TOKEN_PREFIX}{token}"


def blacklist_key(jti: str) -> str:
    return f"{ACCESS_BLACKLIST_PREFIX}{jti}"


# ── API Keys ───────────────────────────────────────────────────────────────

def generate_api_key_pair() -> tuple[str, str, str]:
    """Retorna (key_id, key_secret, key_hash). key_hash es el SHA-256 del secret."""
    key_id = "mk_live_" + secrets.token_urlsafe(18)
    key_secret = "mk_secret_" + secrets.token_urlsafe(36)
    key_hash = hashlib.sha256(key_secret.encode()).hexdigest()
    return key_id, key_secret, key_hash


def hash_api_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


# ── Rate limit helpers ─────────────────────────────────────────────────────

def rate_limit_key(tenant_id: str) -> str:
    """Clave Redis por minuto bucket."""
    minute_bucket = int(datetime.now(timezone.utc).timestamp() // 60)
    return f"rate:{tenant_id}:{minute_bucket}"


def rpm_for_tier(tier: str) -> int:
    return TIER_RPM.get(tier.upper(), TIER_RPM["STARTER"])
