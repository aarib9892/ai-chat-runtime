# app/repositories/conversation_repository.py

from uuid import UUID
import asyncpg
from app.db.database import get_pool


async def create_conversation(
    title: str | None = None,
):
    pool = get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO conversations (title)
        VALUES ($1)
        RETURNING
            id,
            title,
            created_at,
            updated_at
        """,
        title,
    )

    return dict(row)


async def get_conversation(
    conversation_id: UUID,
):
    pool = get_pool()

    row = await pool.fetchrow(
        """
        SELECT
            id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE id = $1
        """,
        conversation_id,
    )

    if row is None:
        return None

    return dict(row)


async def touch_conversation(
    conversation_id: UUID, connection: asyncpg.Connection | None = None
):
    db = connection or get_pool()

    await db.execute(
        """
        UPDATE conversations
        SET updated_at = NOW()
        WHERE id = $1
        """,
        conversation_id,
    )


async def list_conversations(
    limit: int = 50,
):
    pool = get_pool()

    rows = await pool.fetch(
        """
        SELECT
            c.id,
            c.title,
            c.created_at,
            c.updated_at
        FROM conversations c
        WHERE EXISTS (
            SELECT 1
            FROM messages m
            WHERE m.conversation_id = c.id
              AND m.role = 'user'
        )
        ORDER BY c.updated_at DESC
        LIMIT $1
        """,
        limit,
    )

    return [dict(row) for row in rows]


async def update_conversation_title(
    conversation_id: UUID,
    title: str,
    connection: asyncpg.Connection | None = None,
):
    db = connection or get_pool()

    row = await db.fetchrow(
        """
        UPDATE conversations
        SET
            title = $2
        WHERE id = $1
        RETURNING
            id,
            title,
            created_at,
            updated_at
        """,
        conversation_id,
        title,
    )

    return None if row is None else dict(row)
