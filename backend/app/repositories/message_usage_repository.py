from uuid import UUID

from app.db.database import get_pool


async def upsert_message_usage(
    message_id: UUID,
    model: str,
    model_calls: int,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    duration_ms: float,
    estimated_cost_usd: float,
    connection=None,
):
    db = connection or get_pool()

    return await db.fetchrow(
        """
        INSERT INTO message_usage (
            message_id,
            model,
            model_calls,
            input_tokens,
            output_tokens,
            total_tokens,
            duration_ms,
            estimated_cost_usd
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8
        )

        ON CONFLICT (message_id)
        DO UPDATE SET
            model = EXCLUDED.model,
            model_calls =
                EXCLUDED.model_calls,
            input_tokens =
                EXCLUDED.input_tokens,
            output_tokens =
                EXCLUDED.output_tokens,
            total_tokens =
                EXCLUDED.total_tokens,
            duration_ms =
                EXCLUDED.duration_ms,
            estimated_cost_usd =
                EXCLUDED.estimated_cost_usd,
            updated_at = NOW()

        RETURNING *
        """,
        message_id,
        model,
        model_calls,
        input_tokens,
        output_tokens,
        total_tokens,
        duration_ms,
        estimated_cost_usd,
    )
