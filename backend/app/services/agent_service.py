import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.config.llm_config import MAX_OUTPUT_TOKENS, OPENAI_MODEL
from app.services.agent_events import (
    AgentCompleted,
    AgentEvent,
    AgentIncomplete,
    AgentResponseCreated,
    AgentStepCompleted,
    AgentStepStarted,
    AgentTextDelta,
    AgentToolCall,
    AgentToolError,
    AgentToolResult,
    AgentToolStep,
)
from app.services.openai_client import client
from app.services.tool_service import execute_tool
from app.tools.definitions import TOOLS

MAX_AGENT_STEPS = 5
MAX_AGENT_TOOL_CALLS = 8
MAX_IDENTICAL_TOOL_CALLS = 2


@dataclass(frozen=True)
class AgentResult:
    final_text: str
    steps: list[AgentToolStep]
    response_id: str


def build_tool_signature(
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    canonical_arguments = json.dumps(
        arguments,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"{tool_name}:{canonical_arguments}"


def parse_tool_arguments(arguments_json: str) -> dict[str, Any]:
    """Parse model-provided arguments for observability before validation."""
    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError:
        return {"_raw": arguments_json}

    if isinstance(arguments, dict):
        return arguments

    return {"_raw": arguments}


async def stream_agent(
    input_items: list[dict],
    max_steps: int = MAX_AGENT_STEPS,
) -> AsyncIterator[AgentEvent]:
    """Run a bounded Responses API tool loop without persistence concerns."""
    tool_steps: list[AgentToolStep] = []
    total_tool_calls = 0
    tool_call_counts: dict[str, int] = {}
    previous_response_id: str | None = None
    current_input = input_items

    for step_number in range(1, max_steps + 1):
        yield AgentStepStarted(step=step_number)

        request_kwargs: dict[str, Any] = {
            "model": OPENAI_MODEL,
            "input": current_input,
            "tools": TOOLS,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "stream": True,
        }
        if previous_response_id is not None:
            request_kwargs["previous_response_id"] = previous_response_id

        stream = await client.responses.create(**request_kwargs)
        response_id: str | None = None
        tool_calls = []
        step_text = ""
        saw_message = False
        terminal_event_seen = False

        async with stream:
            async for event in stream:
                if event.type == "response.created":
                    response_id = event.response.id
                    yield AgentResponseCreated(
                        step=step_number,
                        response_id=response_id,
                    )

                elif event.type == "response.output_text.delta":
                    step_text += event.delta
                    yield AgentTextDelta(step=step_number, delta=event.delta)

                elif event.type == "response.output_item.done":
                    item = event.item
                    if item.type == "function_call":
                        tool_calls.append(item)
                    elif item.type == "message":
                        saw_message = True

                elif event.type == "response.incomplete":
                    reason = "unknown"
                    if event.response.incomplete_details is not None:
                        reason = event.response.incomplete_details.reason

                    yield AgentIncomplete(
                        step=step_number,
                        reason=reason,
                        partial_text=step_text,
                        response_id=response_id,
                    )
                    return

                elif event.type == "response.failed":
                    raise RuntimeError("OpenAI agent response failed")

                elif event.type == "response.completed":
                    terminal_event_seen = True

        if not terminal_event_seen:
            raise RuntimeError("Agent model stream ended without a terminal event")

        if response_id is None:
            raise RuntimeError("Agent response did not provide a response ID")

        if tool_calls:
            if step_number >= max_steps:
                yield AgentIncomplete(
                    step=step_number,
                    reason="max_agent_steps",
                    partial_text=step_text,
                    response_id=response_id,
                )
                return

            prospective_total = total_tool_calls + len(tool_calls)
            if prospective_total > MAX_AGENT_TOOL_CALLS:
                yield AgentIncomplete(
                    step=step_number,
                    reason="max_tool_calls",
                    partial_text=step_text,
                    response_id=response_id,
                )
                return

            prospective_counts = dict(tool_call_counts)
            parsed_calls = []

            for call in tool_calls:
                arguments = parse_tool_arguments(call.arguments)
                signature = build_tool_signature(call.name, arguments)
                next_count = prospective_counts.get(signature, 0) + 1

                if next_count > MAX_IDENTICAL_TOOL_CALLS:
                    yield AgentIncomplete(
                        step=step_number,
                        reason="repeated_tool_call",
                        partial_text=step_text,
                        response_id=response_id,
                    )
                    return

                prospective_counts[signature] = next_count
                parsed_calls.append((call, arguments))

            tool_call_counts = prospective_counts
            tool_outputs = []

            for call, arguments in parsed_calls:
                total_tool_calls += 1
                yield AgentToolCall(
                    step=step_number,
                    call_id=call.call_id,
                    tool_name=call.name,
                    arguments=arguments,
                )

                execution = execute_tool(
                    name=call.name,
                    arguments_json=call.arguments,
                )
                tool_steps.append(
                    AgentToolStep(
                        step=step_number,
                        call_id=call.call_id,
                        tool_name=call.name,
                        arguments=arguments,
                        ok=execution.ok,
                        result=execution.result,
                        error=execution.error,
                    )
                )

                if execution.ok:
                    yield AgentToolResult(
                        step=step_number,
                        call_id=call.call_id,
                        tool_name=call.name,
                        result=execution.result,
                    )
                else:
                    yield AgentToolError(
                        step=step_number,
                        call_id=call.call_id,
                        tool_name=call.name,
                        error=execution.error or "Tool execution failed.",
                    )

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": execution.to_model_output(),
                    }
                )

            yield AgentStepCompleted(step=step_number, outcome="tool")
            previous_response_id = response_id
            current_input = tool_outputs
            continue

        if saw_message:
            yield AgentStepCompleted(step=step_number, outcome="final")
            yield AgentCompleted(
                final_text=step_text,
                response_id=response_id,
                total_steps=step_number,
                tool_steps=tool_steps,
            )
            return

        if step_number >= max_steps:
            yield AgentIncomplete(
                step=step_number,
                reason="max_agent_steps",
                partial_text=step_text,
                response_id=response_id,
            )
            return

        yield AgentStepCompleted(step=step_number, outcome="continue")
        previous_response_id = response_id
        current_input = []


async def run_agent(
    input_items: list[dict],
    max_steps: int = MAX_AGENT_STEPS,
) -> AgentResult:
    """Consume ``stream_agent`` and return its completed final answer."""
    async for event in stream_agent(input_items=input_items, max_steps=max_steps):
        if isinstance(event, AgentCompleted):
            return AgentResult(
                final_text=event.final_text,
                steps=event.tool_steps,
                response_id=event.response_id,
            )

        if isinstance(event, AgentIncomplete):
            raise RuntimeError(f"Agent response incomplete: {event.reason}")

    raise RuntimeError("Agent stream ended without a completion event")
