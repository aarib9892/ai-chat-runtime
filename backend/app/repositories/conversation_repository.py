# app/repositories/conversation_repository.py

from uuid import UUID

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
    conversation_id: UUID,
):
    pool = get_pool()

    await pool.execute(
        """
        UPDATE conversations
        SET updated_at = NOW()
        WHERE id = $1
        """,
        conversation_id,
    )


async def list_conversations(limit: int = 50):
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT
            id,
            title,
            created_at,
            updated_at
        FROM conversations
        ORDER BY updated_at DESC
        LIMIT $1
        """,
        limit,
    )

    return [dict(row) for row in rows]
