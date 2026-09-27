# app/repositories/message_repository.py

from uuid import UUID

from app.db.database import get_pool


async def create_message(
    conversation_id: UUID,
    role: str,
    content: str,
    status: str = "completed",
    provider_response_id: str | None = None,
):
    pool = get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO messages (
            conversation_id,
            role,
            content,
            status,
            provider_response_id
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING
            id,
            conversation_id,
            role,
            content,
            status,
            provider_response_id,
            created_at
        """,
        conversation_id,
        role,
        content,
        status,
        provider_response_id,
    )

    return dict(row)


async def get_messages(
    conversation_id: UUID,
):
    pool = get_pool()

    rows = await pool.fetch(
        """
        SELECT
            id,
            conversation_id,
            role,
            content,
            status,
            provider_response_id,
            created_at
        FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at ASC
        """,
        conversation_id,
    )

    return [dict(row) for row in rows]


async def update_message(
    message_id: UUID,
    content: str,
    status: str,
    provider_response_id: str | None = None,
):
    pool = get_pool()

    row = await pool.fetchrow(
        """
        UPDATE messages
        SET
            content = $2,
            status = $3,
            provider_response_id = $4
        WHERE id = $1
        RETURNING
            id,
            conversation_id,
            role,
            content,
            status,
            provider_response_id,
            created_at
        """,
        message_id,
        content,
        status,
        provider_response_id,
    )

    if row is None:
        return None

    return dict(row)
