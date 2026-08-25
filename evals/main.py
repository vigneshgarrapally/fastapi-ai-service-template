"""CLI smoke test for the evals harness — scores a few Q/A pairs across all
three metrics (relevancy, helpfulness, hallucination) and prints the results.

Run with::

    uv run python -m evals.main
    uv run python -m evals.main --question "..." --answer "..." [--context "..."]

See ``evals/README.md`` for how this differs from ``tests/``.
"""

from __future__ import annotations

import argparse
import asyncio

from app.core.config import get_settings
from app.llm.factory import init_llm
from evals.evaluator import score_conversation

_EXAMPLE_PAIRS = [
    {
        "question": "What is the capital of France?",
        "answer": "The capital of France is Paris.",
        "context": "France is a country in Western Europe. Its capital is Paris.",
    },
    {
        "question": "How do I reverse a list in Python?",
        "answer": "Use `some_list[::-1]`, or call `.reverse()` to reverse it in place.",
        "context": "",
    },
]

_METRICS = ("relevancy", "helpfulness", "hallucination")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score chat Q/A pairs with the LLM-as-judge evals harness."
    )
    parser.add_argument(
        "--question", help="A single question to score instead of the built-in examples."
    )
    parser.add_argument("--answer", help="The answer to score against --question.")
    parser.add_argument(
        "--context", default="", help="Optional supporting context for the hallucination metric."
    )
    return parser.parse_args()


async def _run(pairs: list[dict[str, str]]) -> None:
    init_llm(get_settings())
    for pair in pairs:
        print(f"\nQ: {pair['question']}\nA: {pair['answer']}")
        for metric in _METRICS:
            result = await score_conversation(
                pair["question"], pair["answer"], metric, pair.get("context", "")
            )
            print(f"  {metric:12s} score={result.score:.1f}  {result.rationale}")


def main() -> None:
    args = _parse_args()
    if args.question and args.answer:
        pairs = [{"question": args.question, "answer": args.answer, "context": args.context}]
    else:
        pairs = _EXAMPLE_PAIRS
    asyncio.run(_run(pairs))


if __name__ == "__main__":
    main()
