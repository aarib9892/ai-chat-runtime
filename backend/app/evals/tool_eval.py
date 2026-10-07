import asyncio
import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app.config.llm_config import OPENAI_MODEL
from app.services.tool_service import execute_tool
from app.tools.definitions import TOOLS

client = AsyncOpenAI()


@dataclass(frozen=True)
class ToolEvalCase:
    name: str
    prompt: str

    expected_tool: str | None

    expected_arguments: dict[str, Any] | None = None

    expected_execution_ok: bool | None = None

    expected_result: Any | None = None


CASES = [
    ToolEvalCase(
        name="multiply_large_numbers",
        prompt=("What is 4817 multiplied " "by 923?"),
        expected_tool="calculate",
        expected_arguments={
            "operation": "multiply",
            "a": 4817,
            "b": 923,
        },
        expected_execution_ok=True,
        expected_result=4446091,
    ),
    ToolEvalCase(
        name="subtract_numbers",
        prompt="What is 9012 minus 487?",
        expected_tool="calculate",
        expected_arguments={
            "operation": "subtract",
            "a": 9012,
            "b": 487,
        },
        expected_execution_ok=True,
        expected_result=8525,
    ),
    ToolEvalCase(
        name="divide_numbers",
        prompt="What is 144 divided by 12?",
        expected_tool="calculate",
        expected_arguments={
            "operation": "divide",
            "a": 144,
            "b": 12,
        },
        expected_execution_ok=True,
        expected_result=12,
    ),
    ToolEvalCase(
        name="simple_arithmetic",
        prompt="What is 2 + 2?",
        expected_tool="calculate",
        expected_arguments={
            "operation": "add",
            "a": 2,
            "b": 2,
        },
        expected_execution_ok=True,
        expected_result=4,
    ),
    ToolEvalCase(
        name="text_length",
        prompt=("How many characters are " 'in "architecture"?'),
        expected_tool="get_text_length",
        expected_arguments={
            "text": "architecture",
        },
        expected_execution_ok=True,
        expected_result=12,
    ),
    ToolEvalCase(
        name="text_length_spaces",
        prompt=("How many characters are " 'in "hello world!"?'),
        expected_tool="get_text_length",
        expected_arguments={
            "text": "hello world!",
        },
        expected_execution_ok=True,
        expected_result=12,
    ),
    ToolEvalCase(
        name="division_by_zero",
        prompt=("Use the calculator to " "divide 10 by 0."),
        expected_tool="calculate",
        expected_arguments={
            "operation": "divide",
            "a": 10,
            "b": 0,
        },
        expected_execution_ok=False,
    ),
    ToolEvalCase(
        name="greeting_no_tool",
        prompt="Say hello to Aarib.",
        expected_tool=None,
    ),
    ToolEvalCase(
        name="explanation_no_tool",
        prompt=("Explain what multiplication " "means in simple terms."),
        expected_tool=None,
    ),
    ToolEvalCase(
        name="writing_no_tool",
        prompt=("Write two sentences " "explaining recursion."),
        expected_tool=None,
    ),
]


def arguments_match(
    tool_name: str,
    expected: dict,
    actual: dict,
) -> bool:

    if tool_name == "calculate":
        if actual.get("operation") != expected.get("operation"):
            return False

        operation = expected["operation"]

        expected_a = expected["a"]
        expected_b = expected["b"]

        actual_a = actual.get("a")
        actual_b = actual.get("b")

        if operation in {
            "add",
            "multiply",
        }:
            return (actual_a == expected_a and actual_b == expected_b) or (
                actual_a == expected_b and actual_b == expected_a
            )

        return actual_a == expected_a and actual_b == expected_b

    return actual == expected


