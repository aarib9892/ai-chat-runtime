from uuid import UUID
from app.config.llm_config import PLANNING_INPUT_BUDGET
from app.schemas.chat import ChatMessage
from app.services.token_service import count_message_tokens, count_context_tokens

MAX_INPUT_TOKENS = 5000
RESERVED_SYSTEM_TOKENS = 200
SAFETY_MARGIN_TOKENS = 200


def build_context(
    messages: list[dict], current_message_id: UUID, summary: dict | None = None
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

    summary_message_tokens = 0
    summary_context_message = None
    if summary:
        summary_context_message = {
            "role": "assistant",
            "content": (
                "Conversation summary from earlier turns:\n\n" + summary["summary"]
            ),
        }
        summary_message_tokens = count_message_tokens(summary_context_message)

        boundary_index = None
        for index, message in enumerate(usable_messages):
            if message["id"] == summary["through_message_id"]:
                boundary_index = index
        if boundary_index is None:
            raise ValueError("Summary boundary message not found")
        historical_messages = usable_messages[boundary_index + 1 :]
    else:
        historical_messages = usable_messages

    historical_messages = [
        message
        for message in historical_messages
        if (message["id"] != current_message_id)
    ]

    mandatory_tokens = current_message_tokens + summary_message_tokens
    if mandatory_tokens > PLANNING_INPUT_BUDGET:
        raise ValueError("Current input and summary exceed token budget")

    history_budget = PLANNING_INPUT_BUDGET - mandatory_tokens

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

    context = [
        *([summary_context_message] if summary_context_message else []),
        *selected_history,
        current_context_message,
    ]
    print("=== CONTEXT BUILD ===")
    print(
        "Summary included:",
        summary is not None,
    )
    print(
        "Summary tokens:",
        summary_message_tokens,
    )
    print(
        "Unsummarized raw messages:",
        len(historical_messages),
    )
    print(
        "Selected raw history:",
        len(selected_history),
    )
    print(
        "Raw history tokens:",
        history_tokens,
    )
    print(
        "Current message tokens:",
        current_message_tokens,
    )
    print(
        "Total selected tokens:",
        count_context_tokens(context),
    )
    return context
