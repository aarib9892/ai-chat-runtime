import asyncio
from uuid import UUID
from app.db.database import get_pool
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.repositories.conversation_repository import (
    create_conversation,
    get_conversation,
    touch_conversation,
    list_conversations,
    update_conversation_title,
)

from app.repositories.document_repository import (
    create_message_sources,
    get_message_sources,
)
from app.repositories.message_repository import (
    create_message,
    get_messages,
)

from app.repositories.summary_repository import (
    get_conversation_summary,
    update_conversation_summary,
)
from app.schemas.conversation import ConversationCreate, MessageCreate, AskRequest
from app.services.context_service import build_context
from app.services.llm_service import stream_llm, stream_static_response
from app.services.retrieval_service import build_rag_message, retrieve_chunks
from app.services.summary_service import (
    SUMMARY_TRIGGER_TOKENS,
    generate_updated_summary,
    plan_summary_update,
)
from app.services.token_service import count_text_tokens

router = APIRouter()
NO_RELEVANT_EVIDENCE_MESSAGE = (
    "I couldn't find relevant information in the selected "
    "document to answer that question."
)


def build_conversation_title(
    message: str,
    max_length: int = 60,
) -> str:
    title = " ".join(message.split())

    if len(title) <= max_length:
        return title

    return title[: max_length - 3].rstrip() + "..."


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
    assistant_messages = [
        message for message in messages if message["role"] == "assistant"
    ]
    sources_by_message = await asyncio.gather(
        *(get_message_sources(message["id"]) for message in assistant_messages)
    )
    for message, sources in zip(assistant_messages, sources_by_message):
        message["sources"] = sources
    return {**conversation, "messages": messages}


@router.post("/conversations/{conversation_id}/ask")
async def ask_conversation(conversation_id: UUID, payload: AskRequest):
    conversation = await get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation Not Found",
        )

    pool = get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():

            user_message = await create_message(
                conversation_id=conversation_id,
                role="user",
                content=payload.message,
                status="completed",
                connection=connection,
            )
            assistant_message = await create_message(
                conversation_id=conversation_id,
                role="assistant",
                content="",
                status="streaming",
                connection=connection,
            )
            if not conversation["title"]:
                await update_conversation_title(
                    conversation_id,
                    build_conversation_title(payload.message),
                    connection=connection,
                )

            await touch_conversation(conversation_id, connection=connection)
    messages = await get_messages(conversation_id)
    summary = await get_conversation_summary(conversation_id)
    summary_plan = plan_summary_update(
        messages=messages,
        summary=summary,
        current_message_id=user_message["id"],
    )
    print("=== SUMMARY PLAN DEBUG ===")
    print("Summary exists:", summary is not None)

    if summary:
        print(
            "Existing boundary:",
            summary["through_message_id"],
        )

    print(
        "Unsummarized tokens:",
        summary_plan.unsummarized_tokens,
    )

    print(
        "Trigger:",
        SUMMARY_TRIGGER_TOKENS,
    )

    print(
        "Should summarize:",
        summary_plan.should_summarize,
    )

    print(
        "Messages to summarize:",
        len(summary_plan.messages_to_summarize),
    )

    print(
        "Recent messages:",
        len(summary_plan.recent_messages),
    )
    if summary_plan.should_summarize:
        try:

            existing_summary_text = summary["summary"] if summary else None
            updated_summary = await generate_updated_summary(
                existing_summary=existing_summary_text,
                messages_to_summarize=summary_plan.messages_to_summarize,
            )
            summary_token_count = count_text_tokens(updated_summary)
            summary = await update_conversation_summary(
                conversation_id=conversation_id,
                summary=updated_summary,
                through_message_id=summary_plan.through_message_id,
                token_count=summary_token_count,
            )
            print("=== SUMMARY UPDATE ===")

            print(
                "Messages summarized:",
                len(summary_plan.messages_to_summarize),
            )

            print(
                "Source tokens:",
                summary_plan.summarize_tokens,
            )

            print(
                "Summary tokens:",
                summary["token_count"],
            )

            print(
                "New boundary:",
                summary["through_message_id"],
            )
        except Exception as error:
            print(
                "Summary update failed:",
                repr(error),
            )
    retrieved_chunks = []
    rag_message = None

    if payload.document_id is not None:
        retrieved_chunks = await retrieve_chunks(
            query=payload.message,
            document_id=payload.document_id,
            top_k=3,
        )

        if not retrieved_chunks:
            return StreamingResponse(
                stream_static_response(
                    text=NO_RELEVANT_EVIDENCE_MESSAGE,
                    user_message_id=user_message["id"],
                    assistant_message_id=assistant_message["id"],
                    conversation_id=conversation_id,
                ),
                media_type="application/x-ndjson",
            )

        await create_message_sources(
            message_id=assistant_message["id"],
            chunks=retrieved_chunks,
        )

        rag_message = build_rag_message(retrieved_chunks)

    context = build_context(
        messages,
        current_message_id=user_message["id"],
        summary=summary,
        rag_message=rag_message,
    )

    return StreamingResponse(
        stream_llm(
            context=context,
            user_message_id=user_message["id"],
            assistant_message_id=assistant_message["id"],
            conversation_id=conversation_id,
            retrieved_chunks=retrieved_chunks,
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
