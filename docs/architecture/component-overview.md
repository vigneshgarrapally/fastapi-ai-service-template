# Component Overview

How the API process, the worker process, and the surrounding infrastructure fit
together.

!!! note "Optional components"
    Database, Worker, Cache, and Observability are all independently togglable
    components (see `copier.yml`). The diagram below shows the **full** template —
    a given generated project only contains the boxes for the components it selected.
    The Worker process and everything downstream of RabbitMQ only exists when the
    Worker component is included, which itself requires the Database component.

---

## High-Level Component Map

```mermaid
flowchart TD
    subgraph API["API Process — app/main.py"]
        MW["Middleware Stack<br/>CORS · RequestContext · OTel · Prometheus"]
        EP_H["Health Endpoint<br/>GET /api/v1/health"]
        EP_C["Chat Endpoints<br/>POST /api/v1/chat<br/>POST /api/v1/chat/jobs<br/>GET /api/v1/chat/jobs/{job_id}"]
        MW --> EP_H & EP_C
    end

    subgraph WORKER["Worker Process — app/worker/main.py (optional: Worker component)"]
        JOB_H["Job Handler<br/>app/worker/ai_job_worker.py"]
        IC_W["Idempotency Cleanup Task<br/>app/worker/idempotency_cleanup.py"]
    end

    subgraph AI["AI Service — app/features/ai/ (optional: AI service)"]
        AGENT["LangGraph Conversational Agent"]
        LLM_BASE["LLM Provider Interface<br/>app/llm/base.py"]
        LLM_FACT["Provider Factory<br/>app/llm/factory.py"]
    end

    subgraph DB_LAYER["Database — app/db/ (optional: Database component)"]
        REPOS["Repositories<br/>jobs · idempotency · api_keys"]
        PG_SA["SQLAlchemy AsyncSession<br/>app/db/postgres.py"]
    end

    PG[("PostgreSQL")]
    MQ([RabbitMQ])
    REDIS[("Redis (optional: Cache component)")]
    LF["Langfuse (optional: Observability)"]
    OTEL["OTel Collector (optional: Observability)"]

    EP_C -->|"sync call"| AGENT
    EP_C -->|"publish job (async path)"| MQ
    EP_C -->|"write Job row"| REPOS
    LLM_FACT -->|"provider=azure_openai\xa0|\xa0openai\xa0|\xa0ollama"| PROVIDER["Configured Provider<br/>Azure OpenAI / OpenAI / Ollama"]
    AGENT -.->|"builds its own LangChain chat model<br/>from the same ai.llm.* settings —<br/>bypasses LLM_BASE/LLM_FACT, see<br/>ADR: LLM Provider Switching"| PROVIDER

    MQ -->|"ai.jobs.q"| JOB_H
    JOB_H --> AGENT
    JOB_H --> REPOS

    REPOS --> PG_SA --> PG
    EP_H -.->|"readiness probe via get_llm()"| PG
    EP_H -.->|"readiness probe via get_llm()"| MQ
    EP_H -.->|"readiness probe via get_llm()"| LLM_FACT
    LLM_FACT -.-> PROVIDER

    MW -.->|"traces"| OTEL
    LF -.->|"LLM call tracing —<br/>helper exists (get_langchain_handler()) but<br/>nothing in graph.py/service.py calls it yet"| AGENT

    EP_C -.->|"session state (optional)"| REDIS
```

---

## Dependency Injection Pattern

All cross-cutting concerns are `Annotated` type aliases in `app/core/dependencies.py`.
Endpoints declare them as function parameters — no direct instantiation of
infrastructure in handlers.

```python
# How it looks in an endpoint
async def chat(
    request: ChatRequest,
    llm: LLMDep,             # configured LLM provider singleton
    session: SessionDep,     # SQLAlchemy AsyncSession, if Database is included
) -> ChatResponse: ...
```

