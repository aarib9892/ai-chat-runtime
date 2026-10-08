from uuid import UUID

from app.db.database import get_pool


async def create_agent_step(
    message_id: UUID,
    step_number: int,
    connection=None,
):
    db = connection or get_pool()

    return await db.fetchrow(
        """
        INSERT INTO message_agent_steps (
            message_id,
            step_number,
            status
        )
        VALUES (
            $1,
            $2,
            'running'
        )
        ON CONFLICT (
            message_id,
            step_number
        )
        DO NOTHING
        RETURNING *
        """,
        message_id,
        step_number,
    )


async def set_agent_step_response_id(
    message_id: UUID,
    step_number: int,
    response_id: str,
    connection=None,
):
    db = connection or get_pool()

    return await db.fetchrow(
        """
        UPDATE message_agent_steps
        SET provider_response_id = $3
        WHERE message_id = $1
          AND step_number = $2
        RETURNING *
        """,
        message_id,
        step_number,
        response_id,
    )


async def complete_agent_step(
    message_id: UUID,
    step_number: int,
    outcome: str,
    connection=None,
):
    db = connection or get_pool()

    return await db.fetchrow(
        """
        UPDATE message_agent_steps
        SET
            status = 'completed',
            outcome = $3,
            completed_at = NOW()
        WHERE message_id = $1
          AND step_number = $2
        RETURNING *
        """,
        message_id,
        step_number,
        outcome,
    )


async def mark_agent_step_status(
    message_id: UUID,
    step_number: int,
    status: str,
    connection=None,
):
    if status not in {
        "incomplete",
        "stopped",
        "error",
    }:
        raise ValueError(f"Invalid terminal agent step status: {status}")

    db = connection or get_pool()

    return await db.fetchrow(
        """
        UPDATE message_agent_steps
        SET
            status = $3,
            completed_at = NOW()
        WHERE message_id = $1
          AND step_number = $2
        RETURNING *
        """,
        message_id,
        step_number,
        status,
    )


async def get_agent_steps_for_messages(
    message_ids: list[UUID],
) -> list[dict]:
    if not message_ids:
        return []

    pool = get_pool()

    rows = await pool.fetch(
        """
        SELECT
            id,
            message_id,
            step_number,
            provider_response_id,
            status,
            outcome,
            started_at,
            completed_at
        FROM message_agent_steps
        WHERE message_id = ANY($1::uuid[])
        ORDER BY
            message_id,
            step_number ASC
        """,
        message_ids,
    )

    return [dict(row) for row in rows]
