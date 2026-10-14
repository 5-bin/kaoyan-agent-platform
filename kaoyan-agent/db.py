"""异步数据库会话。"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

from sqlalchemy import URL

DATABASE_URL = URL.create(
    "mysql+aiomysql", username=settings.DB_USER, password=settings.DB_PASSWORD,
    host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
    query={"charset": "utf8mb4"},
)

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
