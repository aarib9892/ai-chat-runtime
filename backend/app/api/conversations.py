import asyncio
import json
import logging
from uuid import UUID
from app.runtime.concurrency import agent_semaphore
import asyncpg
from app.config.settings import AGENT_QUEUE_TIMEOUT_SECONDS
from app.db.database import get_pool
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.errors import (
    ConversationBusyError,
    ConversationNotFoundError,
    RateLimitedError,
    ServerBusyError,
)
from app.repositories.agent_step_repository import get_agent_steps_for_messages
from app.repositories.conversation_repository import (
    create_conversation,
    get_conversation,
    touch_conversation,
    list_conversations,
    update_conversation_title,
)
from app.runtime.rate_limit import ask_rate_limiter

from app.repositories.document_repository import (
    create_message_sources,
    get_message_sources,
)
from app.repositories.message_repository import (
    create_message,
    get_messages,
)
from app.repositories.tool_call_repository import get_tool_calls_for_messages

from app.repositories.summary_repository import (
    get_conversation_summary,
    update_conversation_summary,
)
from app.schemas.conversation import ConversationCreate, MessageCreate, AskRequest
from app.services.context_service import build_context
from app.services.llm_service import stream_llm, stream_static_response
from app.services.retrieval_service import build_rag_message, retrieve_chunks
from app.services.summary_service import (
    generate_updated_summary,
    plan_summary_update,
)
from app.services.token_service import count_text_tokens

router = APIRouter()
logger = logging.getLogger(__name__)
NO_RELEVANT_EVIDENCE_MESSAGE = (
    "I couldn't find relevant information in the selected "
    "document to answer that question."
)


