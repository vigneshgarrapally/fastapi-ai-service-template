# Error Catalog

Every error response in this template follows FastAPI's default shape — a plain
string under `detail`, except `422` validation errors, which use FastAPI's own
`loc`/`msg`/`type` list shape:

```json
{ "detail": "<message>" }
```

---

## HTTP 401 Unauthorized

Requires the Auth service.

| Cause | Endpoint |
|---|---|
| `X-API-Key` header absent | Any endpoint except `/health` and `/metrics` |
| `X-API-Key` present but no matching active row in `api_keys` | Any endpoint except `/health` and `/metrics` |

```json
{ "detail": "Missing API key" }
```

```json
{ "detail": "Invalid API key" }
```

**Resolution:** issue a new key with
`uv run python scripts/manage_api_keys.py create --label "..."`, or confirm the
existing one is still active with `... list` — see
[Auth Flow — Issuing and Revoking Keys](../flows/auth-flow.md#issuing-and-revoking-keys).

---

## HTTP 404 Not Found

| Cause | Endpoint |
|---|---|
| `job_id` does not exist in `jobs` | `GET /api/v1/chat/jobs/{job_id}` |

```json
{ "detail": "Job not found" }
```

---

## HTTP 409 Conflict

Requires the Worker component (the async chat-job path is the only endpoint that
takes `X-Idempotency-Key`). Both cases return a **plain string** `detail` — FastAPI's
default shape, not a structured `{error, detail}` object.

| Cause | Endpoint |
|---|---|
| Same `X-Idempotency-Key` used with a request body whose fingerprint doesn't match the original claim | `POST /api/v1/chat/jobs` |
| Same `X-Idempotency-Key` reused while the original submission is still `processing` (or completed with no cached response, an edge case that shouldn't normally occur) | `POST /api/v1/chat/jobs` |

```json
{ "detail": "X-Idempotency-Key was already used with a different request body" }
```

```json
{ "detail": "A request with this idempotency key is already being processed" }
```

See [ADR: Idempotency](../decisions/idempotency.md) for why the fingerprint check
exists, and [Failure Paths](../flows/failure-paths.md#idempotency-claimcompletefail-protocol)
for the full claim protocol — including why the second case is a `409`, not a
block-and-wait or a `202` with the original `job_id`.

---

## HTTP 422 Unprocessable Entity

| Cause | Endpoint |
|---|---|
| Pydantic request-body validation failure (missing `message`, wrong type, etc.) | `POST /api/v1/chat`, `POST /api/v1/chat/jobs` |
| `X-Idempotency-Key` header absent — it's a required FastAPI `Header(...)` parameter with no default, so a missing header fails request validation rather than being checked in handler code | `POST /api/v1/chat/jobs` |

FastAPI's default validation error shape (a `loc`/`msg`/`type` list under `detail`).

---

## HTTP 500 Internal Server Error

| Cause | Endpoint |
|---|---|
| Unhandled exception (LLM call failure, RabbitMQ publish failure, etc.) | Any |

Falls through to the global exception handler (`app/core/exceptions.py`), which logs
the full traceback via `structlog` and returns:

```json
{ "detail": "Internal server error" }
```

In `development`/`debug` mode the response additionally includes `exception` and
`traceback` fields — never enabled in `staging`/`production`.

---

## HTTP 503 Service Unavailable

| Cause | Endpoint |
|---|---|
| PostgreSQL unreachable | `GET /api/v1/health?probe=readiness` |

```json
{
  "status": "unhealthy",
  "probe": "readiness",
  "timestamp": "2026-08-24T10:15:00.123456+00:00",
  "services": { "postgres": { "status": "down", "error": "..." } }
}
```

!!! note "RabbitMQ/LLM down is not a 503"
    If RabbitMQ or the LLM provider is unreachable but PostgreSQL is up (or Database
    isn't included), `GET /api/v1/health?probe=readiness` still returns `200` with
    `"status": "degraded"` — see [API Endpoints Overview](overview.md#get-apiv1health).
