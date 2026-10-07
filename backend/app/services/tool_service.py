from dataclasses import dataclass
import json
from typing import Any

from pydantic import ValidationError

from app.tools.registry import TOOL_REGISTRY


@dataclass
class ToolExecutionResult:
    ok: bool
    arguments: dict[str, Any]
    result: Any | None = None
    error: str | None = None

    def to_model_output(self) -> dict[str, Any]:
        if self.ok:
            return {"result": self.result}

        return {"error": self.error}


def execute_tool(
    name: str,
    arguments_json: str,
) -> ToolExecutionResult:
    spec = TOOL_REGISTRY.get(name)

    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError:
        return ToolExecutionResult(
            ok=False,
            arguments={
                "_raw": arguments_json,
            },
            error="Tool arguments were not valid JSON.",
        )

    if not isinstance(arguments, dict):
        return ToolExecutionResult(
            ok=False,
            arguments={
                "_raw": arguments,
            },
            error=("Tool arguments must be " "a JSON object."),
        )
    if spec is None:
        return ToolExecutionResult(
            ok=False,
            arguments=arguments,
            error=f"Unknown tool: {name}",
        )
    try:
        validated = spec.args_model.model_validate(arguments)

    except ValidationError:
        return ToolExecutionResult(
            ok=False,
            arguments=arguments,
            error=("Tool arguments failed " "validation."),
        )
    validated_arguments = validated.model_dump()
    try:
        result = spec.handler(**validated_arguments)
    except ValueError as exc:
        return ToolExecutionResult(
            ok=False,
            arguments=validated_arguments,
            error=str(exc),
        )

    except Exception:
        return ToolExecutionResult(
            ok=False,
            arguments=validated_arguments,
            error="Tool execution failed.",
        )

    return ToolExecutionResult(
        ok=True,
        arguments=validated_arguments,
        result=result,
    )
