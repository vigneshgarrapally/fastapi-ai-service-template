# AI-ML Service Template

A [Copier](https://copier.readthedocs.io/) template I built for standing up new AI-ML
projects fast — FastAPI + Postgres + RabbitMQ + a pluggable LLM provider abstraction (Azure
OpenAI / OpenAI / Ollama, swap with one env var), with everything past the core spine —
auth, an async job worker, caching, observability, a docs site, and the AI agent itself — as
independent, generation-time yes/no toggles instead of one fixed shape.

It grew out of patterns proven in a production FastAPI service I've worked on, then
generalized into something reusable for the next project rather than starting from scratch
each time.

## Use it

```bash
uvx copier copy gh:vigneshgarrapally/fastapi-ai-service-template my-new-project
cd my-new-project
```

You'll be asked a short series of questions (project name, which components/services to
include, default LLM provider) — see [`copier.yml`](copier.yml) for the full list. Then follow
the generated project's own `SETUP.md`.

## What's always included

`uv`, `ruff` + pre-commit, GitHub Actions CI, a `tests/` skeleton, structured logging
(structlog), and a secrets/`.env`-vs-`config.yaml` settings split.

## What's toggleable

**Components** (infra primitives): Backend (FastAPI), Database (Postgres + Alembic), Worker
(RabbitMQ async job runtime), Cache (Redis), Observability (Langfuse + OTel +
Prometheus/Grafana), Docs site (MkDocs + Mermaid).

**Services** (business capabilities): Auth (X-API-Key), AI (LLM provider abstraction + a
LangGraph conversational agent with tool-calling and memory + an LLM-as-judge evals harness
scoring its own output).

## Keeping a generated project in sync

```bash
cd my-existing-project
uvx copier update
```

Copier 3-way-merges whatever's changed here since that project was generated — a template
improvement (a security fix, a CI upgrade) doesn't have to be manually ported into every
project that already used it.

## Why Copier

I compared Cookiecutter, Cookiecutter+cruft, and Copier before building this. Copier won on
the criteria that mattered most here: `copier update`'s native 3-way merge (vs. bolting `cruft`
onto Cookiecutter for the same thing), and it doesn't force every generated file one directory
level deeper the way Cookiecutter's `{{cookiecutter.project_slug}}/` convention does — this
repo's layout is the same shape as anything generated from it.
