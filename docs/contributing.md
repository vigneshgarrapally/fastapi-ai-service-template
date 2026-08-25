# Contributing

Branching, commits, and keeping the docs in sync.

---

## Branching

```
main        ← production; protected, no direct pushes
feature/*   ← new features
fix/*       ← bug fixes
chore/*     ← tooling, deps, config
docs/*      ← docs-only changes
```

`no-commit-to-branch: main` is enforced locally by pre-commit (see below) in addition
to any server-side branch protection — every change to `main` goes through a PR.

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

---

## Pre-commit Hooks

Runs automatically on `git commit`:

| Hook | What it checks |
|---|---|
| `trailing-whitespace` | Trailing whitespace |
| `end-of-file-fixer` | Missing newline at EOF |
| `check-yaml` / `check-toml` | Valid YAML / TOML syntax |
| `check-merge-conflict` | Unresolved conflict markers |
| `detect-private-key` | Blocks accidental commit of secrets |
| `no-commit-to-branch` | Blocks direct commits to `main` |
| `ruff` | Lint (with auto-fix) |
| `ruff-format` | Code formatting |

If a hook auto-fixes files, stage the changes and commit again. All hooks must pass
before a commit succeeds — don't skip them with `--no-verify`.

```bash
uv run pre-commit install   # once per clone
```

---

## Quality Gates

```bash
uv run ruff check app/ --fix
uv run ruff format app/
uv run mypy app/
uv run pytest
```

Run a single test file:

```bash
uv run pytest tests/api/v1/test_health.py
```

Every confirmed bug fix should land with a regression test in the same change — one
that asserts the specific broken behavior, not just that the code runs.

---

## Updating Docs

**Doc updates land in the same PR as the code change** — never a separate one. Use
this table to find the right file:

| Code change | Doc to update |
|---|---|
| New API endpoint | `docs/api/overview.md` |
| New HTTP error code or condition | `docs/api/error-catalog.md` |
| New RabbitMQ queue or exchange | `docs/architecture/component-overview.md` (RabbitMQ Topology) |
| New worker consumer or job type | `docs/flows/ai-service.md` (or a new `docs/flows/<feature>.md`) |
| New ORM model or field | `docs/architecture/data-model.md` — then `uv run alembic revision --autogenerate` |
| New env var / secret | `docs/operations/environment-variables.md` |
| Startup/shutdown sequence changed | `docs/architecture/component-overview.md` |
| Auth mechanism changed | `docs/flows/auth-flow.md` |
| Retry policy or DLQ behavior changed | `docs/flows/failure-paths.md` |
| Architectural decision made | New `docs/decisions/<slug>.md` — see [ADR 0001](decisions/0001-record-architecture-decisions.md) for the format |

!!! note "ADRs are append-only once accepted"
    Don't edit an old ADR to reflect a later change of mind — write a new one that
    supersedes it. See [ADR 0001](decisions/0001-record-architecture-decisions.md).

---

## Building the Docs Locally

```bash
uv run mkdocs serve   # live-reload dev server
uv run mkdocs build   # static build to site/ (this is what CI runs with --strict)
```

See [Local Setup — Building the Docs Site](operations/local-setup.md#building-the-docs-site)
for the Mermaid pre-rendering caveat (`serve` vs `build` render diagrams
differently) and the Node.js toolchain `build` needs.
