import json
from uuid import UUID

from app.db.database import get_pool


async def create_tool_call(
    message_id: UUID,
    call_id: str,
    tool_name: str,
    arguments: dict,
    connection=None,
):
    db = connection or get_pool()

    return await db.fetchrow(
        """
        INSERT INTO message_tool_calls (
            message_id,
            call_id,
            tool_name,
            arguments,
            status
        )
        VALUES (
            $1,
            $2,
            $3,
            $4::jsonb,
            'running'
        )
        RETURNING
            id,
            message_id,
            call_id,
            tool_name,
            arguments,
            result,
            status,
            error,
            created_at,
            completed_at
        """,
        message_id,
        call_id,
        tool_name,
        json.dumps(arguments),
    )


async def complete_tool_call(
    message_id: UUID,
    call_id: str,
    result,
    connection=None,
):
    db = connection or get_pool()

    return await db.fetchrow(
        """
        UPDATE message_tool_calls
        SET
            result = $3::jsonb,
            status = 'completed',
            completed_at = NOW()
        WHERE message_id = $1
          AND call_id = $2
        RETURNING
            id,
            message_id,
            call_id,
            tool_name,
            arguments,
            result,
            status,
            error,
            created_at,
            completed_at
        """,
        message_id,
        call_id,
        json.dumps(result),
    )


async def fail_tool_call(
    message_id: UUID,
    call_id: str,
    error: str,
    connection=None,
):
    db = connection or get_pool()

    return await db.fetchrow(
        """
        UPDATE message_tool_calls
        SET
            status = 'error',
            error = $3,
            completed_at = NOW()
        WHERE message_id = $1
          AND call_id = $2
        RETURNING
            id,
            message_id,
            call_id,
            tool_name,
            arguments,
            result,
            status,
            error,
            created_at,
            completed_at
        """,
        message_id,
        call_id,
        error,
    )


async def get_tool_calls_for_messages(
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
            call_id,
            tool_name,
            arguments,
            result,
            status,
            error,
            created_at,
            completed_at
        FROM message_tool_calls
        WHERE message_id = ANY($1::uuid[])
        ORDER BY created_at ASC
        """,
        message_ids,
    )

    return [dict(row) for row in rows]
