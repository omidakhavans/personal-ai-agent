# ADR 0002: Use PostgreSQL For Durable Workflow State After A File-Adapter Seam

Status: Proposed for Phase 3.

## Context

Phase 2 stores each run in a directory with a JSON checkpoint and Markdown
artifacts. This makes local execution easy to understand and resume, but it
does not provide queries across runs, a durable event history, multi-process
leases, or a safe API/control-plane foundation.

## Decision

Introduce typed run and artifact ports first. Keep the filesystem implementation
as a `FileRunRepository`/artifact adapter while the orchestrator becomes port
based. Then add a PostgreSQL implementation using SQLAlchemy 2 and Alembic.

Persist lifecycle fields, attempts, approvals, artifacts metadata, and events
relationally. Store bounded, versioned variable checkpoints in JSONB. Keep
artifact bytes in a controlled artifact store instead of turning arbitrary
Markdown content into unstructured execution state.

Do not add pgvector until a concrete retrieval feature requires it.

## Consequences

- Existing local runs remain understandable and can be migrated deliberately.
- PostgreSQL becomes the source for operational queries and audit history.
- A small import/compatibility path is needed; incomplete file runs must never
  be imported as completed merely to simplify migration.
- The project gains migration testing and operational database responsibility.
