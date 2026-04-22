from pathlib import Path

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

    # Postgres for per-org user data (meals, procurement, auth).
    user_db_url: str = "postgresql+psycopg://mist:mist@localhost:5432/mist"

    # JWT secret — MUST be overridden via SECRET_KEY env var in production.
    secret_key: str = "dev-insecure-secret-change-in-production"

    # Token lifetime in seconds (default: 7 days)
    jwt_lifetime_seconds: int = 60 * 60 * 24 * 7


settings = Settings()
