# ADR 0001: Record Architecture Decisions

**Status:** Accepted

---

## Context

As this project grows, decisions get made about libraries, data models, provider
abstractions, and trade-offs that aren't obvious from reading the code alone. Without
a record, the same question gets re-litigated every few months, usually by someone
who wasn't there for the original discussion and has no way to find out why things
are the way they are.

## Decision

We will record every significant architectural decision as an **Architecture
Decision Record (ADR)** — a short Markdown file in `docs/decisions/`, one per
decision, following the structure of this file:

- **Title** — a short phrase naming the decision, prefixed with a sequential number (`ADR 000N: ...`)
- **Status** — `Proposed`, `Accepted`, `Superseded by ADR 00NN`, or `Deprecated`
- **Context** — the problem or forces that made a decision necessary
- **Decision** — what was decided, stated plainly
- **Consequences** — what becomes easier or harder as a result, including trade-offs accepted on purpose

Add diagrams (Mermaid `flowchart`/`sequenceDiagram`/`erDiagram`, per this project's
[Documentation Maintenance conventions](../contributing.md#updating-docs)) wherever a
picture would save a paragraph of prose.

## Consequences

- Every future significant decision gets its own numbered file — copy this one's
  structure rather than inventing a new shape each time.
- **ADRs are append-only once accepted.** Don't edit an old ADR to reflect a later
  change of mind — write a new ADR that supersedes it, and update the old one's
  status line to point at the new one. The historical record of what was actually
  decided (and why, at the time) stays intact.
- Not every decision needs an ADR — routine implementation choices don't. Reserve
  this for decisions that are expensive to reverse, non-obvious from the code, or
  likely to be questioned again later (see [ADR: LLM Provider
  Switching](llm-provider-switching.md) and [ADR:
  Idempotency](idempotency.md) for two worked examples already in this template).
