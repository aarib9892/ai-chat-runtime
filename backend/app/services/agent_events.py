from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias


@dataclass(frozen=True)
class AgentToolStep:
    step: int
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    ok: bool
    result: Any | None
    error: str | None


@dataclass(frozen=True)
class AgentStepStarted:
    step: int

    type: Literal["agent_step_started"] = field(
        init=False,
        default="agent_step_started",
    )


@dataclass(frozen=True)
class AgentResponseCreated:
    step: int
    response_id: str

    type: Literal["agent_response_created"] = field(
        init=False,
        default="agent_response_created",
    )


@dataclass(frozen=True)
class AgentTextDelta:
    step: int
    delta: str

    type: Literal["agent_text_delta"] = field(
        init=False,
        default="agent_text_delta",
    )


@dataclass(frozen=True)
class AgentToolCall:
    step: int
    call_id: str
    tool_name: str
    arguments: dict[str, Any]

    type: Literal["agent_tool_call"] = field(
        init=False,
        default="agent_tool_call",
    )


@dataclass(frozen=True)
class AgentToolResult:
    step: int
    call_id: str
    tool_name: str
    result: Any

    type: Literal["agent_tool_result"] = field(
        init=False,
        default="agent_tool_result",
    )


@dataclass(frozen=True)
class AgentToolError:
    step: int
    call_id: str
    tool_name: str
    error: str

    type: Literal["agent_tool_error"] = field(
        init=False,
        default="agent_tool_error",
    )


@dataclass(frozen=True)
class AgentStepCompleted:
    step: int
    outcome: Literal[
        "tool",
        "final",
        "continue",
    ]

    type: Literal["agent_step_completed"] = field(
        init=False,
        default="agent_step_completed",
    )


@dataclass(frozen=True)
class AgentCompleted:
    final_text: str
    response_id: str
    total_steps: int
    tool_steps: list[AgentToolStep]

    type: Literal["agent_completed"] = field(
        init=False,
        default="agent_completed",
    )


@dataclass(frozen=True)
class AgentIncomplete:
    step: int
    reason: str
    partial_text: str
    response_id: str | None

    type: Literal["agent_incomplete"] = field(
        init=False,
        default="agent_incomplete",
    )


AgentEvent: TypeAlias = (
    AgentStepStarted
    | AgentResponseCreated
    | AgentTextDelta
    | AgentToolCall
    | AgentToolResult
    | AgentToolError
    | AgentStepCompleted
    | AgentCompleted
    | AgentIncomplete
)
