import asyncio
import json
from uuid import UUID
import logging
from app.config.settings import settings
from app.db.database import get_pool
from app.errors import AppError
from app.observability.cost import estimate_openai_cost_usd
from app.repositories.agent_step_repository import (
    complete_agent_step,
    create_agent_step,
    mark_agent_step_status,
    set_agent_step_response_id,
)
from app.runtime.concurrency import agent_semaphore
from app.repositories.conversation_repository import touch_conversation
from app.repositories.message_repository import update_message
from app.repositories.message_usage_repository import upsert_message_usage
from app.repositories.tool_call_repository import (
    complete_tool_call,
    create_tool_call,
    fail_tool_call,
)
from app.services.retrieval_service import RetrievedChunk
from app.services.agent_service import stream_agent
from app.services.agent_events import (
    AgentCompleted,
    AgentIncomplete,
    AgentResponseCreated,
    AgentStepCompleted,
    AgentStepStarted,
    AgentTextDelta,
    AgentToolCall,
    AgentToolError,
    AgentToolResult,
)

logger = logging.getLogger(__name__)


async def persist_assistant_result(
    assistant_message_id: UUID,
    conversation_id: UUID,
    content: str,
    status: str,
    provider_response_id: str | None,
):
    pool = get_pool()

    async with pool.acquire() as connection:
        async with connection.transaction():
            await update_message(
                message_id=assistant_message_id,
                content=content,
                status=status,
                provider_response_id=provider_response_id,
                connection=connection,
            )

            await touch_conversation(conversation_id, connection=connection)


