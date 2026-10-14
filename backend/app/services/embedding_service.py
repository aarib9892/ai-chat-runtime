from openai import AsyncOpenAI

from app.config.settings import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_text(
    text: str,
) -> list[float]:
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dimensions,
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
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )

    embeddings = [item.embedding for item in response.data]
    for embedding in embeddings:
        _validate_embedding_dimensions(embedding)
    return embeddings


def _validate_embedding_dimensions(embedding: list[float]) -> None:
    if len(embedding) != settings.embedding_dimensions:
        raise ValueError(
            f"Expected {settings.embedding_dimensions} embedding dimensions, "
            f"received {len(embedding)}"
        )
