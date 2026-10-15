import argparse
import asyncio

from uuid import UUID

from app.evals.agent_eval import (
    run_agent_eval,
)
from app.evals.retrieval_eval import (
    run_rag_eval,
)


async def main(
    document_id: UUID,
) -> None:

    print(
        "\n"
        "========================================\n"
        " RAG EVAL\n"
        "========================================\n"
    )

    rag_passed = await run_rag_eval(document_id)

    print(
        "\n"
        "========================================\n"
        " AGENT EVAL\n"
        "========================================\n"
    )

    agent_passed = await run_agent_eval()

    print(
        "\n"
        "========================================\n"
        " FINAL AI EVAL RESULT\n"
        "========================================"
    )

    print(f"RAG:   " f"{'PASS' if rag_passed else 'FAIL'}")

    print(f"Agent: " f"{'PASS' if agent_passed else 'FAIL'}")

    if not (rag_passed and agent_passed):
        raise SystemExit(1)

    print("\nAll AI evals passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=("Run all live AI eval suites."))

    parser.add_argument(
        "--document-id",
        required=True,
        type=UUID,
        help=("UUID of the embedded acid-rain " "document used by the RAG eval."),
    )

    arguments = parser.parse_args()

    asyncio.run(main(arguments.document_id))
