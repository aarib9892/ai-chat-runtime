import argparse
import asyncio
from uuid import UUID

from app.db.database import (
    connect_db,
    close_db,
)

from app.services.retrieval_service import (
    retrieve_chunks,
)

EVAL_CASES = [
    {
        "query": ("Why do old stone monuments deteriorate " "because of acid rain?"),
        "expected_chunks": {2, 3},
    },
    {
        "query": ("How does acidic water affect fish " "and aquatic animals?"),
        "expected_chunks": {1, 2},
    },
    {
        "query": ("How does acid rain weaken forests?"),
        "expected_chunks": {2},
    },
    {
        "query": ("Is acid rain directly dangerous " "to human skin?"),
        "expected_chunks": {2, 3},
    },
    {
        "query": ("How can power plants reduce " "sulfur dioxide pollution?"),
        "expected_chunks": {4},
    },
    {
        "query": ("Can air pollution travel " "between different countries?"),
        "expected_chunks": {4, 5},
    },
    {
        "query": "Who was Albert Einstein?",
        "expected_chunks": set(),
    },
    {
        "query": "How do I bake a chocolate cake?",
        "expected_chunks": set(),
    },
    {
        "query": "What is the capital of Japan?",
        "expected_chunks": set(),
    },
    {
        "query": "How does React use the virtual DOM?",
        "expected_chunks": set(),
    },
    {
        "query": "Who won the FIFA World Cup in 2018?",
        "expected_chunks": set(),
    },
    {
        "query": "How does photosynthesis work?",
        "expected_chunks": set(),
    },
]


async def run_eval(document_id: UUID):
    await connect_db()

    try:
        hit_at_1 = 0
        hit_at_3 = 0
        positive_cases = 0
        negative_cases = 0
        negative_rejected = 0

        for case in EVAL_CASES:
            results = await retrieve_chunks(
                query=case["query"],
                document_id=document_id,
                top_k=3,
            )

            retrieved_indices = [result.chunk_index for result in results]

            expected = case["expected_chunks"]

            print("\n============================")
            print("QUERY:")
            print(case["query"])

            print("EXPECTED:")
            print(expected)

            print("RETRIEVED:")
            for result in results:
                print(
                    f"chunk={result.chunk_index} " f"similarity={result.similarity:.3f}"
                )

            if not expected:
                negative_cases += 1
                if not results:
                    negative_rejected += 1
                    print("NEGATIVE Rejection:PASS")
                else:
                    print("NEGATIVE Rejection:FAIL")

                continue

            positive_cases += 1

            top_1_hit = retrieved_indices[0] in expected if retrieved_indices else False

            top_3_hit = bool(set(retrieved_indices) & expected)

            top_similarity = results[0].similarity if results else None

            if top_1_hit:
                hit_at_1 += 1

            if top_3_hit:
                hit_at_3 += 1

            print(
                "Top similarity:",
                round(top_similarity, 3) if top_similarity is not None else None,
            )

            print(
                "Hit@1:",
                "PASS" if top_1_hit else "FAIL",
            )

            print(
                "Hit@3:",
                "PASS" if top_3_hit else "FAIL",
            )

        print("\n============================")
        print("FINAL RESULTS")

        print(
            "Hit@1:",
            f"{hit_at_1}/{positive_cases}",
        )

        print(
            "Hit@3:",
            f"{hit_at_3}/{positive_cases}",
        )
        print(
            "Negative rejection:",
            f"{negative_rejected}/{negative_cases}",
        )

    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality for an embedded document."
    )
    parser.add_argument(
        "--document-id",
        required=True,
        type=UUID,
        help="UUID of the document used by the acid-rain evaluation fixture.",
    )
    arguments = parser.parse_args()
    asyncio.run(run_eval(arguments.document_id))
