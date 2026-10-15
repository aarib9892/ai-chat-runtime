from app.services.tool_service import ToolExecutionResult

import json


def test_tool_model_output_is_valid_json():
    result = ToolExecutionResult(
        ok=True,
        arguments={
            "operation": "multiply",
            "a": 2,
            "b": 3,
        },
        result=6,
        error=None,
    )

    parsed = json.loads(result.to_model_output())

    assert parsed == {
        "result": 6,
    }


def test_tool_error_model_output_is_valid_json():
    result = ToolExecutionResult(
        ok=False,
        arguments={},
        result=None,
        error="division by zero",
    )

    parsed = json.loads(result.to_model_output())

    assert parsed == {
        "error": "division by zero",
    }


def test_tool_model_output_is_string():
    result = ToolExecutionResult(
        ok=True,
        arguments={
            "operation": "multiply",
            "a": 2,
            "b": 3,
        },
        result=6,
        error=None,
    )

    output = result.to_model_output()

    assert isinstance(output, str)
