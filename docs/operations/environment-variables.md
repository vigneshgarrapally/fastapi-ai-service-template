# Configuration & Environment Variables

Configuration is split in two (`app/core/config.py`):

- **Secrets** (API keys, connection strings, the auth salt) live **only** in the
  environment / `.env` file, using flat variable names. Loaded by the `Secrets`
  model and never appear in `config.yaml`.
- **Everything else** (pool sizes, timeouts, provider choice, temperature) lives in a
  single committed **`config.yaml`** at the repo root, grouped by area. Each group
  maps to a nested sub-model on `Settings`.

**Source precedence (highest wins):**

```
environment variable  →  .env file  →  config.yaml  →  field default
```

!!! note "Overriding a non-secret value per environment"
    Edit `config.yaml` and restart — no code change or image rebuild needed. To
    override a single value for one environment **without** editing the file, set an
    environment variable using the `__` nested delimiter:
    `DATABASE__POOL_SIZE=20`, `AI__TEMPERATURE=0.5`, `APP__LOG_LEVEL=DEBUG`.

!!! warning "Missing config file fails fast"
    If `config.yaml` (or the path in `CONFIG_FILE`) does not exist, `get_settings()`
    raises `FileNotFoundError` at startup rather than silently falling back to
    field defaults.

| Variable | Default | Description |
|---|---|---|
| `CONFIG_FILE` | `config.yaml` | Path to the yaml config file. Set this in Docker/tests if the file lives at a non-default path |

Every row below is gated by the component/service that owns it — a generated project
that declined a component simply never reads that row's variable (the field doesn't
exist on `Settings` at all, since the whole config class is conditionally rendered).

---

## Secrets (`.env`)

Flat environment-variable names. Must **never** be committed to `config.yaml`. Empty
defaults keep the AI service's provider secrets silently absent (each provider
surfaces its own `ValueError` at startup if selected without its key) — but the
Langfuse pair is **not** in that category, see the warning below the table.

| Variable | Requires | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Database | `postgresql+asyncpg://postgres:postgres@localhost:5432/<db_name>` | PostgreSQL connection string. Must use the `postgresql+asyncpg://` scheme |
| `RABBITMQ_URL` | Worker | `amqp://guest:guest@localhost/` | AMQP connection URL |
| `REDIS_URL` | Cache | `redis://localhost:6379/0` | Redis connection URL |
| `API_KEY_SALT` | Auth | `change-me-in-production` | Secret mixed into the SHA-256 hash of every API key. **Change before any real deployment** |
| `OPENAI_API_KEY` | AI service | `""` | Required when `ai.llm.provider=openai` |
| `AZURE_OPENAI_API_KEY` | AI service | `""` | Required when `ai.llm.provider=azure_openai` |
| `LANGFUSE_PUBLIC_KEY` | Observability | `""` | Langfuse project public key. Leave empty to disable LLM tracing specifically — see note below |
| `LANGFUSE_SECRET_KEY` | Observability | `""` | Langfuse project secret key. Same as above |

!!! note "Langfuse degrades gracefully; OTel/Prometheus don't need it"
    `app/core/observability.py::init_langfuse()` no-ops (logs `langfuse.disabled`
    and returns a disconnected instance) when either key is empty — it does not
    raise, and does not block startup. Enabling the Observability component
    without Langfuse credentials still gets you OTel tracing and the Prometheus
    `/metrics` endpoint; you only lose LLM-specific tracing until both keys are
    set. Every method on the returned instance (`start_trace_span`,
    `get_langchain_handler`, `create_score`, ...) already checks
    `is_connected` and no-ops safely when disconnected.

---

## Config (`config.yaml`) reference

Each key below lives under its group in `config.yaml`. The **Env override** column
shows the variable name using the `__` nested-delimiter convention — set it instead
of editing the file to override a single value for one environment.

### `app` — always present

