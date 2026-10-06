# ADR 0001: Use A Modular Monolith With Explicit Ports

Status: Proposed for Phase 3.

## Context

Phase 2 is a small local Python runtime. Its `Orchestrator` coordinates a
fixed workflow, state helpers persist JSON files, and the CLI directly builds
the OpenAI-backed executors. That is an appropriate learning implementation,
but it would make an API, PostgreSQL, worker, and external publisher tightly
coupled if expanded without boundaries.

## Decision

Phase 3 will remain one deployable application while using four dependency
directions:

```text
interfaces -> application -> domain <- infrastructure
```

The domain defines workflow policies, records, and ports. Application use cases
coordinate them. Infrastructure implements ports. CLI, HTTP, worker, and UI
adapters translate outside input and output.

An abstraction is introduced only where the application genuinely needs more
than one implementation or needs to protect policy from an external detail.

## Consequences

- PostgreSQL, filesystem, model provider, and publishing adapters can change
  without moving workflow policy into those libraries.
- The existing file-backed behavior becomes a compatibility adapter first.
- The project avoids a premature microservice split and retains a simple local
  development story.
- Some short-term code is more explicit, especially composition and contract
  tests. That cost is justified by the planned adapter changes.
