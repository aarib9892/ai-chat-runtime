from app.schemas.chat import ChatMessage

MAX_CONTEXT_MESSAGES = 6


def build_context(
    messages: list[dict],
) -> list[dict[str, str]]:
    usable_messages = [
        message
        for message in messages
        if (message["status"] == "completed" and message["content"].strip())
    ]

    recent_messages = usable_messages[-MAX_CONTEXT_MESSAGES:]

    print("\n=== CONTEXT DEBUG ===")
    print("messages type:", type(usable_messages))

    for index, message in enumerate(recent_messages):
        print(
            index,
            type(message),
            repr(message),
        )

    return [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in recent_messages
    ]