| Key | Default | Env override | Description |
|---|---|---|---|
| `app_name` | project name at generation time | `APP__APP_NAME` | Service name in logs and the OpenAPI schema |
| `app_version` | `0.1.0` | `APP__APP_VERSION` | Semver string in the OpenAPI schema |
| `environment` | `development` | `APP__ENVIRONMENT` | `development` \| `local` \| `staging` \| `production`. Controls log format |
| `debug` | `false` | `APP__DEBUG` | Forces `log_level` to `DEBUG` |
| `host` | `0.0.0.0` | `APP__HOST` | Uvicorn bind address (requires Backend) |
| `port` | `8000` | `APP__PORT` | Uvicorn listen port (requires Backend) |
| `allowed_origins` | `["*"]` | `APP__ALLOWED_ORIGINS` | CORS allowed origins (requires Backend). Restrict this in production |
| `log_level` | `INFO` | `APP__LOG_LEVEL` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL` |

### `database` — requires Database

SQLAlchemy async engine connection pool sizing. Each process (API, worker) creates
its own pool — total Postgres connections scale as roughly
`(pool_size + max_overflow) × number of running processes`.

| Key | Default | Env override | Description |
|---|---|---|---|
| `pool_size` | `10` | `DATABASE__POOL_SIZE` | Persistent connections kept open per process |
| `max_overflow` | `20` | `DATABASE__MAX_OVERFLOW` | Extra connections allowed above `pool_size` under burst load |

### `worker` — requires Worker

| Key | Default | Env override | Description |
|---|---|---|---|
| `prefetch` | `5` | `WORKER__PREFETCH` | RabbitMQ consumer prefetch count |
| `max_retries` | `3` | `WORKER__MAX_RETRIES` | Declared for future retry logic — the shipped worker currently makes one attempt per message and dead-letters on failure; see [Failure Paths](../flows/failure-paths.md) |
| `idem_ttl_hours` | `24` | `WORKER__IDEM_TTL_HOURS` | Idempotency record TTL |
| `idem_cleanup_interval_seconds` | `3600` | `WORKER__IDEM_CLEANUP_INTERVAL_SECONDS` | How often the background task deletes expired `idempotency_records` rows |

### `cache` — requires Cache

| Key | Default | Env override | Description |
|---|---|---|---|
| `default_ttl_seconds` | `3600` | `CACHE__DEFAULT_TTL_SECONDS` | Default TTL for cache entries that don't specify their own |

### `observability` — requires Observability

Secret keys (`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`) live in `.env` — see
Secrets above. Only non-secret values live here.

| Key | Default | Env override | Description |
|---|---|---|---|
| `langfuse_host` | `https://cloud.langfuse.com` | `OBSERVABILITY__LANGFUSE_HOST` | Langfuse server (cloud or self-hosted) |
| `otel_endpoint` | `""` | `OBSERVABILITY__OTEL_ENDPOINT` | OTLP gRPC endpoint, e.g. `otel-collector:4317`. Empty disables tracing |
| `otel_service_name` | `""` | `OBSERVABILITY__OTEL_SERVICE_NAME` | Service name in OTel traces. Defaults to `app.app_name` when empty |

### `ai` — requires AI service

| Key | Default | Env override | Description |
|---|---|---|---|
| `llm.provider` | `azure_openai` | `AI__LLM__PROVIDER` | LLM backend: `ollama` \| `openai` \| `azure_openai` |
| `llm.azure_openai.endpoint` | `""` | `AI__LLM__AZURE_OPENAI__ENDPOINT` | Azure resource URL, e.g. `https://<resource>.openai.azure.com/` |
| `llm.azure_openai.deployment` | `gpt-4o` | `AI__LLM__AZURE_OPENAI__DEPLOYMENT` | Deployment name |
| `llm.azure_openai.api_version` | `2024-02-01` | `AI__LLM__AZURE_OPENAI__API_VERSION` | Azure OpenAI API version string |
| `llm.openai.base_url` | `https://api.openai.com/v1` | `AI__LLM__OPENAI__BASE_URL` | OpenAI base URL |
| `llm.openai.model` | `gpt-4o` | `AI__LLM__OPENAI__MODEL` | OpenAI model name |
| `llm.ollama.base_url` | `http://localhost:11434/v1` | `AI__LLM__OLLAMA__BASE_URL` | Ollama server base URL |
| `llm.ollama.model` | `llama3.1` | `AI__LLM__OLLAMA__MODEL` | Ollama model name |
| `llm.timeout_s` | `30` | `AI__LLM__TIMEOUT_S` | Per-call LLM timeout in seconds |
| `llm.max_retries` | `4` | `AI__LLM__MAX_RETRIES` | Max retry attempts for transient LLM failures |
| `llm.max_tokens` | `4000` | `AI__LLM__MAX_TOKENS` | Ceiling on the response token budget |
| `temperature` | `0.3` | `AI__TEMPERATURE` | Sampling temperature for the conversational agent |
| `max_history_messages` | `20` | `AI__MAX_HISTORY_MESSAGES` | How many prior turns the agent keeps in a session's memory |

---

## `.env` Quickstart (secrets only)

```dotenv
# Database component
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/<db_name>

# Worker component
RABBITMQ_URL=amqp://guest:guest@localhost/

# Cache component
REDIS_URL=redis://localhost:6379/0

# Auth service — CHANGE THIS
API_KEY_SALT=generate-a-random-secret-here

# AI service — set whichever provider ai.llm.provider points at
AZURE_OPENAI_API_KEY=YOUR_AZURE_OPENAI_KEY   # if provider=azure_openai
# OPENAI_API_KEY=sk-...                       # if provider=openai
# (ollama needs no API key — it's a local, unauthenticated server)

# Observability component (optional)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

!!! tip "Non-secret config goes in `config.yaml`"
    Endpoint URLs, deployment names, model names, pool sizes, prefetch counts, and
    timeouts are **not** secrets — set them in `config.yaml`, or override per
    environment with a nested env var (e.g. `AI__LLM__AZURE_OPENAI__ENDPOINT=...`).
