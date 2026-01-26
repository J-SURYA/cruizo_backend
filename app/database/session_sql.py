from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import Any
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.memory import MemorySaver


from app.core.config import settings
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URL, echo=False, pool_pre_ping=True
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


_pg_pool: Any = None
_checkpointer: Any = None


async def initialize_checkpointer():
    """
    Initializes the LangGraph PostgreSQL checkpointer with connection pooling.
    
    Args:
        None

    Returns:
        None
    """
    global _pg_pool, _checkpointer

    if _checkpointer is not None:
        return

    try:
        _pg_pool = AsyncConnectionPool(
            conninfo=settings.POSTGRES_CONNECTION_STRING,
            max_size=20,
            min_size=5,
            open=False,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
            },
        )
        await _pg_pool.open()
        _checkpointer = AsyncPostgresSaver(_pg_pool)
        await _checkpointer.setup()

    except Exception as e:
        logger.error(
            f"Failed to initialize PostgreSQL checkpointer: {e}, Falling back to in-memory checkpointer"
        )
        if _pg_pool is not None:
            await _pg_pool.close()
            _pg_pool = None

        _checkpointer = MemorySaver()


async def connect_to_postgres():
    """
    Initializes DB tables and required sequences.
    
    Args:
        None

    Returns:
        None
    """
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)
        # await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # await conn.run_sync(Base.metadata.create_all)
        # await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS u_id_seq START 1"))
        pass


async def close_postgres_connection():
    """
    Closes PostgreSQL engine, connection pool, and checkpointer.
    
    Args:
        None

    Returns:
        None
    """
    global _pg_pool, _checkpointer

    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
        _checkpointer = None
        logger.info("PostgreSQL checkpointer connection pool closed")

    await engine.dispose()
