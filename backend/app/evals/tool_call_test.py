import asyncio
import json

from openai import AsyncOpenAI

from app.config.llm_config import (
    OPENAI_MODEL,
)

from app.services.tool_service import (
    execute_tool,
)

from app.tools.definitions import (
    TOOLS,
)

client = AsyncOpenAI()


async def run_test(prompt: str):
    input_items = [
        {
            "role": "user",
            "content": (prompt),
        }
    ]

    response = await client.responses.create(
        model=OPENAI_MODEL,
        input=input_items,
        tools=TOOLS,
        tool_choice="auto",
        parallel_tool_calls=False,
    )
    tool_called = False
    tool_outputs = []

    print("\n=== FIRST RESPONSE ===")

    for item in response.output:
        print(
            "type:",
            item.type,
        )
        if item.type != "function_call":
            continue

        tool_called = True
        print("\n=== TOOL CALL ===")
        print("Name:", item.name)
        print("Arguments:", item.arguments)
        print("Call ID:", item.call_id)

        result = execute_tool(
            name=item.name,
            arguments_json=item.arguments,
        )

        print(
            "Tool result:",
            result,
        )

        tool_outputs.append(
            {
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": json.dumps(result),
            }
        )
    if not tool_called:
        print("Model did not call a tool.")
        print(
            "Output:",
            response.output_text,
        )
        return

    final_response = await client.responses.create(
        model=OPENAI_MODEL,
        previous_response_id=response.id,
        input=tool_outputs,
        tools=TOOLS,
        tool_choice="none",
    )

    print("\n=== FINAL ANSWER ===")
    print(final_response.output_text)


async def main():
    await run_test("What is 834 multiplied by 92?")

    await run_test("How many characters are in " "the text 'architecture'?")

    await run_test("What is the number of characters in 834 multiplied by 92?")


if __name__ == "__main__":
    asyncio.run(main())
