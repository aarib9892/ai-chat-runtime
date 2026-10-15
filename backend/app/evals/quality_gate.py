import argparse
import asyncio
import subprocess
import sys

from uuid import UUID

from app.evals.agent_eval import (
    run_agent_eval,
)
from app.evals.api_smoke import (
    run_api_smoke,
)
from app.evals.retrieval_eval import (
    run_rag_eval,
)


def run_pytest() -> bool:
    print(
        "\n"
        "========================================\n"
        " DETERMINISTIC TESTS\n"
        "========================================\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
        ],
        check=False,
    )

    return result.returncode == 0


async def run_quality_gate(
    *,
    document_id: UUID,
    base_url: str,
) -> bool:

    # ---------------------------------
    # 1. Deterministic tests
    # ---------------------------------

    tests_passed = run_pytest()

    if not tests_passed:
        print("\nDeterministic tests failed.")
        return False

    # ---------------------------------
    # 2. RAG eval
    # ---------------------------------

    print(
        "\n"
        "========================================\n"
        " RAG EVAL\n"
        "========================================\n"
    )

    rag_passed = await run_rag_eval(document_id)

    # ---------------------------------
    # 3. Agent eval
    # ---------------------------------

    print(
        "\n"
        "========================================\n"
        " AGENT EVAL\n"
        "========================================\n"
    )

    agent_passed = await run_agent_eval()

    # ---------------------------------
    # 4. Docker/API smoke
    # ---------------------------------

    print(
        "\n"
        "========================================\n"
        " API SMOKE\n"
        "========================================\n"
    )

    api_passed = await run_api_smoke(base_url)

    # ---------------------------------
    # Final summary
    # ---------------------------------

    print(
        "\n"
        "========================================\n"
        " FINAL QUALITY GATE\n"
        "========================================"
    )

    print(f"Tests: " f"{'PASS' if tests_passed else 'FAIL'}")

    print(f"RAG:   " f"{'PASS' if rag_passed else 'FAIL'}")

    print(f"Agent: " f"{'PASS' if agent_passed else 'FAIL'}")

    print(f"API:   " f"{'PASS' if api_passed else 'FAIL'}")

    passed = all(
        [
            tests_passed,
            rag_passed,
            agent_passed,
            api_passed,
        ]
    )

    if passed:
        print("\nQUALITY GATE: PASS")
    else:
        print("\nQUALITY GATE: FAIL")

    return passed


async def main(
    *,
    document_id: UUID,
    base_url: str,
) -> None:

    passed = await run_quality_gate(
        document_id=document_id,
        base_url=base_url,
    )

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Run the complete AI Chat Runtime " "production quality gate.")
    )

    parser.add_argument(
        "--document-id",
        required=True,
        type=UUID,
        help=("UUID of the acid-rain " "RAG evaluation fixture."),
    )

    parser.add_argument(
        "--base-url",
        default="http://localhost:3000",
        help=("URL of the running " "Dockerized application."),
    )

    arguments = parser.parse_args()

    asyncio.run(
        main(
            document_id=arguments.document_id,
            base_url=arguments.base_url,
        )
    )
