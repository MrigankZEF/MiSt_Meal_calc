from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"
DEFAULT_REFERENCE_DB = DATA_DIR / "reference.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    cors_origins: list[str] = ["http://localhost:5173"]

    # SQLite for committed reference data (RIVM + NEVO + EAT-Lancet tags)
    reference_db_url: str = f"sqlite:///{DEFAULT_REFERENCE_DB.as_posix()}"

    # User data DB.
    # Dev default: SQLite file next to reference.db — no Postgres needed locally.
    # Production (Railway): set USER_DB_URL to the Postgres DATABASE_URL from Railway.
    # The validator below normalises postgres:// and postgresql:// → postgresql+psycopg://
    # so you can paste Railway's URL directly without editing the scheme.
    user_db_url: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'user.db').as_posix()}"

    @field_validator("user_db_url", mode="before")
    @classmethod
    def _normalise_user_db_url(cls, v: str) -> str:
        # Railway (and Heroku) provide postgres:// or postgresql:// but psycopg3 needs +psycopg
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    # JWT secret — MUST be overridden via SECRET_KEY env var in production.
    secret_key: str = "dev-insecure-secret-change-in-production"

    # Token lifetime in seconds (default: 7 days)
    jwt_lifetime_seconds: int = 60 * 60 * 24 * 7


settings = Settings()
