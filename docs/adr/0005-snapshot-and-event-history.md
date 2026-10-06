# ADR 0005: Keep Snapshots And Event History Distinct

## Status

Accepted.

## Context

The orchestrator needs one current workflow checkpoint to resume safely. The
future API and control plane also need an ordered explanation of run and stage
transitions. Treating either requirement as the other would be misleading:
logs are not a business audit trail, and reconstructing every state detail from
events would introduce event sourcing that the current runtime does not need.

## Decision

Keep `RunSnapshot` as the current durable state used for resume. The PostgreSQL
adapter derives a small append-only event vocabulary from snapshot transitions
and writes those events in the same transaction as the new snapshot. Every
event has a sequence unique within a run and a schema-versioned, redacted
metadata payload.

Continue using the existing per-stage `attempts` count. Do not add a separate
run-attempt model until a worker retry or restart has a distinct lifecycle that
the runtime can enforce.

## Consequences

- The control plane can render a deterministic timeline without reading logs.
- Resume behavior remains simple and based on the latest checkpoint.
- Events contain stable metadata, never raw prompts, model responses,
  credentials, headers, private resume configuration, or artifact bytes.
- A later worker system can add a real run-attempt entity without destructive
  reinterpretation of today’s stage-attempt counter.
