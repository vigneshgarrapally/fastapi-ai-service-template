"""LLM-as-judge scoring of the chat service's output quality.

Judge prompts live as separate .md files under ``evals/metrics/prompts/``
(same convention as the agent's own system prompt — see
``app.features.ai.graph``) with ``{question}``/``{answer}``/``{context}``
placeholders filled in with ``str.format()`` before the prompt is sent to the
judge model.
"""

from __future__ import annotations

from pathlib import Path

from app.llm.factory import get_llm
from evals.schemas import EvalScore

_PROMPTS_DIR = Path(__file__).parent / "metrics" / "prompts"

_METRIC_FILES = {
    "relevancy": "relevancy.md",
    "helpfulness": "helpfulness.md",
    "hallucination": "hallucination.md",
}


def _load_prompt(metric: str) -> str:
    try:
        filename = _METRIC_FILES[metric]
    except KeyError:
        raise ValueError(
            f"Unknown metric {metric!r}; expected one of {sorted(_METRIC_FILES)}"
        ) from None
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


async def score_conversation(
    question: str,
    answer: str,
    metric: str,
    context: str = "",
) -> EvalScore:
    """Score one (question, answer) pair on a single metric via LLM-as-judge.

    Args:
        question: The user's original question/message.
        answer: The chat service's reply being evaluated.
        metric: One of "relevancy", "helpfulness", "hallucination".
        context: Optional supporting context (used by the hallucination judge).

    Returns:
        A validated ``EvalScore`` (0-10 plus a one-sentence rationale).

    Raises:
        ValueError: ``metric`` is not one of the known metric names.
    """
    template = _load_prompt(metric)
    prompt = template.format(question=question, answer=answer, context=context)
    result = await get_llm().complete(
        messages=[{"role": "user", "content": prompt}],
        response_format=EvalScore,
    )
    # response_format guarantees a validated EvalScore instance — see the same
    # pattern in app/llm/providers/*.
    assert isinstance(result, EvalScore)
    return result
