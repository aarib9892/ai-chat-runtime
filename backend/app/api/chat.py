from app.schemas.chat import ChatRequest
from app.services.llm_service import stream_llm
from fastapi import APIRouter
import asyncio
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post("/ask")
async def ask(request: ChatRequest):
    return StreamingResponse(
        stream_llm(request.messages), media_type="application/x-ndjson"
    )
