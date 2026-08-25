# API Endpoints Overview

All endpoints are mounted under `/api/v1` (`app/api/v1/router.py`). Every route
except `GET /api/v1/health` and `GET /metrics` requires the `X-API-Key` header when
the Auth service is included — see [Auth Flow](../flows/auth-flow.md).

!!! note "Interactive reference"
    FastAPI generates a live OpenAPI schema for every route below at `/openapi.json`.
    Point any interactive API client (Swagger UI, Scalar, Postman) at it for a
    request-by-request try-it-out console — this page documents intent and examples,
    not a substitute for the generated schema.

---

## `GET /api/v1/health`

Liveness/readiness probe. **Never requires `X-API-Key`.** Not included in the OpenAPI
schema — it's an infrastructure endpoint, not a product API.

| Query param | Values | Default | Behavior |
|---|---|---|---|
| `probe` | `liveness` \| `readiness` | `liveness` | `liveness` never makes an external call — it only confirms the process itself is responsive. `readiness` pings every enabled dependency |

**Liveness** — always `200`:

```json
{
  "status": "healthy",
  "probe": "liveness",
  "timestamp": "2026-08-24T10:15:00.123456+00:00"
}
```

**Readiness** — pings Postgres (Database), RabbitMQ (Worker), and the LLM provider
(AI service), whichever are included:

```json
{
  "status": "degraded",
  "probe": "readiness",
  "timestamp": "2026-08-24T10:15:00.123456+00:00",
  "services": {
    "postgres": { "status": "up", "latency_ms": 4 },
    "rabbitmq": { "status": "down", "error": "not connected: job_publisher" },
    "llm": { "status": "up" }
  }
}
```

| Overall `status` | HTTP | Trigger |
|---|---|---|
| `healthy` | 200 | Every enabled dependency reports `up` |
| `degraded` | 200 | RabbitMQ and/or the LLM provider is `down`, but Postgres is `up` (or Database isn't included) |
| `unhealthy` | 503 | Postgres reports `down` |

Postgres is the only **hard** dependency — RabbitMQ and the LLM provider being
unreachable still returns `200` so the pod stays in rotation (it can still serve
the sync `/chat` path, or requests that don't touch the down dependency).

---

## `POST /api/v1/chat`

Requires the AI service. Synchronous conversational turn — call the LangGraph agent
and return its reply in the same request/response cycle. Requires `X-API-Key` when
Auth is included.

**Request:**

```json
{
  "session_id": "6f1c1e2a-9b3d-4e7a-8f2b-1a2b3c4d5e6f",
  "message": "What's the status of order #4521?"
}
```

**Response — `200`:**

```json
{
  "session_id": "6f1c1e2a-9b3d-4e7a-8f2b-1a2b3c4d5e6f",
  "reply": "Order #4521 shipped yesterday and is expected to arrive Thursday."
}
```

`session_id` is client-generated (or omitted for a fresh session, depending on the
agent's own session-creation contract) and threaded through to scope the agent's
conversational memory — see [AI Service Flows](../flows/ai-service.md#synchronous-chat).

---

## `POST /api/v1/chat/jobs`

Requires **both** the AI service and the Worker component. Async submit — the same
conversational turn as `POST /chat`, but queued for the worker to process instead of
blocking the request. Requires `X-API-Key` when Auth is included, and always requires
`X-Idempotency-Key`.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-API-Key` | If Auth included | Caller authentication |
| `X-Idempotency-Key` | **Yes** — a FastAPI `Header(...)` with no default, so a missing header is a `422`, not a custom error | Client-generated key identifying this submission attempt. A retry with the same key and the same body replays the original `202` response instead of enqueuing a second job — see [Failure Paths](../flows/failure-paths.md#idempotency-claimcompletefail-protocol) |

**Request:**

```json
{
  "session_id": "6f1c1e2a-9b3d-4e7a-8f2b-1a2b3c4d5e6f",
  "message": "Summarize the last 90 days of support tickets for account 4521."
}
```

**Response — `202 Accepted`:**

```json
{
  "job_id": "d3e4f5a6-b7c8-49d0-9e1f-2a3b4c5d6e7f",
  "status": "queued"
}
```

A retry with the same `X-Idempotency-Key` and an unchanged body returns this exact
cached payload again — `status` will still read `"queued"` even if the job has since
finished, since this response is a snapshot from submission time, not a live status
read. Poll `GET /chat/jobs/{job_id}` for the current status. A retry that arrives
**while the original submission is still being processed** gets a `409` instead (see
[Error Catalog](error-catalog.md#http-409-conflict)) — there is no block-and-wait.

---

## `GET /api/v1/chat/jobs/{job_id}`

Requires **both** the AI service and the Worker component. Poll for the result of a
job submitted via `POST /chat/jobs`. Requires `X-API-Key` when Auth is included.

**Response — `200`, still running:**

```json
{
  "job_id": "d3e4f5a6-b7c8-49d0-9e1f-2a3b4c5d6e7f",
  "status": "processing",
  "result": null,
  "error": null
}
```

**Response — `200`, completed:**

```json
{
  "job_id": "d3e4f5a6-b7c8-49d0-9e1f-2a3b4c5d6e7f",
  "status": "completed",
  "result": {
    "reply": "Over the last 90 days, account 4521 opened 12 tickets — 9 resolved, 3 open, median resolution time 1.8 days."
  },
  "error": null
}
```

**Response — `200`, failed:**

```json
{
  "job_id": "d3e4f5a6-b7c8-49d0-9e1f-2a3b4c5d6e7f",
  "status": "failed",
  "result": null,
  "error": "LLM call timed out after 30s"
}
```

`status` mirrors `jobs.status`: `queued` \| `processing` \| `completed` \| `failed`.
See `GET /api/v1/chat/jobs/{job_id}` in [Error Catalog](error-catalog.md) for the
`404` case.

---

## `GET /metrics`

Present when Observability is included. Prometheus scrape endpoint. Never requires
`X-API-Key` — same exemption as `/health`, since it's an infrastructure endpoint
scraped from inside the deployment's own network, not called by product clients.
