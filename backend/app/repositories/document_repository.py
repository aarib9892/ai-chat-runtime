from uuid import UUID

from pgvector import Vector

from app.config.llm_config import EMBEDDING_MODEL
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


async def get_document(
    document_id: UUID,
):
    row = await get_pool().fetchrow(
        """
        SELECT
            id,
            filename,
            mime_type,
            content,
            created_at
        FROM documents
        WHERE id = $1
        """,
        document_id,
    )

    return None if row is None else dict(row)


async def replace_document_chunks(
    document_id: UUID,
    chunks,
):
    pool = get_pool()

    async with pool.acquire() as connection:
        async with connection.transaction():

            await connection.execute(
                """
                DELETE FROM document_chunks
                WHERE document_id = $1
                """,
                document_id,
            )

            for chunk in chunks:
                await connection.execute(
                    """
                    INSERT INTO document_chunks (
                        document_id,
                        chunk_index,
                        content,
                        token_count
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    document_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.token_count,
                )


async def get_document_chunks(
    document_id: UUID,
):
    pool = get_pool()

    rows = await pool.fetch(
        """
        SELECT
            id,
            document_id,
            chunk_index,
            content,
            token_count,
            created_at
        FROM document_chunks
        WHERE document_id = $1
        ORDER BY chunk_index ASC
        """,
        document_id,
    )

    return [dict(row) for row in rows]


async def update_chunk_embedding(
    chunk_id: UUID,
    embedding: list[float],
):
    pool = get_pool()

    row = await pool.fetchrow(
        """
        UPDATE document_chunks
        SET
            embedding = $2,
            embedding_model = $3,
            embedded_at = NOW()
        WHERE id = $1
        RETURNING
            id,
            document_id,
            chunk_index,
            token_count,
            embedding_model,
            embedded_at
        """,
        chunk_id,
        Vector(embedding),
        EMBEDDING_MODEL,
    )

    return None if row is None else dict(row)


async def update_chunk_embeddings(
    chunks: list[dict],
    embeddings: list[list[float]],
):
    if len(chunks) != len(embeddings):
        raise ValueError("Chunk and embedding counts do not match")

    pool = get_pool()

    async with pool.acquire() as connection:
        async with connection.transaction():

            for chunk, embedding in zip(
                chunks,
                embeddings,
            ):
                await connection.execute(
                    """
                    UPDATE document_chunks
                    SET
                        embedding = $2,
                        embedding_model = $3,
                        embedded_at = NOW()
                    WHERE id = $1
                    """,
                    chunk["id"],
                    Vector(embedding),
                    EMBEDDING_MODEL,
                )


async def search_document_chunks(
    query_embedding: list[float],
    limit: int = 5,
):
    pool = get_pool()

    rows = await pool.fetch(
        """
        SELECT
            id,
            document_id,
            chunk_index,
            content,
            token_count,

            embedding <=> $1 AS distance,

            1 - (embedding <=> $1) AS similarity

        FROM document_chunks

        WHERE embedding IS NOT NULL

        ORDER BY embedding <=> $1

        LIMIT $2
        """,
        Vector(query_embedding),
        limit,
    )

    return [dict(row) for row in rows]
