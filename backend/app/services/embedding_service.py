from openai import AsyncOpenAI

from app.config.llm_config import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
)

client = AsyncOpenAI()


async def embed_text(
    text: str,
) -> list[float]:
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    embedding = response.data[0].embedding
    _validate_embedding_dimensions(embedding)
    return embedding


async def embed_texts(
    texts: list[str],
) -> list[list[float]]:

    if not texts:
        return []

    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    embeddings = [item.embedding for item in response.data]
    for embedding in embeddings:
        _validate_embedding_dimensions(embedding)
    return embeddings


def _validate_embedding_dimensions(embedding: list[float]) -> None:
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSIONS} embedding dimensions, "
            f"received {len(embedding)}"
        )
