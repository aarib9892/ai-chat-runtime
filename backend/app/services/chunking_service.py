from dataclasses import dataclass

from app.services.token_service import (
    decode_tokens,
    encode_text,
)

MAX_CHUNK_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 80


@dataclass
class TextChunk:
    chunk_index: int
    content: str
    token_count: int


def chunk_text(
    document_text: str,
    chunk_size: int = MAX_CHUNK_TOKENS,
    overlap: int = CHUNK_OVERLAP_TOKENS,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    tokens = encode_text(document_text)

    if len(tokens) == 0:
        return []

    chunks = []
    start = 0
    chunk_index = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_break = tokens[start:end]
        chunk_content = decode_tokens(chunk_break)
        chunks.append(
            TextChunk(
                chunk_index=chunk_index,
                content=chunk_content,
                token_count=len(chunk_break),
            )
        )
        if end == len(tokens):
            break
        chunk_index += 1
        start = end - overlap
    return chunks
