from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# psycopg3 supports async natively; the same URL scheme works for both.
user_engine = create_async_engine(
    settings.user_db_url,
    echo=False,
    # Connection pool tuning — small pool is fine for dev; Railway scales automatically.
    pool_size=5,
    max_overflow=10,
)

async_user_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    user_engine,
    expire_on_commit=False,
)


async def get_async_user_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_user_session_maker() as session:
        yield session
