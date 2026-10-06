import asyncio
import json
from uuid import UUID

from openai import AsyncOpenAI

from app.config.llm_config import MAX_OUTPUT_TOKENS, OPENAI_MODEL
from app.db.database import get_pool
from app.repositories.conversation_repository import touch_conversation
from app.repositories.message_repository import update_message
from app.repositories.tool_call_repository import (
    complete_tool_call,
    create_tool_call,
    fail_tool_call,
)
from app.services.retrieval_service import RetrievedChunk
from app.services.token_service import count_context_tokens
from app.services.tool_service import execute_tool
from app.tools.definitions import TOOLS

client = AsyncOpenAI()


def build_tool_call_event(
    call_id: str,
    name: str,
    arguments: dict[str, object],
) -> str:
    return (
        json.dumps(
            {
                "type": "tool_call",
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
            }
        )
        + "\n"
    )


def build_tool_result_event(
    call_id: str,
    name: str,
    status: str,
    result: dict[str, object] | None = None,
    error: str | None = None,
) -> str:
    event: dict[str, object] = {
        "type": "tool_result",
        "call_id": call_id,
        "name": name,
        "status": status,
    }

    if result is not None:
        event["result"] = result

    if error is not None:
        event["error"] = error

    return json.dumps(event) + "\n"


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


def log_token_usage(usage, estimated_input_tokens: int):
    if not usage:
        return

    actual_input_tokens = usage.input_tokens
    difference = actual_input_tokens - estimated_input_tokens
    error_percentage = (
        (difference / actual_input_tokens) * 100 if actual_input_tokens else 0
    )

    print("=== TOKEN USAGE ===")
    print("Estimated input:", estimated_input_tokens)
    print("Actual input:", actual_input_tokens)
    print("Difference:", difference)
    print("Estimation error %:", round(error_percentage, 2))
    print("Output tokens:", usage.output_tokens)
    print("Total tokens:", usage.total_tokens)


async def stream_llm(
    context: list[dict],
    user_message_id: UUID,
    assistant_message_id: UUID,
    conversation_id: UUID,
    retrieved_chunks: list[RetrievedChunk] | None = None,
):
    full_response = ""
    provider_response_id: str | None = None
    first_response_id: str | None = None
    tool_call: dict[str, str] | None = None
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
            tools=TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            stream=True,
        )

        async for event in stream:
            if event.type == "response.created":
                first_response_id = event.response.id
                provider_response_id = event.response.id

            elif event.type == "response.output_text.delta":
                full_response += event.delta
                yield json.dumps({"type": "delta", "delta": event.delta}) + "\n"

            elif event.type == "response.output_item.done":
                item = event.item

                if item.type == "function_call":
                    tool_call = {
                        "call_id": item.call_id,
                        "name": item.name,
                        "arguments": item.arguments,
                    }

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

                yield json.dumps({"type": "incomplete", "reason": reason}) + "\n"
                return

            elif event.type == "response.failed":
                raise RuntimeError("OpenAI response failed")

            elif event.type == "response.completed":
                if tool_call is not None:
                    break

                await persist_assistant_result(
                    assistant_message_id=assistant_message_id,
                    conversation_id=conversation_id,
                    content=full_response,
                    status="completed",
                    provider_response_id=provider_response_id,
                )
                log_token_usage(event.response.usage, estimated_input_tokens)
                yield json.dumps({"type": "done"}) + "\n"
                return

        if tool_call is None:
            raise RuntimeError("Initial response stream ended without a terminal event")

        arguments = json.loads(tool_call["arguments"])
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")

        await create_tool_call(
            message_id=assistant_message_id,
            call_id=tool_call["call_id"],
            tool_name=tool_call["name"],
            arguments=arguments,
        )
        yield build_tool_call_event(
            call_id=tool_call["call_id"],
            name=tool_call["name"],
            arguments=arguments,
        )

        try:
            tool_result = execute_tool(
                name=tool_call["name"],
                arguments_json=tool_call["arguments"],
            )
            await complete_tool_call(
                message_id=assistant_message_id,
                call_id=tool_call["call_id"],
                result=tool_result,
            )
            yield build_tool_result_event(
                call_id=tool_call["call_id"],
                name=tool_call["name"],
                status="completed",
                result=tool_result,
            )
        except Exception as exc:
            tool_error = str(exc) or "Tool execution failed"
            await fail_tool_call(
                message_id=assistant_message_id,
                call_id=tool_call["call_id"],
                error=tool_error,
            )
            tool_result = {"error": tool_error}
            yield build_tool_result_event(
                call_id=tool_call["call_id"],
                name=tool_call["name"],
                status="error",
                error=tool_error,
            )

        if first_response_id is None:
            raise RuntimeError("Missing first response ID for tool continuation")

        final_stream = await client.responses.create(
            model=OPENAI_MODEL,
            previous_response_id=first_response_id,
            input=[
                {
                    "type": "function_call_output",
                    "call_id": tool_call["call_id"],
                    "output": json.dumps(tool_result),
                }
            ],
            tools=TOOLS,
            tool_choice="none",
            max_output_tokens=MAX_OUTPUT_TOKENS,
            stream=True,
        )

        async for event in final_stream:
            if event.type == "response.created":
                provider_response_id = event.response.id

            elif event.type == "response.output_text.delta":
                full_response += event.delta
                yield json.dumps({"type": "delta", "delta": event.delta}) + "\n"

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
                yield json.dumps({"type": "incomplete", "reason": reason}) + "\n"
                return

            elif event.type == "response.failed":
                raise RuntimeError("OpenAI final response failed")

            elif event.type == "response.completed":
                await persist_assistant_result(
                    assistant_message_id=assistant_message_id,
                    conversation_id=conversation_id,
                    content=full_response,
                    status="completed",
                    provider_response_id=provider_response_id,
                )
                yield json.dumps({"type": "done"}) + "\n"
                return

        raise RuntimeError("Final response stream ended without a terminal event")

    except asyncio.CancelledError:
        await persist_assistant_result(
            assistant_message_id=assistant_message_id,
            conversation_id=conversation_id,
            content=full_response,
            status="stopped",
            provider_response_id=provider_response_id,
        )
        raise

    except GeneratorExit:
        await persist_assistant_result(
            assistant_message_id=assistant_message_id,
            conversation_id=conversation_id,
            content=full_response,
            status="stopped",
            provider_response_id=provider_response_id,
        )
        raise

    except Exception:
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