def parse_json_value(value):
    if value is None:
        return None

    if isinstance(value, str):
        return json.loads(value)

    return value


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
async def get_conversation_endpoint(
    conversation_id: UUID,
):
    conversation = await get_conversation(conversation_id)

    if not conversation:
        raise ConversationNotFoundError()

    messages = await get_messages(conversation_id)

    assistant_messages = [
        message for message in messages if message["role"] == "assistant"
    ]

    assistant_message_ids = [message["id"] for message in assistant_messages]

    # -----------------------------
    # Load persisted tool calls
    # -----------------------------

    tool_call_rows, agent_step_rows = await asyncio.gather(
        get_tool_calls_for_messages(assistant_message_ids),
        get_agent_steps_for_messages(assistant_message_ids),
    )
    tool_calls_by_message = {}
    agent_steps_by_message = {}

    for row in tool_call_rows:
        message_id = row["message_id"]

        tool_calls_by_message.setdefault(
            message_id,
            [],
        ).append(
            {
                "call_id": row["call_id"],
                "name": row["tool_name"],
                "arguments": parse_json_value(row["arguments"]),
                "step": row["step_number"],
                "result": parse_json_value(row["result"]),
                "status": row["status"],
                "error": row["error"],
            }
        )
    for row in agent_step_rows:
        message_id = row["message_id"]

        agent_steps_by_message.setdefault(
            message_id,
            [],
        ).append(
            {
                "step": row["step_number"],
                "response_id": row["provider_response_id"],
                "status": row["status"],
                "outcome": row["outcome"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
            }
        )

    # -----------------------------
    # Load persisted RAG sources
    # -----------------------------

    sources_by_message = await asyncio.gather(
        *(get_message_sources(message["id"]) for message in assistant_messages)
    )

    sources_map = {
        message["id"]: sources
        for message, sources in zip(
            assistant_messages,
            sources_by_message,
        )
    }

    # -----------------------------
    # Build API messages
    # -----------------------------

    response_messages = []

    for message in messages:
        message_data = dict(message)

        message_data["sources"] = sources_map.get(
            message["id"],
            [],
        )
        message_data["agent_steps"] = agent_steps_by_message.get(
            message["id"],
            [],
        )

        message_data["tool_calls"] = tool_calls_by_message.get(
            message["id"],
            [],
        )

        response_messages.append(message_data)

    return {
        **conversation,
        "messages": response_messages,
    }


@router.post("/conversations/{conversation_id}/ask")
async def ask_conversation(
    conversation_id: UUID, payload: AskRequest, request: Request
):
    client_ip = request.client.host if request.client else "unknown"
    allowed = await ask_rate_limiter.allow(client_ip)

    if not allowed:
        raise RateLimitedError()
    conversation = await get_conversation(conversation_id)

    if conversation is None:
        raise ConversationNotFoundError()

    agent_slot_acquired = False
    agent_slot_transferred = False

    try:
        # --------------------------------
        # Global concurrency guard
        # --------------------------------

        try:
            await asyncio.wait_for(
                agent_semaphore.acquire(),
                timeout=(AGENT_QUEUE_TIMEOUT_SECONDS),
            )

            agent_slot_acquired = True

        except TimeoutError:
            raise ServerBusyError()

        # --------------------------------
        # Create user + assistant placeholder
        # --------------------------------

        pool = get_pool()

        async with pool.acquire() as connection:
            try:
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

                    await touch_conversation(
                        conversation_id,
                        connection=connection,
                    )

            except asyncpg.UniqueViolationError as exc:
                if exc.constraint_name == "uq_one_streaming_assistant_per_conversation":
                    raise (ConversationBusyError()) from exc

                raise

        # --------------------------------
        # Summary/context work
        # --------------------------------

        messages = await get_messages(conversation_id)

        summary = await get_conversation_summary(conversation_id)

        summary_plan = plan_summary_update(
            messages=messages,
            summary=summary,
            current_message_id=user_message["id"],
        )

        if summary_plan.should_summarize:
            try:
                existing_summary = summary["summary"] if summary else None
                updated_summary = await generate_updated_summary(
                    existing_summary=existing_summary,
                    messages_to_summarize=summary_plan.messages_to_summarize,
                )
                summary = await update_conversation_summary(
                    conversation_id=conversation_id,
                    summary=updated_summary,
                    through_message_id=summary_plan.through_message_id,
                    token_count=count_text_tokens(updated_summary),
                )
            except Exception:
                logger.exception(
                    "conversation_summary_update_failed",
                    extra={"conversation_id": str(conversation_id)},
                )

        # --------------------------------
        # RAG
        # --------------------------------

        retrieved_chunks = []
        rag_message = None

        if payload.document_id is not None:
            retrieved_chunks = await retrieve_chunks(
                query=payload.message,
                document_id=payload.document_id,
                top_k=3,
            )

            if not retrieved_chunks:
                # No agent/model run needed.
                # endpoint finally will release
                # the semaphore.

                return StreamingResponse(
                    stream_static_response(
                        text=(NO_RELEVANT_EVIDENCE_MESSAGE),
                        user_message_id=user_message["id"],
                        assistant_message_id=assistant_message["id"],
                        conversation_id=conversation_id,
                    ),
                    media_type=("application/x-ndjson"),
                )

            await create_message_sources(
                message_id=assistant_message["id"],
                chunks=retrieved_chunks,
            )

            rag_message = build_rag_message(retrieved_chunks)

        # --------------------------------
        # Context
        # --------------------------------

        context = build_context(
            messages,
            current_message_id=user_message["id"],
            summary=summary,
            rag_message=rag_message,
        )

        # --------------------------------
        # Transfer semaphore ownership
        # to streaming generator
        # --------------------------------

        agent_slot_transferred = True

        return StreamingResponse(
            stream_llm(
                context=context,
                user_message_id=user_message["id"],
                assistant_message_id=assistant_message["id"],
                conversation_id=conversation_id,
                retrieved_chunks=retrieved_chunks,
                release_agent_slot=True,
            ),
            media_type=("application/x-ndjson"),
        )

    finally:
        # If stream_llm did NOT take ownership,
        # release here.

        if agent_slot_acquired and not agent_slot_transferred:
            agent_semaphore.release()


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
