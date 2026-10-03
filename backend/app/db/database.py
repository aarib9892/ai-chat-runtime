import os
import asyncpg
from dotenv import load_dotenv
from pgvector.asyncpg import register_vector

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
_pool: asyncpg.Pool | None = None


async def connect_db() -> None:
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL, min_size=1, max_size=5, init=init_connection
    )

    async with _pool.acquire() as connection:
        result = await connection.fetchval("SELECT 1")
    print("Database connected", result)


async def init_connection(
    connection: asyncpg.Connection,
):
    await register_vector(connection)


def get_pool() -> asyncpg.pool:
    if _pool is None:
        raise RuntimeError("Database Pool has not been initialized")
    return _pool


async def close_db() -> None:
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None
    print("Database Connection Pool Closed")
