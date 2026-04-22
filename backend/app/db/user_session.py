from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# SQLite (dev default) and Postgres (production) both work here.
# SQLite uses aiosqlite driver; Postgres uses psycopg3.
# Connection pool kwargs are not supported by SQLite — skip them for SQLite.
_is_sqlite = settings.user_db_url.startswith("sqlite")

user_engine = create_async_engine(
    settings.user_db_url,
    echo=False,
    # SQLite doesn't support pool_size / max_overflow
    **({} if _is_sqlite else {"pool_size": 5, "max_overflow": 10}),
)

async_user_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    user_engine,
    expire_on_commit=False,
)


async def get_async_user_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_user_session_maker() as session:
        yield session
