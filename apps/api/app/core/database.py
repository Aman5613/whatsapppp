"""Async SQLAlchemy engine, session factory, and dynamic reconnection for Neon PostgreSQL."""

import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from app.core.config import settings

logger = logging.getLogger(__name__)

_CONNECT_RETRIES = 3
_CONNECT_RETRY_DELAY = 2.0  # seconds – accommodates Neon cold starts



def normalize_db_url(url: str, is_async: bool = True) -> str:
    """Normalize database connection string for asyncpg or psycopg/sync."""
    url = url.strip()
    if not url or url.startswith("sqlite"):
        return url

    parsed = urlparse(url)
    scheme = parsed.scheme

    if is_async:
        if scheme in ("postgresql", "postgres"):
            scheme = "postgresql+asyncpg"
        query_params = dict(parse_qsl(parsed.query))
        if "sslmode" in query_params:
            ssl_mode = query_params.pop("sslmode")
            if ssl_mode in ("require", "verify-ca", "verify-full"):
                query_params["ssl"] = "require"
        query_params.pop("channel_binding", None)
        new_query = urlencode(query_params)
        return urlunparse(
            (scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )
    else:
        if scheme == "postgresql+asyncpg":
            scheme = "postgresql"
        query_params = dict(parse_qsl(parsed.query))
        query_params.pop("ssl", None)
        if "sslmode" not in query_params:
            query_params["sslmode"] = "require"
        new_query = urlencode(query_params)
        return urlunparse(
            (scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )



def build_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async engine with Neon-friendly pool settings (or SQLite for tests)."""
    url = normalize_db_url(database_url or settings.DATABASE_URL, is_async=True)
    kwargs = {
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "echo": settings.DEBUG,
    }
    if not url.startswith("sqlite"):
        kwargs["pool_size"] = settings.DB_POOL_SIZE
        kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

    return create_async_engine(url, **kwargs)


# Active engine & session factory singletons
engine: AsyncEngine = build_engine()
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session():
    """FastAPI dependency yielding a scoped async session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def test_connection(url: str) -> tuple[bool, str]:
    """Test connecting to a target PostgreSQL database URL."""
    temp_url = normalize_db_url(url, is_async=True)
    temp_engine = create_async_engine(temp_url, pool_pre_ping=True)
    try:
        async with temp_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "Connection successful."
    except Exception as exc:
        logger.warning("Database test connection failed: %s", exc)
        return False, str(exc)
    finally:
        await temp_engine.dispose()


def run_migrations_sync(direct_url: str | None = None) -> None:
    """Run Alembic upgrade head programmatically."""
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    target_url = normalize_db_url(
        direct_url or settings.DIRECT_DATABASE_URL or settings.DATABASE_URL,
        is_async=False,
    )
    alembic_cfg.set_main_option("sqlalchemy.url", target_url)
    command.upgrade(alembic_cfg, "head")


async def update_database_connection(new_url: str, new_direct_url: str | None = None) -> None:
    """Safely test, migrate, persist to .env, and rebind running engine."""
    global engine, async_session_factory

    # 1. Test connectivity
    ok, err = await test_connection(new_url)
    if not ok:
        raise ValueError(f"Cannot connect to database: {err}")

    # 2. Update .env file
    env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        content = re.sub(
            r"^DATABASE_URL=.*$", f"DATABASE_URL={new_url}", content, flags=re.MULTILINE
        )
        if new_direct_url:
            content = re.sub(
                r"^DIRECT_DATABASE_URL=.*$",
                f"DIRECT_DATABASE_URL={new_direct_url}",
                content,
                flags=re.MULTILINE,
            )
        env_path.write_text(content, encoding="utf-8")

    # 3. Update active settings
    settings.DATABASE_URL = new_url
    if new_direct_url:
        settings.DIRECT_DATABASE_URL = new_direct_url

    # 4. Run migrations
    run_migrations_sync(new_direct_url or new_url)

    # 5. Dispose old engine and rebind with new URL
    old_engine = engine
    new_engine = build_engine(new_url)
    engine = new_engine
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    await old_engine.dispose()
    logger.info("Database engine successfully rebound to new connection.")


async def check_db_connection() -> bool:
    """Verify database connectivity with retries for Neon cold starts."""
    for attempt in range(1, _CONNECT_RETRIES + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning(
                "DB connection attempt %d/%d failed: %s",
                attempt,
                _CONNECT_RETRIES,
                exc,
            )
            if attempt < _CONNECT_RETRIES:
                await asyncio.sleep(_CONNECT_RETRY_DELAY)
    return False
