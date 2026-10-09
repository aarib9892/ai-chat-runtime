import asyncio
import re
from dataclasses import dataclass
from typing import Callable, Literal

from app.services.agent_service import stream_agent
from app.services.agent_events import (
    AgentStepStarted,
    AgentToolCall,
    AgentToolResult,
    AgentToolError,
    AgentCompleted,
    AgentIncomplete,
)

TerminalState = Literal[
    "completed",
    "incomplete",
]


@dataclass(frozen=True)
class AgentEvalCase:
    name: str
    prompt: str

    expected_tools: list[str]

    expected_terminal: TerminalState = "completed"

    expected_execution_ok: list[bool] | None = None

    expected_steps: int | None = None

    expected_incomplete_reason: str | None = None

    final_answer_check: Callable[[str], bool] | None = None

    max_steps: int = 5

    max_tool_calls: int = 8

    max_identical_tool_calls: int = 2


@dataclass
class AgentEvalObservation:
    tools: list[str]
    execution_ok: list[bool]

    steps: int

    completed: bool

    incomplete_reason: str | None

    final_text: str

    exception: str | None


@dataclass
class AgentEvalResult:
    case: AgentEvalCase

    observation: AgentEvalObservation

    checks: dict[str, bool]

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def normalize_number_text(
    text: str,
) -> str:
    """
    Remove formatting such as commas,
    whitespace, markdown etc.

    Useful for checking numeric answers
    without caring whether the model writes:

        76728
        76,728
        **76,728**
    """

    return re.sub(
        r"[^0-9]",
        "",
        text,
    )


def contains_number(
    expected: int,
) -> Callable[[str], bool]:

    expected_text = str(expected)

    def check(text: str) -> bool:
        normalized = normalize_number_text(text)

        return expected_text in normalized

    return check


def contains_all_numbers(
    *expected_numbers: int,
) -> Callable[[str], bool]:

    expected_strings = [str(number) for number in expected_numbers]

    def check(text: str) -> bool:
        normalized = normalize_number_text(text)

        return all(expected in normalized for expected in expected_strings)

    return check


async def run_eval_case(
    case: AgentEvalCase,
) -> AgentEvalResult:

    tools: list[str] = []

    execution_ok: list[bool] = []

    highest_step = 0

    completed = False

    incomplete_reason = None

    final_text = ""

    exception = None

    try:
        async for event in stream_agent(
            input_items=[
                {
                    "role": "user",
                    "content": case.prompt,
                }
            ],
            max_steps=case.max_steps,
            max_tool_calls=case.max_tool_calls,
            max_identical_tool_calls=case.max_identical_tool_calls,
        ):

            if isinstance(
                event,
                AgentStepStarted,
            ):
                highest_step = max(
                    highest_step,
                    event.step,
                )

            elif isinstance(
                event,
                AgentToolCall,
            ):
                tools.append(event.tool_name)

            elif isinstance(
                event,
                AgentToolResult,
            ):
                execution_ok.append(True)

            elif isinstance(
                event,
                AgentToolError,
            ):
                execution_ok.append(False)

            elif isinstance(
                event,
                AgentCompleted,
            ):
                completed = True
                final_text = event.final_text

            elif isinstance(
                event,
                AgentIncomplete,
            ):
                incomplete_reason = event.reason

    except Exception as exc:
        exception = repr(exc)

    observation = AgentEvalObservation(
        tools=tools,
        execution_ok=execution_ok,
        steps=highest_step,
        completed=completed,
        incomplete_reason=(incomplete_reason),
        final_text=final_text,
        exception=exception,
    )

    checks: dict[str, bool] = {}

    # --------------------------------
    # Unexpected runtime exception
    # --------------------------------

    checks["no_exception"] = exception is None

    # --------------------------------
    # Terminal state
    # --------------------------------

    if case.expected_terminal == "completed":
        checks["terminal_state"] = completed and incomplete_reason is None

    else:
        checks["terminal_state"] = not completed and incomplete_reason is not None

    # --------------------------------
    # Tool trajectory
    # --------------------------------

    checks["tool_sequence"] = tools == case.expected_tools

    # --------------------------------
    # Tool execution success/failure
    # --------------------------------

    if case.expected_execution_ok is not None:
        checks["tool_execution"] = execution_ok == case.expected_execution_ok

    # --------------------------------
    # Step count
    # --------------------------------

    if case.expected_steps is not None:
        checks["step_count"] = highest_step == case.expected_steps

    # --------------------------------
    # Incomplete reason
    # --------------------------------

    if case.expected_incomplete_reason is not None:
        checks["incomplete_reason"] = (
            incomplete_reason == case.expected_incomplete_reason
        )

    # --------------------------------
    # Final answer
    # --------------------------------

    if case.final_answer_check is not None:
        checks["final_answer"] = completed and case.final_answer_check(final_text)

    return AgentEvalResult(
        case=case,
        observation=observation,
        checks=checks,
    )