| Alias | Provides | Requires |
|---|---|---|
| `SettingsDep` | `Settings` singleton (env + `config.yaml`) | always |
| `SessionDep` | SQLAlchemy `AsyncSession` (per-request) | Database |
| `ApiKeyRepoDep` | `ApiKeyRepository` | Database + Auth |
| `LLMDep` | `LLMProvider` singleton (the AI service's configured provider) | AI service |
| `CacheDep` | Redis `CacheClient` singleton | Cache |

---

## RabbitMQ Topology

Requires the Worker component. One exchange/queue family for the AI service's async
job type — see [Failure Paths](../flows/failure-paths.md) for the retry/dead-letter
behavior.

```mermaid
flowchart LR
    EX["ai.jobs<br/>direct exchange, durable"]
    Q["ai.jobs.q<br/>durable queue"]
    DLX["ai.jobs.dlx<br/>fanout exchange, durable"]
    DLQ["ai.jobs.dlq<br/>durable queue"]

    EX -->|"routing key: submit"| Q
    Q -->|"rejected / requeue=false"| DLX --> DLQ
```

To add a second job type, declare a second exchange + queue + DLX + DLQ pair
(`app/infrastructure/rabbitmq.py`'s own comment recommends this) rather than
overloading the single `ai.jobs.q` queue with multiple message shapes.

---

## Application Startup Sequence

Order matters: each step in `app/main.py`'s `lifespan()` depends on the ones before
it, and if any step raises, the remaining steps are skipped and the process never
starts accepting requests.

```mermaid
sequenceDiagram
    autonumber
    participant UV as Uvicorn
    participant APP as FastAPI lifespan
    participant DB as PostgreSQL
    participant LLM as LLM Provider
    participant MQ as RabbitMQ
    participant CACHE as Redis
    participant LF as Langfuse

    UV->>APP: start lifespan
    APP->>DB: init_engine(pool_size, max_overflow) — Database only
    APP->>DB: verify_connection() — SELECT 1, raises on failure
    Note over APP,DB: Unreachable/misconfigured DB crashes the process here —<br/>fails fast instead of serving requests against a broken connection
    APP->>LLM: init_llm(settings) — AI service only
    APP->>MQ: connect() — Worker only
    APP->>CACHE: init_cache_client() — Cache only
    APP->>LF: init_langfuse() — Observability only<br/>(raises if LANGFUSE_PUBLIC_KEY/SECRET_KEY are unset — not a no-op, see<br/>Environment Variables — Secrets)
    APP-->>UV: yield ← server starts accepting requests

    Note over UV,LF: Shutdown (SIGTERM)
    UV->>APP: shutdown signal
    APP->>LF: shutdown_langfuse() + shutdown_tracing() — Observability only
    APP->>MQ: disconnect() — Worker only
    APP->>CACHE: close_cache_client() — Cache only
    APP->>DB: dispose_engine() — Database only
```

The unified worker entry point (`app/worker/main.py`, run via
`uv run python -m app.worker.main`) follows the same connect-then-verify order —
`init_engine()` + `verify_connection()` before it declares any RabbitMQ topology or
starts consuming — so a broken database exits the worker before it ever touches the
queue.

---

## Module Ownership

| Module | Responsibility |
|---|---|
| `app/core/` | Auth, config, middleware, DI wiring, observability |
| `app/api/v1/endpoints/` | HTTP layer only — validation, delegation to features |
| `app/features/` | Business logic (the AI service's conversational agent) |
| `app/worker/` | Consumer loop, job dispatch, background cleanup tasks |
| `app/db/` | PostgreSQL access — SQLAlchemy ORM models + repositories |
| `app/infrastructure/` | External service clients (RabbitMQ, Redis) |
| `app/llm/` | LLM provider abstraction (config, factory, provider implementations) |
| `evals/` | LLM-as-judge scoring harness for the AI service's output quality — not part of the pytest suite |
