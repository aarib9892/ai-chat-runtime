from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas.document import (
    DocumentCreate,
    DocumentSearchRequest,
)

from app.repositories.document_repository import (
    create_document,
    get_document,
    get_document_chunks,
    replace_document_chunks,
    update_chunk_embeddings,
)
from app.services.chunking_service import chunk_text
from app.services.embedding_service import (
    embed_texts,
)
from app.services.retrieval_service import build_retrieval_context, retrieve_chunks

router = APIRouter()


@router.post("/documents")
async def create_document_endpoint(
    payload: DocumentCreate,
):
    document = await create_document(
        filename=payload.filename,
        content=payload.content,
        mime_type=payload.mime_type,
    )

    return document


@router.post("/documents/{document_id}/chunks")
async def chunk_document_endpoint(
    document_id: UUID,
):
    document = await get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    chunks = chunk_text(document["content"])

    await replace_document_chunks(
        document_id=document_id,
        chunks=chunks,
    )

    return {
        "document_id": document_id,
        "chunk_count": len(chunks),
        "total_tokens": sum(chunk.token_count for chunk in chunks),
    }


@router.post("/documents/{document_id}/embeddings")
async def embed_document_endpoint(
    document_id: UUID,
):
    chunks = await get_document_chunks(document_id)

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="Document has no chunks",
        )

    texts = [chunk["content"] for chunk in chunks]

    embeddings = await embed_texts(texts)
    if len(chunks) != len(embeddings):
        raise RuntimeError("Embedding count mismatch")
    await update_chunk_embeddings(
        chunks=chunks,
        embeddings=embeddings,
    )

    return {
        "document_id": document_id,
        "chunk_count": len(chunks),
        "embedding_count": len(embeddings),
        "dimensions": (len(embeddings[0]) if embeddings else 0),
    }


@router.post("/documents/search")
async def search_documents(
    payload: DocumentSearchRequest,
):
    results = await retrieve_chunks(
        query=payload.query,
        document_id=payload.document_id,
        top_k=payload.limit,
    )
    context = build_retrieval_context(results)

    return {
        "query": payload.query,
        "results": [
            {
                "id": result.id,
                "document_id": result.document_id,
                "filename": result.filename,
                "chunk_index": result.chunk_index,
                "content": result.content,
                "token_count": result.token_count,
                "similarity": result.similarity,
            }
            for result in results
        ],
        "context": context,
    }