async def stream_llm(
    context: list[dict],
    user_message_id: UUID,
    assistant_message_id: UUID,
    conversation_id: UUID,
    retrieved_chunks: list[RetrievedChunk] | None = None,
    release_agent_slot: bool = False,
):
    full_response = ""
    provider_response_id: str | None = None
    active_agent_step: int | None = None
    logger.info(
        "assistant_stream_started",
        extra={
            "conversation_id": str(conversation_id),
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
        },
    )

    try:
        # ---------------------------------
        # Application message identity
        # ---------------------------------

        yield json.dumps(
            {
                "type": "message_ids",
                "user_message_id": str(user_message_id),
                "assistant_message_id": str(assistant_message_id),
            }
        ) + "\n"

        # ---------------------------------
        # RAG provenance
        # ---------------------------------

        if retrieved_chunks:
            yield json.dumps(
                {
                    "type": "sources",
                    "sources": [
                        {
                            "document_id": str(chunk.document_id),
                            "filename": chunk.filename,
                            "chunk_index": chunk.chunk_index,
                            "similarity": chunk.similarity,
                        }
                        for chunk in retrieved_chunks
                    ],
                }
            ) + "\n"

        input_items = list(context)

        # =================================
        # AGENT RUNTIME
        # =================================

        async for event in stream_agent(input_items=input_items):

            # -----------------------------
            # Step started
            # -----------------------------

            if isinstance(
                event,
                AgentStepStarted,
            ):
                logger.info(
                    "agent_step_started",
                    extra={
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id),
                        "step": event.step,
                    },
                )
                active_agent_step = event.step
                await create_agent_step(
                    message_id=assistant_message_id,
                    step_number=event.step,
                )
                yield json.dumps(
                    {
                        "type": "agent_step_started",
                        "step": event.step,
                    }
                ) + "\n"

            # -----------------------------
            # Provider response ID
            # -----------------------------

            elif isinstance(
                event,
                AgentResponseCreated,
            ):
                provider_response_id = event.response_id
                await set_agent_step_response_id(
                    message_id=assistant_message_id,
                    step_number=event.step,
                    response_id=event.response_id,
                )

                yield json.dumps(
                    {
                        "type": "response_id",
                        "response_id": event.response_id,
                    }
                ) + "\n"

            # -----------------------------
            # Visible text
            # -----------------------------

            elif isinstance(
                event,
                AgentTextDelta,
            ):
                full_response += event.delta

                yield json.dumps(
                    {
                        "type": "delta",
                        "delta": event.delta,
                    }
                ) + "\n"

            # -----------------------------
            # Tool requested
            # -----------------------------

            elif isinstance(
                event,
                AgentToolCall,
            ):
                logger.info(
                    "agent_tool_started",
                    extra={
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id),
                        "step": event.step,
                        "tool_name": event.tool_name,
                        "call_id": event.call_id,
                    },
                )
                await create_tool_call(
                    message_id=assistant_message_id,
                    call_id=event.call_id,
                    tool_name=event.tool_name,
                    arguments=event.arguments,
                    step_number=event.step,
                )

                yield json.dumps(
                    {
                        "type": "tool_call",
                        "call_id": event.call_id,
                        "name": event.tool_name,
                        "step": event.step,
                        "arguments": event.arguments,
                    }
                ) + "\n"

            # -----------------------------
            # Tool succeeded
            # -----------------------------

            elif isinstance(
                event,
                AgentToolResult,
            ):
                logger.info(
                    "agent_tool_completed",
                    extra={
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id),
                        "step": event.step,
                        "tool_name": event.tool_name,
                        "call_id": event.call_id,
                        "status": "completed",
                    },
                )
                await complete_tool_call(
                    message_id=assistant_message_id,
                    call_id=event.call_id,
                    result=event.result,
                )

                yield json.dumps(
                    {
                        "type": "tool_result",
                        "call_id": event.call_id,
                        "name": event.tool_name,
                        "status": "completed",
                        "result": event.result,
                    }
                ) + "\n"

            # -----------------------------
            # Tool failed
            # -----------------------------

            elif isinstance(
                event,
                AgentToolError,
            ):
                logger.warning(
                    "agent_tool_failed",
                    extra={
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id),
                        "step": event.step,
                        "tool_name": event.tool_name,
                        "call_id": event.call_id,
                        "status": "error",
                        "reason": event.error,
                    },
                )
                await fail_tool_call(
                    message_id=assistant_message_id,
                    call_id=event.call_id,
                    error=event.error,
                )

                yield json.dumps(
                    {
                        "type": "tool_error",
                        "call_id": event.call_id,
                        "name": event.tool_name,
                        "error": event.error,
                    }
                ) + "\n"

            # -----------------------------
            # Agent step finished
            # -----------------------------

            elif isinstance(
                event,
                AgentStepCompleted,
            ):

                await complete_agent_step(
                    message_id=assistant_message_id,
                    step_number=event.step,
                    outcome=event.outcome,
                    duration_ms=event.duration_ms,
                    input_tokens=event.input_tokens,
                    output_tokens=event.output_tokens,
                    total_tokens=event.total_tokens,
                )
                yield json.dumps(
                    {
                        "type": "agent_step_completed",
                        "step": event.step,
                        "outcome": event.outcome,
                    }
                ) + "\n"
                active_agent_step = None

                logger.info(
                    "agent_step_completed",
                    extra={
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id),
                        "step": event.step,
                        "outcome": event.outcome,
                        "duration_ms": round(
                            event.duration_ms,
                            2,
                        ),
                        "input_tokens": event.input_tokens,
                        "output_tokens": event.output_tokens,
                        "total_tokens": event.total_tokens,
                    },
                )

            # -----------------------------
            # Agent incomplete
            # -----------------------------

            elif isinstance(
                event,
                AgentIncomplete,
            ):
                logger.warning(
                    "agent_incomplete",
                    extra={
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id),
                        "step": event.step,
                        "status": "incomplete",
                        "reason": event.reason,
                    },
                )
                if event.response_id:
                    provider_response_id = event.response_id
                await mark_agent_step_status(
                    message_id=assistant_message_id,
                    step_number=event.step,
                    status="incomplete",
                )

                await persist_assistant_result(
                    assistant_message_id=assistant_message_id,
                    conversation_id=conversation_id,
                    content=full_response,
                    status="incomplete",
                    provider_response_id=provider_response_id,
                )

                yield json.dumps(
                    {
                        "type": "incomplete",
                        "reason": event.reason,
                    }
                ) + "\n"

                return

            # -----------------------------
            # Agent completed
            # -----------------------------

            elif isinstance(
                event,
                AgentCompleted,
            ):
                provider_response_id = event.response_id

                if not full_response:
                    full_response = event.final_text

                await persist_assistant_result(
                    assistant_message_id=assistant_message_id,
                    conversation_id=conversation_id,
                    content=full_response,
                    status="completed",
                    provider_response_id=provider_response_id,
                )

                estimated_cost = estimate_openai_cost_usd(
                    input_tokens=event.input_tokens,
                    output_tokens=event.output_tokens,
                )
                await upsert_message_usage(
                    message_id=assistant_message_id,
                    model=settings.openai_model,
                    model_calls=event.total_steps,
                    input_tokens=event.input_tokens,
                    output_tokens=event.output_tokens,
                    total_tokens=event.total_tokens,
                    duration_ms=event.duration_ms,
                    estimated_cost_usd=estimated_cost,
                )
                yield json.dumps(
                    {
                        "type": "done",
                    }
                ) + "\n"
                logger.info(
                    "agent_completed",
                    extra={
                        "conversation_id": str(conversation_id),
                        "assistant_message_id": str(assistant_message_id),
                        "response_id": event.response_id,
                        "status": "completed",
                        "duration_ms": round(
                            event.duration_ms,
                            2,
                        ),
                        "input_tokens": event.input_tokens,
                        "output_tokens": event.output_tokens,
                        "total_tokens": event.total_tokens,
                        "estimated_cost_usd": round(
                            estimated_cost,
                            8,
                        ),
                    },
                )

                return

        # Defensive case
        raise RuntimeError("Agent stream ended without " "a terminal event.")

    except asyncio.CancelledError:
        if active_agent_step is not None:
            await mark_agent_step_status(
                message_id=assistant_message_id,
                step_number=active_agent_step,
                status="stopped",
            )
        await persist_assistant_result(
            assistant_message_id=assistant_message_id,
            conversation_id=conversation_id,
            content=full_response,
            status="stopped",
            provider_response_id=provider_response_id,
        )
        logger.info(
            "assistant_stream_cancelled",
            extra={
                "conversation_id": str(conversation_id),
                "assistant_message_id": str(assistant_message_id),
                "status": "stopped",
            },
        )

        raise

    except GeneratorExit:
        if active_agent_step is not None:
            await mark_agent_step_status(
                message_id=assistant_message_id,
                step_number=active_agent_step,
                status="stopped",
            )

        await persist_assistant_result(
            assistant_message_id=assistant_message_id,
            conversation_id=conversation_id,
            content=full_response,
            status="stopped",
            provider_response_id=provider_response_id,
        )
        logger.info(
            "assistant_stream_closed",
            extra={
                "conversation_id": str(conversation_id),
                "assistant_message_id": str(assistant_message_id),
                "status": "stopped",
            },
        )

        raise

    except AppError as exc:
        logger.warning(
            "assistant_stream_app_error",
            extra={
                "conversation_id": str(conversation_id),
                "assistant_message_id": str(assistant_message_id),
                "status": "error",
                "reason": exc.code.value,
            },
            exc_info=True,
        )

        if active_agent_step is not None:
            await mark_agent_step_status(
                message_id=assistant_message_id,
                step_number=active_agent_step,
                status="error",
            )

        await persist_assistant_result(
            assistant_message_id=assistant_message_id,
            conversation_id=conversation_id,
            content=full_response,
            status="error",
            provider_response_id=provider_response_id,
        )

        yield json.dumps(
            {
                "type": "error",
                "code": exc.code.value,
                "message": exc.public_message,
                "retryable": exc.retryable,
            }
        ) + "\n"

        return

    except Exception:
        logger.exception(
            "assistant_stream_failed",
            extra={
                "conversation_id": str(conversation_id),
                "assistant_message_id": str(assistant_message_id),
                "status": "error",
            },
        )

        if active_agent_step is not None:
            await mark_agent_step_status(
                message_id=assistant_message_id,
                step_number=active_agent_step,
                status="error",
            )

        await persist_assistant_result(
            assistant_message_id=assistant_message_id,
            conversation_id=conversation_id,
            content=full_response,
            status="error",
            provider_response_id=provider_response_id,
        )

        yield json.dumps(
            {
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": (
                    "Something went wrong " "while generating the " "response."
                ),
                "retryable": False,
            }
        ) + "\n"
    finally:
        if release_agent_slot:
            agent_semaphore.release()
        logger.info(
            "assistant_stream_finished",
            extra={
                "conversation_id": str(conversation_id),
                "assistant_message_id": str(assistant_message_id),
            },
        )


async def stream_static_response(
    text: str,
    user_message_id: UUID,
    assistant_message_id: UUID,
    conversation_id: UUID,
):
    yield json.dumps(
        {
            "type": "message_ids",
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
        }
    ) + "\n"

    await persist_assistant_result(
        assistant_message_id=assistant_message_id,
        conversation_id=conversation_id,
        content=text,
        status="completed",
        provider_response_id=None,
    )

    yield json.dumps({"type": "delta", "delta": text}) + "\n"
    yield json.dumps({"type": "done"}) + "\n"
