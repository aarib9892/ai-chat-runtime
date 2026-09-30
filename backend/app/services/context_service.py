from uuid import UUID
from app.config.llm_config import PLANNING_INPUT_BUDGET
from app.schemas.chat import ChatMessage
from app.services.token_service import count_message_tokens, count_context_tokens

MAX_INPUT_TOKENS = 5000
RESERVED_SYSTEM_TOKENS = 200
SAFETY_MARGIN_TOKENS = 200


def build_context(
    messages: list[dict], current_message_id: UUID
) -> list[dict[str, str]]:
    usable_messages = [
        message
        for message in messages
        if (message["status"] == "completed" and message["content"].strip())
    ]
    current_message = next(
        (message for message in usable_messages if message["id"] == current_message_id),
        None,
    )
    if current_message is None:
        raise ValueError("Current user message not found")

    current_context_message = {
        "role": current_message["role"],
        "content": current_message["content"],
    }
    current_message_tokens = count_message_tokens(current_context_message)
    if current_message_tokens > (
        MAX_INPUT_TOKENS - RESERVED_SYSTEM_TOKENS - SAFETY_MARGIN_TOKENS
    ):
        raise ValueError("Current message exceeds the input token budget")
    history_budget = PLANNING_INPUT_BUDGET - current_message_tokens
    historical_messages = [
        message for message in usable_messages if message["id"] != current_message_id
    ]

    selected_history: list[dict[str, str]] = []
    history_tokens = 0
    if history_budget > 0:
        for message in reversed(historical_messages):
            context_message = {"role": message["role"], "content": message["content"]}
            message_tokens = count_message_tokens(context_message)
            if history_tokens + message_tokens > history_budget:
                break
            selected_history.append(context_message)
            history_tokens += message_tokens
    selected_history.reverse()
    context = [*selected_history, current_context_message]
    print("=== CONTEXT BUILD ===")
    print(
        "Selected history messages:",
        len(selected_history),
    )

    print(
        "History tokens:",
        history_tokens,
    )

    print(
        "Total selected tokens:",
        count_context_tokens(context),
    )

    print(
        "Available messages:",
        len(usable_messages),
    )

    print(
        "Current message tokens:",
        current_message_tokens,
    )

    print(
        "History budget:",
        max(history_budget, 0),
    )
    return context