async def main() -> bool:

    cases = [
        # ==================================
        # 1. Multi-step agent trajectory
        # ==================================
        AgentEvalCase(
            name="multi_step_math_then_length",
            prompt=(
                "Multiply 834 by 92. "
                "Then use the text-length "
                "tool to count the characters "
                "in the raw resulting number "
                "with no commas or separators."
            ),
            expected_tools=[
                "calculate",
                "get_text_length",
            ],
            expected_execution_ok=[
                True,
                True,
            ],
            expected_steps=3,
            final_answer_check=(
                contains_all_numbers(
                    76728,
                    5,
                )
            ),
        ),
        # ==================================
        # 2. Single tool
        # ==================================
        AgentEvalCase(
            name="single_tool_calculation",
            prompt=("Use the calculator tool " "to multiply 4817 by 923."),
            expected_tools=[
                "calculate",
            ],
            expected_execution_ok=[
                True,
            ],
            expected_steps=2,
            final_answer_check=(contains_number(4446091)),
        ),
        # ==================================
        # 3. No tool
        # ==================================
        AgentEvalCase(
            name="direct_no_tool",
            prompt=("Say hello in one short " "sentence. Do not use tools."),
            expected_tools=[],
            expected_execution_ok=[],
            expected_steps=1,
            final_answer_check=lambda text: (len(text.strip()) > 0),
        ),
        # ==================================
        # 4. Tool failure recovery
        # ==================================
        AgentEvalCase(
            name="tool_failure_recovery",
            prompt=(
                "Use the calculator tool "
                "to divide 10 by 0. "
                "After receiving the tool "
                "result, explain what "
                "happened."
            ),
            expected_tools=[
                "calculate",
            ],
            expected_execution_ok=[
                False,
            ],
            expected_steps=2,
            final_answer_check=lambda text: ("zero" in text.lower()),
        ),
        # ==================================
        # 5. Max agent steps
        # ==================================
        AgentEvalCase(
            name="max_agent_steps_guard",
            prompt=(
                "Multiply 834 by 92. "
                "Then count the characters "
                "in the resulting number "
                "using the text-length tool."
            ),
            expected_tools=[],
            expected_terminal=("incomplete"),
            expected_execution_ok=[],
            expected_steps=1,
            expected_incomplete_reason=("max_agent_steps"),
            max_steps=1,
        ),
        # ==================================
        # 6. Max tool calls
        # ==================================
        AgentEvalCase(
            name="max_tool_calls_guard",
            prompt=(
                "Multiply 834 by 92. "
                "Then use the text-length "
                "tool to count the characters "
                "in the raw resulting number "
                "with no commas or separators."
            ),
            expected_tools=[
                "calculate",
            ],
            expected_execution_ok=[
                True,
            ],
            expected_terminal=("incomplete"),
            expected_steps=2,
            expected_incomplete_reason=("max_tool_calls"),
            max_tool_calls=1,
        ),
        # ==================================
        # 7. Repeated-tool guard path
        # ==================================
        #
        # Setting the limit to zero means
        # even the first identical signature
        # exceeds the allowed count.
        #
        # This verifies the guard PATH.
        AgentEvalCase(
            name="repeated_tool_guard_path",
            prompt=("Use the calculator tool " "to multiply 10 by 20."),
            expected_tools=[],
            expected_execution_ok=[],
            expected_terminal=("incomplete"),
            expected_steps=1,
            expected_incomplete_reason=("repeated_tool_call"),
            max_identical_tool_calls=0,
        ),
    ]

    results: list[AgentEvalResult] = []

    for case in cases:

        print("\n" + "=" * 60)

        print(f"CASE: {case.name}")

        print("=" * 60)

        result = await run_eval_case(case)

        results.append(result)

        observation = result.observation

        print(
            "Tools:",
            observation.tools,
        )

        print(
            "Execution:",
            observation.execution_ok,
        )

        print(
            "Steps:",
            observation.steps,
        )

        print(
            "Completed:",
            observation.completed,
        )

        print(
            "Incomplete reason:",
            observation.incomplete_reason,
        )

        if observation.final_text:
            print(
                "Final:",
                observation.final_text,
            )

        if observation.exception:
            print(
                "Exception:",
                observation.exception,
            )

        print("\nChecks:")

        for (
            check_name,
            passed,
        ) in result.checks.items():

            symbol = "PASS" if passed else "FAIL"

            print(f"  {symbol:<4} " f"{check_name}")

        print(
            "\nRESULT:",
            "PASS" if result.passed else "FAIL",
        )

    # ======================================
    # Overall summary
    # ======================================

    passed_count = sum(result.passed for result in results)

    print("\n" + "=" * 60)

    print("AGENT EVAL SUMMARY")

    print("=" * 60)

    print(f"Overall: " f"{passed_count}/" f"{len(results)}")

    print()

    for result in results:

        symbol = "PASS" if result.passed else "FAIL"

        print(f"{symbol:<4} " f"{result.case.name}")

    return all(result.passed for result in results)


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
