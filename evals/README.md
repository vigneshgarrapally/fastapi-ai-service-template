# Evals

LLM-as-judge scoring of the chat service's *output quality* — a different
concern from `tests/`, which checks code correctness (does `chat()` update
memory correctly, does the endpoint return the right shape), not whether a
given reply is actually any good.

Each metric (`relevancy`, `helpfulness`, `hallucination`) has a judge prompt
under `metrics/prompts/`. `evaluator.py` loads the right one, fills in
`{question}` / `{answer}` / `{context}`, and asks the configured LLM to
return a structured `EvalScore` (0-10 plus a one-sentence rationale) via
`LLMProvider.complete(..., response_format=EvalScore)`.

## Run it

```bash
uv run python -m evals.main
uv run python -m evals.main --question "..." --answer "..."
```

This is a smoke test of the harness, not a regression suite — there are no
pass/fail thresholds wired up. Extend `evals/main.py` (or add a script
alongside it) to run scoring over a larger fixed dataset, assert score
thresholds in CI, etc.
