import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import openai
from app.config.settings import settings
from app.errors import AppError
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
from app.services.provider_errors import map_openai_error
from app.services.tool_service import execute_tool
from app.tools.definitions import TOOLS

MAX_AGENT_STEPS = settings.max_agent_steps
MAX_AGENT_TOOL_CALLS = settings.max_agent_tool_calls
MAX_IDENTICAL_TOOL_CALLS = settings.max_identical_tool_calls


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
    max_tool_calls: int = MAX_AGENT_TOOL_CALLS,
    max_identical_tool_calls: int = MAX_IDENTICAL_TOOL_CALLS,
) -> AsyncIterator[AgentEvent]:
    """Run a bounded Responses API tool loop without persistence concerns."""
    agent_started_at = time.perf_counter()
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")
    if max_tool_calls < 0:
        raise ValueError("max_tool_calls must not be negative")
    if max_identical_tool_calls < 0:
        raise ValueError("max_identical_tool_calls must not be negative")

    tool_steps: list[AgentToolStep] = []
    total_tool_calls = 0
    tool_call_counts: dict[str, int] = {}
    previous_response_id: str | None = None
    current_input = input_items

    for step_number in range(1, max_steps + 1):
        step_started_at = time.perf_counter()
        step_input_tokens = 0
        step_output_tokens = 0
        step_total_tokens = 0
        yield AgentStepStarted(step=step_number)

        request_kwargs: dict[str, Any] = {
            "model": settings.openai_model,
            "input": current_input,
            "tools": TOOLS,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "max_output_tokens": settings.max_output_tokens,
            "stream": True,
        }
        if previous_response_id is not None:
            request_kwargs["previous_response_id"] = previous_response_id

        try:
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
                        usage = event.response.usage

                        if usage is not None:
                            step_input_tokens = usage.input_tokens or 0

                            step_output_tokens = usage.output_tokens or 0

                            step_total_tokens = usage.total_tokens or 0
            step_duration_ms = (time.perf_counter() - step_started_at) * 1000
            total_input_tokens += step_input_tokens
            total_output_tokens += step_output_tokens
            total_tokens += step_total_tokens

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
                if prospective_total > max_tool_calls:
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

                    if next_count > max_identical_tool_calls:
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

                yield AgentStepCompleted(
                    step=step_number,
                    outcome="tool",
                    duration_ms=step_duration_ms,
                    input_tokens=step_input_tokens,
                    output_tokens=step_output_tokens,
                    total_tokens=step_total_tokens,
                )
                previous_response_id = response_id
                current_input = tool_outputs
                continue

            if saw_message:
                yield AgentStepCompleted(
                    step=step_number,
                    outcome="final",
                    duration_ms=step_duration_ms,
                    input_tokens=step_input_tokens,
                    output_tokens=step_output_tokens,
                    total_tokens=step_total_tokens,
                )
                agent_duration_ms = (time.perf_counter() - agent_started_at) * 1000
                yield AgentCompleted(
                    final_text=step_text,
                    response_id=response_id,
                    total_steps=step_number,
                    tool_steps=tool_steps,
                    duration_ms=agent_duration_ms,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    total_tokens=total_tokens,
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

            yield AgentStepCompleted(
                step=step_number,
                outcome="continue",
                duration_ms=step_duration_ms,
                input_tokens=step_input_tokens,
                output_tokens=step_output_tokens,
                total_tokens=step_total_tokens,
            )
            previous_response_id = response_id
            current_input = []
        except AppError:
            raise

        except (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.APIStatusError,
        ) as exc:
            raise map_openai_error(exc) from exc


async def run_agent(
    input_items: list[dict],
    max_steps: int = MAX_AGENT_STEPS,
    max_tool_calls: int = MAX_AGENT_TOOL_CALLS,
    max_identical_tool_calls: int = MAX_IDENTICAL_TOOL_CALLS,
) -> AgentResult:
    """Consume ``stream_agent`` and return its completed final answer."""
    async for event in stream_agent(
        input_items=input_items,
        max_steps=max_steps,
        max_tool_calls=max_tool_calls,
        max_identical_tool_calls=max_identical_tool_calls,
    ):
        if isinstance(event, AgentCompleted):
            return AgentResult(
                final_text=event.final_text,
                steps=event.tool_steps,
                response_id=event.response_id,
            )

        if isinstance(event, AgentIncomplete):
            raise RuntimeError(f"Agent response incomplete: {event.reason}")

    raise RuntimeError("Agent stream ended without a completion event")
