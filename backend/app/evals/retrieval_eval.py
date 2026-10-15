import argparse
import asyncio

from dataclasses import dataclass
from uuid import UUID

from app.db.database import (
    connect_db,
    close_db,
)

from app.services.retrieval_service import (
    retrieve_chunks,
)

# ============================================================
# Eval models
# ============================================================


@dataclass(frozen=True)
class RagEvalCase:
    query: str
    expected_chunks: set[int]


@dataclass
class RagEvalResult:
    case: RagEvalCase

    retrieved_indices: list[int]
    similarities: list[float]

    top_1_hit: bool | None
    top_3_hit: bool | None

    negative_rejected: bool | None

    @property
    def passed(self) -> bool:
        # Negative case:
        # we expect retrieval to return nothing.
        if not self.case.expected_chunks:
            return self.negative_rejected is True

        # Positive case:
        # require both Hit@1 and Hit@3.
        return self.top_1_hit is True and self.top_3_hit is True


# ============================================================
# Eval cases
# ============================================================


def build_rag_eval_cases() -> list[RagEvalCase]:

    return [
        # ==================================
        # Positive retrieval cases
        # ==================================
        RagEvalCase(
            query=("Why do old stone monuments " "deteriorate because of acid rain?"),
            expected_chunks={2, 3},
        ),
        RagEvalCase(
            query=("How does acidic water affect " "fish and aquatic animals?"),
            expected_chunks={1, 2},
        ),
        RagEvalCase(
            query=("How does acid rain weaken " "forests?"),
            expected_chunks={2},
        ),
        RagEvalCase(
            query=("Is acid rain directly dangerous " "to human skin?"),
            expected_chunks={2, 3},
        ),
        RagEvalCase(
            query=("How can power plants reduce " "sulfur dioxide pollution?"),
            expected_chunks={4},
        ),
        RagEvalCase(
            query=("Can air pollution travel " "between different countries?"),
            expected_chunks={4, 5},
        ),
        # ==================================
        # Negative retrieval cases
        # ==================================
        RagEvalCase(
            query="Who was Albert Einstein?",
            expected_chunks=set(),
        ),
        RagEvalCase(
            query=("How do I bake a " "chocolate cake?"),
            expected_chunks=set(),
        ),
        RagEvalCase(
            query=("What is the capital of Japan?"),
            expected_chunks=set(),
        ),
        RagEvalCase(
            query=("How does React use " "the virtual DOM?"),
            expected_chunks=set(),
        ),
        RagEvalCase(
            query=("Who won the FIFA World Cup " "in 2018?"),
            expected_chunks=set(),
        ),
        RagEvalCase(
            query=("How does photosynthesis work?"),
            expected_chunks=set(),
        ),
    ]


# ============================================================
# Single-case execution
# ============================================================


async def run_eval_case(
    case: RagEvalCase,
    document_id: UUID,
) -> RagEvalResult:

    results = await retrieve_chunks(
        query=case.query,
        document_id=document_id,
        top_k=3,
    )

    retrieved_indices = [result.chunk_index for result in results]

    similarities = [result.similarity for result in results]

    # --------------------------------
    # Negative case
    # --------------------------------

    if not case.expected_chunks:
        return RagEvalResult(
            case=case,
            retrieved_indices=(retrieved_indices),
            similarities=similarities,
            top_1_hit=None,
            top_3_hit=None,
            negative_rejected=(len(results) == 0),
        )

    # --------------------------------
    # Positive case
    # --------------------------------

    top_1_hit = (
        retrieved_indices[0] in case.expected_chunks if retrieved_indices else False
    )

    top_3_hit = bool(set(retrieved_indices) & case.expected_chunks)

    return RagEvalResult(
        case=case,
        retrieved_indices=(retrieved_indices),
        similarities=similarities,
        top_1_hit=top_1_hit,
        top_3_hit=top_3_hit,
        negative_rejected=None,
    )


# ============================================================
# Printing
# ============================================================


def print_eval_result(
    result: RagEvalResult,
) -> None:

    print("\n" + "=" * 60)

    print("QUERY:")
    print(result.case.query)

    print("\nEXPECTED:")
    print(result.case.expected_chunks)

    print("\nRETRIEVED:")

    if not result.retrieved_indices:
        print("None")

    else:
        for (
            chunk_index,
            similarity,
        ) in zip(
            result.retrieved_indices,
            result.similarities,
        ):
            print(f"chunk={chunk_index} " f"similarity={similarity:.3f}")

    # --------------------------------
    # Negative case
    # --------------------------------

    if not result.case.expected_chunks:
        print(
            "\nNegative rejection:",
            ("PASS" if result.negative_rejected else "FAIL"),
        )

    # --------------------------------
    # Positive case
    # --------------------------------

    else:
        top_similarity = result.similarities[0] if result.similarities else None

        print(
            "\nTop similarity:",
            (
                round(
                    top_similarity,
                    3,
                )
                if top_similarity is not None
                else None
            ),
        )

        print(
            "Hit@1:",
            ("PASS" if result.top_1_hit else "FAIL"),
        )

        print(
            "Hit@3:",
            ("PASS" if result.top_3_hit else "FAIL"),
        )

    print(
        "\nRESULT:",
        ("PASS" if result.passed else "FAIL"),
    )


def print_eval_summary(
    results: list[RagEvalResult],
) -> None:

    positive_results = [result for result in results if result.case.expected_chunks]

    negative_results = [result for result in results if not result.case.expected_chunks]

    hit_at_1 = sum(result.top_1_hit is True for result in positive_results)

    hit_at_3 = sum(result.top_3_hit is True for result in positive_results)

    negative_rejected = sum(
        result.negative_rejected is True for result in negative_results
    )

    passed_count = sum(result.passed for result in results)

    print("\n" + "=" * 60)

    print("RAG EVAL SUMMARY")

    print("=" * 60)

    print(
        "Hit@1:",
        f"{hit_at_1}/" f"{len(positive_results)}",
    )

    print(
        "Hit@3:",
        f"{hit_at_3}/" f"{len(positive_results)}",
    )

    print(
        "Negative rejection:",
        f"{negative_rejected}/" f"{len(negative_results)}",
    )

    print(
        "Overall:",
        f"{passed_count}/" f"{len(results)}",
    )

    print()

    for result in results:
        symbol = "PASS" if result.passed else "FAIL"

        print(f"{symbol:<4} " f"{result.case.query}")


# ============================================================
# Public reusable runner
# ============================================================


async def run_rag_eval(
    document_id: UUID,
) -> bool:
    """
    Run the complete retrieval eval suite.

    Returns:
        True when every positive retrieval
        and negative rejection case passes.

        False when one or more cases fail.
    """

    await connect_db()

    try:
        cases = build_rag_eval_cases()

        results: list[RagEvalResult] = []

        for case in cases:
            result = await run_eval_case(
                case,
                document_id,
            )

            results.append(result)

            print_eval_result(result)

        print_eval_summary(results)

        return all(result.passed for result in results)

    finally:
        await close_db()


# ============================================================
# CLI entrypoint
# ============================================================


async def main(
    document_id: UUID,
) -> None:

    passed = await run_rag_eval(document_id)

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Evaluate retrieval quality " "for an embedded document.")
    )

    parser.add_argument(
        "--document-id",
        required=True,
        type=UUID,
        help=("UUID of the document used by " "the acid-rain evaluation fixture."),
    )

    arguments = parser.parse_args()

    asyncio.run(main(arguments.document_id))
