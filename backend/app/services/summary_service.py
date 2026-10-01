from dataclasses import dataclass
from uuid import UUID
from app.services.token_service import (
    count_message_tokens,
)
from app.config.llm_config import OPENAI_MODEL, SUMMARY_MAX_OUTPUT_TOKENS
from openai import AsyncOpenAI

SUMMARY_TRIGGER_TOKENS = 5000
RECENT_HISTORY_TARGET_TOKENS = 3000

client = AsyncOpenAI()


@dataclass
class SummaryPlan:
    should_summarize: bool
    messages_to_summarize: list[dict]
    recent_messages: list[dict]
    through_message_id: UUID | None
    unsummarized_tokens: int
    summarize_tokens: int


async def generate_updated_summary(
    existing_summary: str | None, messages_to_summarize: list[dict]
) -> str:

    formatted_messages = format_messages_for_summary(messages_to_summarize)
    existing_summary_text = (
        existing_summary if existing_summary else "No previous summary exists."
    )
    input_text = f"""
                EXISTING CONVERSATION SUMMARY:

                {existing_summary_text}


                NEW CONVERSATION MESSAGES:

                {formatted_messages}
                """.strip()
    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions="""
                    Create an updated factual summary of the conversation.

                    The summary will be used as memory for future conversation turns.

                    Preserve important:
                    - facts supplied by the user
                    - preferences
                    - decisions
                    - requirements and constraints
                    - technical context
                    - unresolved questions or tasks
                    - important conclusions already reached

                    Merge the existing summary with the new messages.

                    Do not invent information.
                    Do not include conversational filler.
                    Do not describe the summarization process.
                    Keep the summary concise but preserve information that could matter later.
                    """.strip(),
        input=input_text,
        max_output_tokens=SUMMARY_MAX_OUTPUT_TOKENS,
    )
    summary_text = response.output_text.strip()

    if not summary_text:
        raise RuntimeError("Summary generation returned empty output")

    return summary_text


def format_messages_for_summary(
    messages: list[dict],
) -> str:
    parts = []

    for message in messages:
        role = message["role"]
        content = message["content"]

        parts.append(f"{role.upper()}:\n{content}")

    return "\n\n".join(parts)


def plan_summary_update(
    messages: list[dict],
    summary: dict | None,
    current_message_id: UUID,
) -> SummaryPlan:
    # Step:1 get unsummarized messages
    unsummarized_messages = get_unsummarized_messages(
        messages=messages, summary=summary
    )

    # Step:2  filter out user's current mssg
    historical_messages = []
    for message in unsummarized_messages:
        if message["id"] != current_message_id:
            historical_messages.append(message)

    # Step:3 Calculate unsummarized tokens  and verify whether it hits the limit or not
    unsummarized_tokens = 0
    for message in historical_messages:
        unsummarized_tokens += message_token_count(message)

    # Step:4 Return if limit is not hit , no need to summarize
    if unsummarized_tokens <= SUMMARY_TRIGGER_TOKENS:
        return SummaryPlan(
            should_summarize=False,
            messages_to_summarize=[],
            recent_messages=historical_messages,
            through_message_id=None,
            unsummarized_tokens=unsummarized_tokens,
            summarize_tokens=0,
        )

    # Step:5 Limit hits , summarization is needed
    # History is too large.
    # Work backwards to preserve roughly
    # RECENT_HISTORY_TARGET_TOKENS raw.
    recent_history_tokens = 0
    recent_history_messages = []
    for message in reversed(historical_messages):
        message_tokens = message_token_count(message)
        if recent_history_tokens + message_tokens > RECENT_HISTORY_TARGET_TOKENS:
            break
        recent_history_tokens += message_tokens
        recent_history_messages.append(message)
    recent_history_messages.reverse()
    # Step:6 if there are no messages to summarize then return so
    summarize_count = len(historical_messages) - len(recent_history_messages)
    messages_to_summarize = historical_messages[:summarize_count]

    if not messages_to_summarize:
        return SummaryPlan(
            should_summarize=False,
            messages_to_summarize=[],
            recent_messages=historical_messages,
            through_message_id=None,
            unsummarized_tokens=unsummarized_tokens,
            summarize_tokens=0,
        )
    through_message_id = messages_to_summarize[-1]["id"]
    summarize_tokens = sum(
        message_token_count(message) for message in messages_to_summarize
    )

    # Step:7 post this summarization actulay happens so calculate the through_message_id and

    return SummaryPlan(
        should_summarize=True,
        messages_to_summarize=messages_to_summarize,
        recent_messages=recent_history_messages,
        through_message_id=through_message_id,
        unsummarized_tokens=unsummarized_tokens,
        summarize_tokens=summarize_tokens,
    )


def message_token_count(
    message: dict,
) -> int:
    return count_message_tokens(
        {
            "role": message["role"],
            "content": message["content"],
        }
    )


def get_unsummarized_messages(
    messages: list[dict],
    summary: dict | None,
) -> list[dict]:

    usable_messages = [
        message
        for message in messages
        if (message["status"] == "completed" and message["content"].strip())
    ]
    if summary is None:
        return usable_messages
    through_message_id = summary["through_message_id"]
    boundary_index = None
    for index, message in enumerate(usable_messages):
        if message["id"] == through_message_id:
            boundary_index = index
            break
    if boundary_index is None:
        raise ValueError("Summary Boundary Message not found")
    return usable_messages[boundary_index + 1 :]
