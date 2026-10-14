import asyncio
from pathlib import Path

import asyncpg

from app.config.settings import settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


async def run_migrations():
    connection = await asyncpg.connect(settings.database_url)

    try:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS
            schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ
                    NOT NULL
                    DEFAULT NOW()
            )
            """)

        rows = await connection.fetch("""
            SELECT filename
            FROM schema_migrations
            """)

        applied = {row["filename"] for row in rows}

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        for path in migration_files:
            if path.name in applied:
                continue

            print(f"Applying migration: " f"{path.name}")

            sql = path.read_text(encoding="utf-8")

            async with connection.transaction():
                await connection.execute(sql)

                await connection.execute(
                    """
                    INSERT INTO
                    schema_migrations (
                        filename
                    )
                    VALUES ($1)
                    """,
                    path.name,
                )

            print(f"Applied: {path.name}")

    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
