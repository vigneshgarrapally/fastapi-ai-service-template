# CLAUDE.md

Guidance for Claude Code when working **on this repo itself** — i.e. maintaining the
template. This file is intentionally excluded from Copier generation (see `copier.yml`'s
`_exclude: ["/CLAUDE.md"]`) so it never leaks into a project generated *from* this
template — those get `CLAUDE.md.jinja`'s rendered output instead, which documents the
generated project's own conventions, not the template's.

## What this is

A [Copier](https://copier.readthedocs.io/) template for AI-ML team projects — FastAPI +
Postgres + RabbitMQ + a pluggable LLM provider abstraction (Azure OpenAI / OpenAI /
Ollama), with everything past an always-on spine (`uv`, `ruff`, pre-commit, CI, a
`tests/` skeleton, structured logging, the secrets/`.env`-vs-`config.yaml` split) exposed
as independent generation-time yes/no toggles — see `copier.yml` for the exact question
set and current defaults.

Taxonomy, mirroring `lbedner/aegis-stack`'s split (researched before building this):
- **Components** (infra primitives): Backend (FastAPI), Database (Postgres + Alembic),
  Worker (RabbitMQ async job runtime — `when: include_database`), Cache (Redis),
  Observability (Langfuse + OTel + Prometheus/Grafana), Docs site (MkDocs + Mermaid).
- **Services** (business capabilities built on components): Auth (X-API-Key —
  `when: include_database`), AI (LLM provider abstraction + a LangGraph tool-calling
  agent + memory + an LLM-as-judge evals harness for its own output).

## Why Copier, specifically

Compared against Cookiecutter, Cookiecutter+cruft, and a plain "clone and rename"
approach (the last is what `fastapi/full-stack-fastapi-template` settled on after trying
*both* Cookiecutter and Copier and dropping both). Copier won because of `copier update`'s
native 3-way merge — a template fix or new default can be pulled into a project already
generated from this template, not just baked into new ones — and because it doesn't force
every generated file one directory level deeper the way Cookiecutter's
`{{cookiecutter.project_slug}}/` convention does, so this repo's own layout matches
whatever it generates. **`.copier-answers.yml.jinja` is what makes `copier update` work at
all** — it was missing for a while during this template's own build and nothing failed
loudly about it; if `copier update` ever silently does nothing, check this file exists and
is not excluded.

## File conventions

- A file gets a `.jinja` suffix **only if its own content contains `{{ }}` / `{% %}`**.
  Plain files that exist unconditionally, or whose existence is toggle-gated but content
  never varies, stay suffix-less.
- Whole-directory/file removal for a declined toggle happens in
  `_tasks_cleanup.py.jinja` (rendered to `_tasks_cleanup.py`, run once via `copier.yml`'s
  `_tasks`, then deleted) — **not** via Jinja-conditional filenames. When you add a new
  file that only makes sense for a given toggle, add its `rm(...)` line there too; nothing
  enforces this automatically and it's the single most common place to introduce a
  generation-time bug (ships file X in every project, but only wires it up for some).
- `_exclude` in `copier.yml` uses **gitignore-style pathspec matching**, not plain
  fnmatch — an unanchored pattern like `"README.md"` matches at *any* depth (it took out
  `evals/README.md` during this template's own build). Anchor with a leading `/` for
  anything meant to match only the template root: `/README.md`, `/CLAUDE.md`,
  `/copier.yml`, `/branding`, `/scripts/prepare_release.sh`.
- "Hub" files carry `{% if include_x %}` blocks for *every* component/service, not just
  one — they're the files most likely to break when you add a new toggle and forget one
  of them:
  `pyproject.toml.jinja`, `app/core/config.py.jinja`, `app/core/dependencies.py.jinja`,
  `app/main.py.jinja`, `app/api/v1/router.py.jinja`, `app/worker/main.py.jinja`,
  `tests/conftest.py.jinja`, `docker-compose.yml.jinja`, `_tasks_cleanup.py.jinja`.
  Everything else is component-local and only needs to know about its own toggle.
- The post-generation `_tasks` also run `uvx ruff check --fix .` (not `--select I` —
  the full default rule set, deliberately, so `F401` cleans up conditional imports that
  end up unused for whatever combination of toggles a given generation chose) and
  `uvx ruff format .`, then `git init` + an initial commit (required for `copier update`
  to have a merge base later).

## Testing a change — this repo is not directly runnable in place

Most files here are Jinja sources; there's no literal `pyproject.toml`, only
`pyproject.toml.jinja`. To test anything, generate an instance and run *that*:

```bash
copier copy . /tmp/dev-instance --trust --defaults \
  --data project_name="Test" --data author_name="You" --data author_email="you@example.com"
cd /tmp/dev-instance
uv sync --group docs   # --group docs only needed if you also want to build the docs site
uv run ruff check . && uv run ruff format --check . && uv run mypy app/ && uv run pytest
```

**If you touch a hub file, generate more than the defaults** — at minimum: everything
off except Backend+AI (live chat shape), Backend+Database+Worker+Auth+AI (async job
shape), and everything on. This template's own build caught several real bugs
(a worker dispatch bug, a missing `AppConfig` field, missing `__init__.py` files across
`app/`, a Langfuse crash-on-missing-keys, a missing mkdocs plugin dependency) *only*
because each combination was actually generated and run — not by reading the Jinja and
reasoning about it. Don't skip this.

If the Database component is involved, apply a real migration against a throwaway
Postgres rather than trusting that the model diffs look right:
```bash
export DATABASE_URL="postgresql+asyncpg://$(whoami)@localhost:5432/some_throwaway_db"
uv run alembic revision --autogenerate -m "initial schema" && uv run alembic upgrade head
```

To verify `copier update` itself still works after a change: commit the change here,
then inside a project generated from an *older* commit, run `copier update --trust`, and
confirm the expected diff actually lands.

## Publishing (personal vs. Wallero)

`branding/personal/` and `branding/wallero/` hold the only files that differ between the
two published copies (`README.md`, `LICENSE`, `CODEOWNERS`, `CONTRIBUTING.md`).
`scripts/prepare_release.sh <personal|wallero>` rsyncs this repo (minus `.git`,
`branding/`, and the script itself) into a sibling `ai-ml-service-template-<variant>/`
directory and overlays that variant's branding on top — it does not push anything.
Everything else (this `CLAUDE.md` included) is identical between the two.

## Planned

- Replace the unconditionally-rendered `CLAUDE.md.jinja` with an agent-agnostic
  `AGENTS.md.jinja` as the canonical file, and make `CLAUDE.md.jinja` a one-line pointer
  to it ("See AGENTS.md."). `AGENTS.md` is becoming the shared convention across coding
  agents (Claude Code, Cursor, Codex, Aider), so this covers whichever tool a generated
  project's developer uses without a new toggle — a toggle would need a new `copier.yml`
  question plus hub-file branches plus `_tasks_cleanup.py.jinja` entries, all avoidable
  since a pointer file works regardless of tool choice. Separately, decide whether to also
  parameterize which *agent framework* the AI service's own agent runs on (currently always
  LangGraph) — that one's a real structural toggle, not a docs-only change.

## Known gaps

- The Cache component (`app/infrastructure/cache.py`) is only unit-tested against a
  mocked Redis client — no live Redis was available in the environment this template was
  built in. Low risk (it's a thin wrapper), but worth a real integration pass eventually.
- Docker-based verification (actually running `docker compose up`) wasn't done — Docker
  wasn't available either. Everything was verified running the processes natively instead
  (`uv run uvicorn ...`, `uv run python -m app.worker.main`) against a real local Postgres
  and RabbitMQ. The compose files themselves are unverified beyond `docker compose config`
  -style reasoning about the Jinja output.
- No conditional-file-inclusion pattern exists yet for something needed only within one
  *specific* toggle combination (e.g. something needed only when Worker+Cache are both on
  but not otherwise) — every current toggle's needs are expressible as "this file exists
  iff toggle X is on," which covers everything so far but won't automatically if a future
  component/service is genuinely cross-cutting.
