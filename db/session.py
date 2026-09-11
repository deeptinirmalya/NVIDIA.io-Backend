import asyncio
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ---------------------------------------------------------
# TLS / CA Certificate
# ---------------------------------------------------------

CA_CERT_PATH = Path(settings.TIDB_CA_CERT).resolve()

if not CA_CERT_PATH.exists():
    raise FileNotFoundError(
        f"TiDB CA certificate not found: {CA_CERT_PATH}"
    )


# ---------------------------------------------------------
# Database URL
# ---------------------------------------------------------

DATABASE_URL = URL.create(
    drivername="mysql+asyncmy",
    username=settings.TIDB_USER,
    password=settings.TIDB_PASSWORD,
    host=settings.TIDB_HOST,
    port=settings.TIDB_PORT,
    database=settings.TIDB_DATABASE,
)


# ---------------------------------------------------------
# Connection Pool + TLS
# ---------------------------------------------------------

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,

    # Connection pool
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,

    # TLS
    connect_args={
        "ssl": {
            "ca": str(CA_CERT_PATH),
        }
    },

    echo=False,
)


# ---------------------------------------------------------
# Session Factory
# ---------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ---------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------
# Connection Test
# ---------------------------------------------------------

async def test_database_connection() -> bool:
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            return result.scalar() == 1

    except Exception as exc:
        print(f"Database connection failed: {exc}")
        return False

# ---------------------------------------------------------
# Shutdown
# ---------------------------------------------------------

async def close_database() -> None:
    await engine.dispose()