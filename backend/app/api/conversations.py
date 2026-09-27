from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.repositories.conversation_repository import (
    create_conversation,
    get_conversation,
    touch_conversation,
    list_conversations,
)

from app.repositories.message_repository import (
    create_message,
    get_messages,
)

from app.schemas.conversation import ConversationCreate, MessageCreate, AskRequest
from app.services.context_service import build_context
from app.services.llm_service import stream_llm

router = APIRouter()


@router.post("/conversations")
async def create_conversation_endpoint(payload: ConversationCreate):
    conversation = await create_conversation(title=payload.title)
    return conversation


@router.post("/conversations/{conversation_id}/messages")
async def create_conversation_message_endpoint(
    conversation_id: UUID, payload: MessageCreate
):
    conversation = await get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation Not Found")

    message = await create_message(
        conversation_id=conversation_id, role=payload.role, content=payload.content
    )

    await touch_conversation(conversation_id)
    return message


@router.get("/conversations/{conversation_id}")
async def get_conversation_endpoint(conversation_id: UUID):
    conversation = await get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation Not Found")
    messages = await get_messages(conversation_id)
    return {**conversation, "messages": messages}


@router.post("/conversations/{conversation_id}/ask")
async def ask_conversation(conversation_id: UUID, payload: AskRequest):
    conversation = await get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation Not Found",
        )

    await create_message(
        conversation_id=conversation_id,
        role="user",
        content=payload.message,
        status="completed",
    )
    await touch_conversation(conversation_id)
    messages = await get_messages(conversation_id)

    context = build_context(messages)
    assistant_message = await create_message(
        conversation_id=conversation_id,
        role="assistant",
        content="",
        status="streaming",
    )
    return StreamingResponse(
        stream_llm(
            context=context,
            assistant_message_id=assistant_message["id"],
            conversation_id=conversation_id,
        ),
        media_type="application/x-ndjson",
    )


@router.get("/conversations")
async def list_conversations_endpoint():
    return {"conversations": await list_conversations()}


# curl \
#   http://127.0.0.1:8000/api/conversations/7c11d5df-a210-46e7-af35-ff60890c1d2d
# curl \
#   -X POST \
#   http://127.0.0.1:8000/api/conversations/7c11d5df-a210-46e7-af35-ff60890c1d2d/messages \
#   -H "Content-Type: application/json" \
#   -d '{
#     "role": "user",
#     "content": "My name is Raj"
#   }'
