from app.db.database import get_pool


async def create_document(
    filename: str,
    content: str,
    mime_type: str | None = None,
):
    pool = get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO documents (
            filename,
            content,
            mime_type
        )
        VALUES ($1, $2, $3)

        RETURNING
            id,
            filename,
            mime_type,
            created_at
        """,
        filename,
        content,
        mime_type,
    )

    return dict(row)