async def evaluate_case(
    case: ToolEvalCase,
) -> dict:

    response = await client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "user",
                "content": case.prompt,
            }
        ],
        tools=TOOLS,
        tool_choice="auto",
        parallel_tool_calls=False,
    )

    function_calls = [item for item in response.output if item.type == "function_call"]

    # -------------------------
    # Expected NO tool
    # -------------------------

    if case.expected_tool is None:
        routing_ok = len(function_calls) == 0

        return {
            "case": case.name,
            "passed": routing_ok,
            "routing_ok": routing_ok,
            "expected_tool": None,
            "actual_tool": (function_calls[0].name if function_calls else None),
        }

    # -------------------------
    # Expected exactly 1 tool
    # -------------------------

    if len(function_calls) != 1:
        return {
            "case": case.name,
            "passed": False,
            "routing_ok": False,
            "expected_tool": case.expected_tool,
            "actual_tool": None,
            "reason": (
                "Expected exactly one " f"tool call, got " f"{len(function_calls)}"
            ),
        }

    call = function_calls[0]

    routing_ok = call.name == case.expected_tool

    # -------------------------
    # Parse arguments
    # -------------------------

    try:
        actual_arguments = json.loads(call.arguments)

    except json.JSONDecodeError:
        return {
            "case": case.name,
            "passed": False,
            "routing_ok": routing_ok,
            "arguments_ok": False,
            "expected_tool": case.expected_tool,
            "actual_tool": call.name,
            "reason": "Invalid JSON arguments",
        }

    if not isinstance(actual_arguments, dict):
        return {
            "case": case.name,
            "passed": False,
            "routing_ok": routing_ok,
            "arguments_ok": False,
            "expected_tool": case.expected_tool,
            "actual_tool": call.name,
            "reason": "Tool arguments were not a JSON object",
        }

    arguments_ok = arguments_match(
        tool_name=call.name,
        expected=(case.expected_arguments or {}),
        actual=actual_arguments,
    )

    # -------------------------
    # Execute using real runtime
    # -------------------------

    execution = execute_tool(
        name=call.name,
        arguments_json=call.arguments,
    )

    execution_ok = execution.ok == case.expected_execution_ok

    # -------------------------
    # Result correctness
    # -------------------------

    result_ok = True

    if case.expected_execution_ok and case.expected_result is not None:
        result_ok = execution.result == case.expected_result

    passed = routing_ok and arguments_ok and execution_ok and result_ok

    return {
        "case": case.name,
        "passed": passed,
        "routing_ok": routing_ok,
        "arguments_ok": arguments_ok,
        "execution_ok": execution_ok,
        "result_ok": result_ok,
        "expected_tool": case.expected_tool,
        "actual_tool": call.name,
        "expected_arguments": case.expected_arguments,
        "actual_arguments": actual_arguments,
        "result": execution.result,
        "error": execution.error,
    }


def print_summary(
    results: list[dict],
):
    total = len(results)

    passed = sum(1 for result in results if result["passed"])

    routing_passed = sum(1 for result in results if result.get("routing_ok"))

    no_tool_cases = [
        result for result in results if result.get("expected_tool") is None
    ]

    no_tool_passed = sum(1 for result in no_tool_cases if result["passed"])

    argument_cases = [result for result in results if "arguments_ok" in result]

    arguments_passed = sum(1 for result in argument_cases if result["arguments_ok"])

    print("\n====================")
    print("TOOL EVAL SUMMARY")
    print("====================")

    print(f"Overall: " f"{passed}/{total}")

    print(f"Routing: " f"{routing_passed}/{total}")

    print(
        "No-tool accuracy:",
        f"{no_tool_passed}/" f"{len(no_tool_cases)}",
    )

    print(
        "Argument accuracy:",
        f"{arguments_passed}/" f"{len(argument_cases)}",
    )


async def main() -> bool:
    results: list[dict] = []

    for case in CASES:
        print(f"\n=== {case.name} ===")

        result = await evaluate_case(case)

        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"

        print(status)
        print(
            "Expected tool:",
            result.get("expected_tool"),
        )
        print(
            "Actual tool:",
            result.get("actual_tool"),
        )

        if result.get("arguments_ok") is not None:
            print(
                "Arguments:",
                result["arguments_ok"],
            )

        if result.get("execution_ok") is not None:
            print(
                "Execution:",
                result["execution_ok"],
            )

        if "result" in result:
            print(
                "Result:",
                result["result"],
            )

        if result.get("error"):
            print(
                "Error:",
                result["error"],
            )

    print_summary(results)

    return all(result["passed"] for result in results)


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
