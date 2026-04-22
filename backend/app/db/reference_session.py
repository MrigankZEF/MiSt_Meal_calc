from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

reference_engine = create_engine(settings.reference_db_url, future=True)
ReferenceSession = sessionmaker(bind=reference_engine, autoflush=False)


def get_reference_session() -> Iterator[Session]:
    """FastAPI dependency for a per-request reference-DB session."""
    with ReferenceSession() as session:
        yield session
