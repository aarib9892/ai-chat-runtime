from uuid import UUID

from openai import AsyncOpenAI
import asyncio
import json
from app.repositories.message_repository import update_message
from app.services.context_service import build_context
from app.repositories.conversation_repository import touch_conversation

client = AsyncOpenAI()


async def persist_assistant_result(
    assistant_message_id: UUID,
    conversation_id: UUID,
    content: str,
    status: str,
    provider_response_id: str | None,
):
    await update_message(
        message_id=assistant_message_id,
        content=content,
        status=status,
        provider_response_id=provider_response_id,
    )

    await touch_conversation(conversation_id)


async def stream_llm(
    context: list[dict], assistant_message_id: UUID, conversation_id: UUID
):
    # input_messages = [{"role": mssg.role, "content": mssg.content} for mssg in messages]
    full_response = ""
    provider_response_id = None
    try:
        stream = await client.responses.create(
            model="gpt-6-luna",
            input=context,
            # previous_response_id=previous_response_id,
            stream=True,
        )

        async for event in stream:
            print("\n----------------")
            print("EVENT TYPE:", event.type)
            print(event)
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

                print("\n=== TOKEN USAGE ===")

                if usage:
                    print("Input tokens:", usage.input_tokens)
                    print("Output tokens:", usage.output_tokens)
                    print("Total tokens:", usage.total_tokens)

                print("===================")
                yield json.dumps({"type": "done"}) + "\n"

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
