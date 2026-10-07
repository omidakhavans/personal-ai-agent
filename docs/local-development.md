# Local Runtime Package

## Purpose

The local package runs the parts of the agent that exist today as one
development topology:

```text
browser -> React control plane -> FastAPI -> PostgreSQL
                                  |
                                  -> durable artifact volume

browser -> learning/documentation site
```

The React control plane is intentionally read-only. It displays run history,
stages, timeline events, and fixed workflow metadata through the versioned API.
It does not start runs, edit credentials, inspect artifact bytes, or publish
content. Those are future capabilities that need explicit backend policy and
audit records first.

## Start The Stack

Prerequisites are Docker Desktop (with its engine running), Docker Compose v2,
and GNU Make or the platform's compatible `make` command.

```bash
cp .env.example .env
make local-up
```

Open these local addresses after readiness succeeds:

- React control plane: `http://localhost:5173`
- FastAPI OpenAPI UI: `http://localhost:8000/docs`
- Learning site: `http://localhost:3000`

Use `make local-status` for a compact service and endpoint report, `make
local-logs` to follow logs, and `make local-down` to stop the stack. Stopping
the stack preserves the named PostgreSQL and artifact volumes.

`make local-reset CONFIRM=reset` is intentionally destructive: it removes both
volumes and creates an empty local stack. It is for disposable development data
only.

## Database And Quality Commands

```bash
make db-shell
make db-migrate
make db-current
make db-history
make lint
make typecheck
make test
make admin-check
make docs-check
make check
```

The quality commands execute inside the relevant Compose images, so the
container toolchain is the one being checked. Run `make local-up` first so the
images have been built.

## Configuration And Migration Rules

`.env` is local-only and ignored by Git. `.env.example` contains only safe
placeholder values. Set a unique local database password in `.env`; do not put
provider credentials there because this package has no provider runtime yet.

The API container runs `alembic upgrade head` before Uvicorn starts. This is
safe for the existing forward-only local migrations and guarantees that its
readiness endpoint cannot become healthy against an older schema. `make
db-migrate` remains available when you want to run the same migration explicitly.

The database stores durable run snapshots and event history. The artifact
volume stores generated Markdown artifacts. Neither volume is copied into the
repository or the documentation site.

## Health Semantics

- PostgreSQL health uses `pg_isready`.
- API liveness is `GET /api/v1/health`; readiness is `GET /api/v1/ready` and
  verifies that the run-history database can answer a read-only query.
- The admin and learning site health checks request their local HTTP root.
- `make local-check` waits for all three browser-visible endpoints.

## Future Model Providers

No model service runs in Compose today. When a later provider adapter needs a
local Ollama instance, prefer running it as an explicitly documented external
service and configure its base URL through a bounded provider configuration
boundary. A Linux Docker container cannot use host `localhost` for that; it
normally needs a host-reachable address such as `host.docker.internal` when the
environment supports it. Do not add the setting, credential plumbing, or a
placeholder service until the provider milestone begins.

## Security Boundary

This is a localhost development topology, not a multi-user deployment. There
is no authentication yet, so do not expose these ports to a network. CORS is
limited to the configured local admin origin and rejects wildcard origins. API
responses are purposely safe read models; they do not expose private resume
configuration, database connection values, artifact contents, or secrets.
