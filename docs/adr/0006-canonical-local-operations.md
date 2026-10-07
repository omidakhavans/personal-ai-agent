# ADR 0006: Use Make As The Canonical Local Operations Interface

## Status

Accepted.

## Context

The local runtime now has multiple real processes: PostgreSQL, FastAPI, the
React control plane, and the learning site. Asking each developer to remember
Compose filenames, environment variables, port mappings, migration ordering,
and health endpoints would make the topology harder to learn and easier to run
inconsistently.

## Decision

Use a small root `Makefile` as the canonical interface for local lifecycle,
database, and quality commands. Docker Compose remains the process supervisor;
Make does not replace it. The Make targets check for a local `.env`, invoke the
same `compose.yml`, wait for readiness, and keep destructive reset behind an
explicit confirmation value.

## Consequences

- Documentation and future automation have one stable command vocabulary.
- PostgreSQL and artifacts survive normal `local-down` operations in named
  volumes.
- A developer can still use Docker Compose directly for diagnosis, but that is
  not the supported onboarding path.
- This does not introduce a production deployment abstraction. The package is
  explicitly for local development.
