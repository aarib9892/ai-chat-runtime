from uuid import UUID
from app.config.llm_config import MAX_OUTPUT_TOKENS, OPENAI_MODEL
from app.db.database import get_pool
from openai import AsyncOpenAI
import asyncio
import json
from app.repositories.message_repository import update_message
from app.services.context_service import build_context
from app.repositories.conversation_repository import touch_conversation
from app.services.retrieval_service import RetrievedChunk
from app.services.token_service import (
    count_context_tokens,
)

client = AsyncOpenAI()


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
):
    # input_messages = [{"role": mssg.role, "content": mssg.content} for mssg in messages]
    full_response = ""
    provider_response_id = None
    estimated_input_tokens = count_context_tokens(context)
    try:
        yield json.dumps(
            {
                "type": "message_ids",
                "user_message_id": str(user_message_id),
                "assistant_message_id": str(assistant_message_id),
            }
        ) + "\n"
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
        stream = await client.responses.create(
            model=OPENAI_MODEL,
            input=context,
            # previous_response_id=previous_response_id,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            stream=True,
        )

        async for event in stream:
            # print("\n----------------")
            # print("EVENT TYPE:", event.type)
            # print(event)
            if event.type == "response.output_text.delta":
                full_response += event.delta
                yield json.dumps({"type": "delta", "delta": event.delta}) + "\n"
            elif event.type == "response.created":
                provider_response_id = event.response.id
                yield json.dumps(
                    {"type": "response_id", "response_id": event.response.id}
                ) + "\n"

            elif event.type == "response.completed":
                await persist_assistant_result(
                    assistant_message_id=assistant_message_id,
                    conversation_id=conversation_id,
                    content=full_response,
                    status="completed",
                    provider_response_id=provider_response_id,
                )
                usage = event.response.usage

                if usage:
                    actual_input_tokens = usage.input_tokens

                    actual_output_tokens = usage.output_tokens

                    difference = actual_input_tokens - estimated_input_tokens

                    error_percentage = (
                        (difference / actual_input_tokens) * 100
                        if actual_input_tokens
                        else 0
                    )

                    print("=== TOKEN USAGE ===")
                    print(
                        "Estimated input:",
                        estimated_input_tokens,
                    )
                    print(
                        "Actual input:",
                        actual_input_tokens,
                    )
                    print(
                        "Difference:",
                        difference,
                    )
                    print(
                        "Estimation error %:",
                        round(
                            error_percentage,
                            2,
                        ),
                    )
                    print(
                        "Output tokens:",
                        actual_output_tokens,
                    )
                    print(
                        "Total tokens:",
                        usage.total_tokens,
                    )
                yield json.dumps({"type": "done"}) + "\n"

            elif event.type == "response.incomplete":
                reason = "unknown"

                if event.response.incomplete_details:
                    reason = event.response.incomplete_details.reason

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
                        "reason": reason,
                    }
                ) + "\n"

                return

            elif event.type == "response.failed":
                raise RuntimeError("OpenAI response failed")

    except asyncio.CancelledError:
        print("Cancelled Stream")
        await persist_assistant_result(
            assistant_message_id=assistant_message_id,
            conversation_id=conversation_id,
            content=full_response,
            status="stopped",
            provider_response_id=provider_response_id,
        )
        raise

    except GeneratorExit:
        print("Stream generator closed")

        await persist_assistant_result(
            assistant_message_id=assistant_message_id,
            conversation_id=conversation_id,
            content=full_response,
            status="stopped",
            provider_response_id=provider_response_id,
        )

        raise

    except Exception as exc:
        print("STREAM ERROR:", repr(exc))
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
                "message": "Something went wrong while generating the response.",
            }
        ) + "\n"

    finally:
        print("Stream Function Ended")


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

    yield json.dumps(
        {
            "type": "delta",
            "delta": text,
        }
    ) + "\n"

    yield json.dumps(
        {
            "type": "done",
        }
    ) + "\n"
