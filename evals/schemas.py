"""Pydantic models shared by the evals harness."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvalScore(BaseModel):
    """A single LLM-as-judge score for one (question, answer) pair."""

    score: float = Field(ge=0.0, le=10.0, description="0 (worst) to 10 (best).")
    rationale: str = Field(description="One-sentence justification for the score.")
