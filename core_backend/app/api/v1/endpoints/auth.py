from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.api.deps import get_db
from app.core.redis_client import get_redis
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RefreshResponse, TokenResponse
from app.services.auth import authenticate_user, issue_tokens, logout, refresh_session

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    user = await authenticate_user(body.email, body.password, db)
    return await issue_tokens(user, redis)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await refresh_session(body.refresh_token, db, redis)


@router.post("/logout", status_code=204)
async def do_logout(
    body: LogoutRequest,
    redis: aioredis.Redis = Depends(get_redis),
):
    await logout(body.refresh_token, redis)
