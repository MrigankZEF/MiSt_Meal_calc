import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import auth_backend, fastapi_users
from app.api.ingredients import router as ingredients_router
from app.api.meals import router as meals_router
from app.api.procurement import router as procurement_router
from app.api.score import router as score_router
from app.config import settings
from app.db.user_base import UserBase
from app.db.user_session import user_engine
from app.schemas.user import UserCreate, UserRead, UserUpdate

log = logging.getLogger(__name__)


async def _init_user_tables(max_attempts: int = 10, delay: float = 2.0) -> None:
    """Create user-DB tables on startup, retrying if Postgres isn't ready yet.

    This is intentionally idempotent (``create_all`` is a no-op for tables that
    already exist).  For proper production migrations use ``alembic upgrade head``
    before starting the server.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            async with user_engine.begin() as conn:
                await conn.run_sync(UserBase.metadata.create_all)
            log.info("User-DB tables ready.")
            return
        except Exception as exc:
            if attempt == max_attempts:
                log.error("Could not initialise user DB after %d attempts: %s", attempt, exc)
                raise
            log.warning(
                "User DB not ready (attempt %d/%d): %s — retrying in %.0fs…",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_user_tables()
    yield
    await user_engine.dispose()


app = FastAPI(
    title="MiSt API",
    version="0.3.0",
    description="Sustainability analytics for caterers — backend API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth routers (fastapi-users) ──────────────────────────────────────────

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/auth/users",
    tags=["users"],
)

# ── Application routers ───────────────────────────────────────────────────

app.include_router(ingredients_router)
app.include_router(meals_router)
app.include_router(procurement_router)
app.include_router(score_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version, "environment": settings.environment}
