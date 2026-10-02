from fastapi import APIRouter

from app.schemas.document import (
    DocumentCreate,
)

from app.repositories.document_repository import (
    create_document,
)

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
