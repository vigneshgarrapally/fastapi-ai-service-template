# Local Setup

Get the generated service running on your machine.

---

## Prerequisites

| Tool | Minimum Version | Install |
|---|---|---|
| Python | 3.13 | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| process-compose | latest | See [Step 5](#5-start-the-service) — optional, but the recommended way to run the API/worker/docs processes natively in one terminal |
| Docker | latest | Only needed if you run Postgres/RabbitMQ/Redis via `docker compose` instead of native installs |

### Infrastructure (if Database / Worker / Cache are included)

The generated `docker-compose.yml` includes `postgres`, `rabbitmq`, and `redis`
services gated behind their respective components — the quickest way to get
dependencies running locally is:

```bash
docker compose up -d postgres rabbitmq redis   # only the services your project actually included
```

=== "Native install instead of Docker"
    ```bash
    # Mac
    brew install postgresql@16 rabbitmq redis
    brew services start postgresql@16
    brew services start rabbitmq
    brew services start redis

    # Linux (Debian/Ubuntu)
    sudo apt install -y postgresql postgresql-client rabbitmq-server redis-server
    sudo systemctl enable --now postgresql rabbitmq-server redis-server
    ```
    Create the database (name matches `project_slug` with `-` replaced by `_`):
    ```bash
    createdb <project_slug_with_underscores>
    ```

---

## 1. Install Dependencies

```bash
uv sync
```

Add the `docs` group if you're working on this documentation site:

```bash
uv sync --all-groups
```

---

## 2. Configure Environment

```bash
cp .env.example .env
```

`.env` holds **secrets only** — connection strings, API keys, the auth salt. Fill in
whichever of these your generated project actually includes (see
[Environment Variables — Secrets](environment-variables.md#secrets-env) for the
complete, generation-independent list):

```dotenv
# Database component
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/<db_name>

# Worker component
RABBITMQ_URL=amqp://guest:guest@localhost/

# Cache component
REDIS_URL=redis://localhost:6379/0

# Auth service
API_KEY_SALT=local-dev-salt-change-me

# AI service — set whichever provider ai.llm.provider points at
AZURE_OPENAI_API_KEY=<key>
# OPENAI_API_KEY=sk-...

# Observability component — required if included, the app won't start without both
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

!!! warning "Langfuse keys are required, not optional, once Observability is included"
    Unlike the rest of this template's optional secrets, leaving these two empty
    doesn't disable tracing — it crashes startup. See
    [Environment Variables — Secrets](environment-variables.md#secrets-env) for why.

Everything that isn't a secret — provider endpoints, deployment names, temperature,
pool sizes, prefetch counts — lives in `config.yaml` at the repo root, or can be
overridden per environment with a `GROUP__FIELD` env var:

```yaml
ai:
  llm:
    provider: "azure_openai"
    azure_openai:
      endpoint: "https://<resource>.openai.azure.com/"
      deployment: "gpt-4o"
```

See [Environment Variables](environment-variables.md) for the full reference and the
`__` nested-delimiter override syntax.

---

## 3. Run Database Migrations

Only if the Database component is included:

```bash
uv run alembic upgrade head
```

Run this on first clone and after every pull that includes new Alembic revisions.
After editing an ORM model in `app/db/models/`, generate a new migration:

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

---

## 4. Create an API Key

Only if the Auth service is included:

```bash
uv run python scripts/manage_api_keys.py create --label "local-dev"
```

Prints the raw key once — save it, it can't be recovered. See
[Auth Flow — Issuing and Revoking Keys](../flows/auth-flow.md#issuing-and-revoking-keys)
for the other subcommands (`list`, `deactivate`, `reactivate`, `delete`).

---

## 5. Start the Service

=== "process-compose (recommended, native)"
    ```bash
    process-compose up
    ```
    One command, one terminal, colour-coded per-process logs. Runs whichever of the
    `api` (`uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`),
    `worker` (`uv run python -m app.worker.main`), and `docs`
    (`uv run mkdocs serve -a 0.0.0.0:8001` — note the non-default port, since `:8000`
    is already the API's) processes the generated project included, restarting any
    of them up to 5 times on failure. Requires Postgres/RabbitMQ already running
    (natively or via `docker compose up -d postgres rabbitmq redis`) — see
    `process-compose.yaml` for the exact process definitions.

    Install it once per machine:
    ```bash
    # Mac
    brew install f1bonacc1/tap/process-compose
    # Linux
    sh -c "$(curl -L https://raw.githubusercontent.com/F1bonacc1/process-compose/main/scripts/get-pc.sh)" -- -d -b ~/.local/bin
    ```

    Run a subset: `process-compose up api worker` (skip `docs`).

=== "Pieces individually"
    ```bash
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000   # Backend
    uv run python -m app.worker.main                                    # Worker, in a second terminal
    ```
    The worker connects to Postgres and RabbitMQ, starts the idempotency-cleanup
    background task, and consumes `ai.jobs.q` — one process, one entry point.

=== "Docker Compose (full stack)"
    ```bash
    docker compose up -d --build
    ```
    Builds and starts every included service — `postgres`/`rabbitmq`/`redis`
    (components), the one-shot `migrate` runner, `fastapi`, and `worker` — wired
    together on the compose network. `docker-compose.override.yml` layers on hot
    reload for local dev automatically.

---

## 6. Run Tests

```bash
# Full suite
uv run pytest

# Single file
uv run pytest tests/api/v1/test_health.py

# All quality gates
uv run ruff check app/ --fix && \
uv run ruff format app/ && \
uv run mypy app/ && \
uv run pytest
```

!!! note "evals/ is separate from tests/"
    If the AI service is included, `evals/` holds an LLM-as-judge harness that scores
    the agent's output quality (relevancy, helpfulness, hallucination) — it is not
    part of the pytest suite and is not run by `uv run pytest`. Run it directly:
    ```bash
    uv run python -m evals.main
    ```

---

## Building the Docs Site

Only if the Docs site component is included.

```bash
uv run mkdocs serve   # live-reload dev server at http://localhost:8000
uv run mkdocs build   # static build to site/
```

!!! warning "`mkdocs serve` does NOT pre-render Mermaid — it looks different from the real build"
    Mermaid diagrams are pre-rendered to static SVG **at `mkdocs build` time** (not
    client-side JS) by `mkdocs-mermaid-to-svg`, and are click-to-zoom via
    `mkdocs-glightbox`. `mkdocs-mermaid-to-svg` hardcodes
    `is_serve_mode = "serve" in sys.argv` and returns the page unmodified when true —
    under `mkdocs serve`, diagrams fall back to Material's default client-side
    renderer (`mermaid.js`, loaded from a CDN), producing an inline `<svg>` in the DOM
    rather than a real image file. That means, in `serve` mode: right-click gives no
    "Save Image As" / "Open image in new tab" (browsers only offer those for real
    `<img>`/`<canvas>` resources, not inline SVG), and glightbox's zoom won't behave
    the same way either. There is no config flag to force pre-rendering during serve.
    **To verify a diagram's real, shipped behavior — zoom, save, open-in-new-tab —
    run `mkdocs build` and serve the static `site/` output**
    (e.g. `python3 -m http.server 8000 --directory site`), not `mkdocs serve`. Use
    `mkdocs serve` only for fast content iteration; don't treat what it renders as
    final.

Pre-rendering requires **Node.js + `@mermaid-js/mermaid-cli`** on the machine running
`mkdocs build`:

```bash
npm install -g @mermaid-js/mermaid-cli
# One-time: download the headless Chrome revision mermaid-cli's puppeteer-core
# expects. If mkdocs build fails with "Could not find Chrome (ver. X.Y.Z...)",
# install that exact revision:
npx puppeteer browsers install chrome-headless-shell@<version from the error message>
```

`uv sync --all-groups` installs the Python side; the Node.js toolchain above is
separate and only needed to build the docs, not to run the application.

---

## Using a Local LLM (No Cloud Credentials Required)

=== "Ollama"
    ```yaml
    ai:
      llm:
        provider: "ollama"
        ollama:
          base_url: "http://localhost:11434/v1"
          model: "llama3.1"
    ```
    Env var equivalent:
    ```dotenv
    AI__LLM__PROVIDER=ollama
    AI__LLM__OLLAMA__BASE_URL=http://localhost:11434/v1
    AI__LLM__OLLAMA__MODEL=llama3.1
    ```
    Start it: `ollama pull llama3.1 && ollama serve`

=== "OpenAI"
    ```yaml
    ai:
      llm:
        provider: "openai"
        openai:
          base_url: "https://api.openai.com/v1"
          model: "gpt-4o"
    ```
    The API key is a secret — set `OPENAI_API_KEY` in `.env`, never in `config.yaml`.

See [ADR: LLM Provider Switching](../decisions/llm-provider-switching.md) for the
full rationale.

---

## Common Issues

**Postgres / RabbitMQ / Redis connection refused**

Check `DATABASE_URL` / `RABBITMQ_URL` / `REDIS_URL` in `.env` match your running
instances, and that the services are actually up (`docker compose ps`, or
`brew services list` / `systemctl status postgresql rabbitmq-server redis-server`
for a native install).

**`alembic upgrade head` fails with "relation already exists"**

The database was created from an older snapshot or a competing migration. Reset with:

```bash
uv run alembic downgrade base
uv run alembic upgrade head
```

**LLM call times out or fails**

Tests mock the LLM provider, so this only affects real calls against a live
endpoint. Raise the per-call timeout in `config.yaml` (not `.env` — it isn't a
secret):

```dotenv
AI__LLM__TIMEOUT_S=60
```
