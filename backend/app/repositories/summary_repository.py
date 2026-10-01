from uuid import UUID
from app.db.database import get_pool


async def get_conversation_summary(conversation_id: UUID):
    pool = get_pool()

    row = await pool.fetchrow(
        """
        SELECT
            conversation_id,
            summary,
            through_message_id,
            token_count,
            updated_at
        FROM conversation_summaries
        WHERE conversation_id = $1
        """,
        conversation_id,
    )

    return None if row is None else dict(row)


async def update_conversation_summary(
    conversation_id: UUID, summary: str, through_message_id: UUID, token_count: int
):
    pool = get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO conversation_summaries (
            conversation_id,
            summary,
            through_message_id,
            token_count
        )
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (conversation_id) DO UPDATE
        SET
            summary = EXCLUDED.summary,
            through_message_id = EXCLUDED.through_message_id,
            token_count = EXCLUDED.token_count,
            updated_at = NOW()
        RETURNING
            conversation_id,
            summary,
            through_message_id,
            token_count
        """,
        conversation_id,
        summary,
        through_message_id,
        token_count,
    )
    return dict(row)
