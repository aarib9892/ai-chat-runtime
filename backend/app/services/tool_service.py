import json
from typing import Any

from app.tools.registry import TOOL_HANDLERS


def execute_tool(
    name: str,
    arguments_json: str,
) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")

    arguments = json.loads(arguments_json)

    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object")

    result = handler(**arguments)

    return {"result": result}
