# API Guide

## Scope

The Phase 3.5 API is a thin, read-only FastAPI transport adapter. It exposes
the durable run-history query layer and fixed workflow metadata for the future
control plane. It does not start workflows, invoke model providers, read
artifacts, edit configuration, publish content, cancel work, or retry work.

## Local Development

Apply the Alembic migrations to a PostgreSQL database, then set a database URL
in the environment and start the API:

```bash
export PERSONAL_AI_AGENT_DATABASE_URL="postgresql+psycopg://<user>:<password>@<host>/<database>"
uvicorn personal_ai_agent.api.app:app --reload
```

The OpenAPI document is available at `/openapi.json`; interactive development
documentation is available at `/docs`.

## Routes

| Route | Purpose |
| --- | --- |
| `GET /api/v1/health` | Process liveness; it does not check the database or an LLM provider. |
| `GET /api/v1/ready` | Database connectivity required for normal history reads. |
| `GET /api/v1/runs` | Newest-first run history with `status`, creation date, `limit`, and keyset `cursor` filters. |
| `GET /api/v1/runs/{run_id}` | One safe run detail, including stages and its current complete event timeline. |
| `GET /api/v1/workflows` | The current fixed content workflow and stages. |

There is no separate events route: events are already bounded by the current
run-detail payload and do not yet support independent timeline pagination.

## Error Model

The API returns small stable errors such as `run_not_found`, `invalid_cursor`,
and `dependency_unavailable`. Unexpected errors are logged server-side and
become a generic `internal_error`; stack traces and connection details are not
sent to callers.

## Security Boundary

This API is **not safe to expose publicly without authentication and a deployed
reverse-proxy policy**. Its initial intended use is local development. CORS
defaults to the explicit local React origin `http://localhost:5173`, does not
allow credentials, and can be adjusted with `PERSONAL_AI_AGENT_CORS_ORIGINS`.

Responses are built from application query DTOs. They do not expose secrets,
tokens, provider credentials, local filesystem paths, private resume inputs,
artifact contents, ORM identifiers, or raw exception details.
