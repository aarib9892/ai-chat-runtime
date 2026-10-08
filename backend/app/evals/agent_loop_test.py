import asyncio

from app.services.agent_service import (
    stream_agent,
)


async def main():
    input_items = [
        {
            "role": "user",
            "content": (
                "Multiply 834 by 92. "
                "Then use the text-length "
                "tool to count the "
                "characters in the raw "
                "resulting number with no "
                "commas or separators."
            ),
        }
    ]

    async for event in stream_agent(input_items=input_items):
        print(
            event.type,
            event,
        )


if __name__ == "__main__":
    asyncio.run(main())
