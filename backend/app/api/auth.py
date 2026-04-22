"""fastapi-users wiring: transport, strategy, user manager, and the
``current_active_user`` dependency used by other routers.
"""

from __future__ import annotations

import uuid

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.user_session import get_async_user_session
from app.models.user import User

# ── Database dependency ────────────────────────────────────────────────────


async def get_user_db(
    session: AsyncSession = Depends(get_async_user_session),
) -> SQLAlchemyUserDatabase:  # type: ignore[type-arg]
    yield SQLAlchemyUserDatabase(session, User)


# ── User manager ───────────────────────────────────────────────────────────


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),  # type: ignore[type-arg]
) -> UserManager:
    yield UserManager(user_db)


# ── JWT backend ────────────────────────────────────────────────────────────

bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=settings.jwt_lifetime_seconds,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# ── FastAPIUsers instance ──────────────────────────────────────────────────

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

# Dependency injected into protected routes.
current_active_user = fastapi_users.current_user(active=True)
