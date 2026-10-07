# Personal AI Agent Roadmap

## Purpose And Current Position

This project is a learning-oriented, draft-first content agent. It turns a
subject and explicitly supplied evidence into reviewable technical-content
artifacts. It does not publish anything automatically.

- **Phase 1 — Codex Skills:** complete. Codex was the runtime; the skills
  defined the behavior for research, context building, writing, review, human
  approval, and social transformation.
- **Phase 2 — local Python runtime:** complete. The repository contains a
  file-backed, resumable implementation of that workflow, with a command-line
  interface, bounded model calls, artifacts, validation, review, and explicit
  approval.
- **Phase 3 — production-style agent platform:** in progress. It evolves the
  working runtime into a small, observable, API-driven modular monolith without
  discarding the Phase 2 workflow guarantees.

Phase 1's skill specifications are a behavioral reference, not source code in
this repository. Phase 2 is the implementation baseline for Phase 3.

## Phase 1: Codex Skills

Status: Complete.

The behavioral workflow was:

```text
subject
  -> research-work
  -> research-resources
  -> build-evidence-context
  -> write-blog
  -> review-blog
  -> human approval
  -> write-linkedin
  -> write-x
```

Phase 1 taught the capability boundaries. It kept repository research,
resource research, context selection, writing, evaluation, approval, and
platform transformation separate. Codex supplied orchestration, tools, and
conversation state.

## Phase 2: Local Runtime

Status: Complete.

Phase 2 made the runtime explicit:

```text
CLI -> Orchestrator -> JSON run state -> stage executors -> Markdown artifacts
```

The current implementation includes:

- sequential deterministic orchestration with `pending`, `running`,
  `completed`, `skipped`, `blocked`, `failed`, and `awaiting_approval` states;
- atomic file checkpoints, per-run locks, artifact validation, and resumability;
- bounded local and remote research inputs with evidence identifiers;
- grounded blog generation and evidence-aware review;
- an explicit human approval checkpoint before social drafts;
- draft-only LinkedIn and X transformations; and
- linting, type checking, behavioral tests, and documentation-site checks.

The existing `edit-blog` skill remains a useful content-workflow idea, but it
is not the next platform task. Phase 3 first needs durable boundaries around
the runtime that already works.

Read [Phase 3 Platform Plan](phase-3-platform-plan.md) for the evidence-led
transition plan and [Architecture Notes](architecture.md) for the current
implementation.

## Phase 3: Production-Style Agent Platform

Status: In progress. Milestones 3.1 through 3.5 and Phase 4.1/4.2 local
control-plane packaging are complete.

### Goal

Evolve the local runtime into a small, production-style platform that can keep
durable run history, expose an API and an operator UI, manage model and
integration configuration safely, run longer work in background jobs, and keep
human approval in control of publishing.

Phase 3's backend baseline will be Python 3.12+; FastAPI, Pydantic v2,
SQLAlchemy 2, and Alembic enter only in the milestones where their boundary is
needed.

The target is a **modular monolith**, not a collection of services:

```text
interfaces (CLI, API, admin UI, worker entry points)
  -> application (use cases and orchestration)
  -> domain (workflow rules and contracts)
  -> infrastructure (PostgreSQL, filesystem, providers, integrations)
```

The core must remain independent of FastAPI, SQLAlchemy, OpenAI, Redis, and a
specific publishing platform. Those are replaceable adapters at the edge.

### Delivery Principles

1. Preserve Phase 2 behavior first. A completed stage, evidence reference,
   review gate, and owner approval must not become weaker during migration.
2. Introduce a port before replacing an adapter. The file-backed runtime stays
   runnable while a new persistence or provider adapter is proved.
3. Migrate incrementally. Do not combine a package rearrangement, a database,
   an API, and an admin UI in one pull request.
4. Keep the documentation site separate from the future operator control plane.
   The site teaches the system; it does not administer it.
5. Prefer relational data for workflow status, ownership, timestamps, foreign
   keys, approvals, and publication records. Use JSONB only for bounded,
   versioned payloads that are genuinely variable.
6. No automatic publishing. Human review and an explicit approval record remain
   required even after integrations exist.

### Milestones

#### 3.1 Architecture Mapping And Decisions

Status: Complete as documentation. See [Phase 3 Platform Plan](phase-3-platform-plan.md)
and [ADRs](adr/README.md).

This planning milestone maps the Phase 1 behavior to the Phase 2 codebase,
records constraints, defines the target boundaries, and identifies the first
safe implementation task. It deliberately adds no dependencies or runtime
behavior.

#### 3.2 Typed Runtime And Persistence Boundary

Status: Complete.

Introduce explicit domain records and repository ports around the current run
state, then make the existing file-backed implementation an adapter. Preserve
the CLI, filesystem artifacts, and current run behavior while tests prove the
new boundary is behaviorally equivalent.

Implemented:

- framework-independent `RunSnapshot`, `StageSnapshot`, and artifact contracts;
- repository and artifact-store ports;
- file-backed adapters that retain atomic JSON checkpoints, locks, private
  resume configuration, and path-constrained Markdown artifacts;
- a port-backed `Orchestrator` with unchanged CLI outputs and workflow rules;
- Python 3.12+ package and CI baseline; and
- characterization tests for snapshot compatibility, file adapter round trips,
  and artifact confinement, alongside the existing lifecycle tests.

Why first: PostgreSQL can now replace an adapter rather than becoming entangled
with orchestration dictionaries and filesystem paths.

#### 3.3 PostgreSQL Persistence Foundation

Status: Foundation complete; history and event work remains in Milestone 3.4.

Add SQLAlchemy 2, Alembic, PostgreSQL configuration, and a PostgreSQL run
repository. The initial adapter persists runs and their latest per-stage
checkpoint behind the existing repository port, while artifact bytes and
owner-only resume configuration remain in their existing stores. Alembic owns
the PostgreSQL schema. Keep the file adapter available until a small, tested
import or compatibility path exists.

#### 3.4 Execution History, Audit Trail, And Recovery

Status: Complete.

The PostgreSQL adapter now appends a small, ordered event vocabulary when a
snapshot transition is checkpointed. It records run creation/start/terminal
status, stage start/terminal status, and approval requests/completion in the
same transaction as the current snapshot. `RunStage.attempts` remains the only
meaningful attempt record today because the runtime has stage retries but no
worker-level whole-run retry identity.

`RunQueryService` DTOs provide newest-first keyset pages, status/date filters,
and safe run details without exposing ORM rows, artifact bytes, private resume
configuration, provider secrets, or technical logs. The filesystem adapter
continues to run the existing CLI workflow unchanged.

#### 3.5 API And Typed Contracts

Status: Complete.

The FastAPI adapter now exposes versioned, read-only endpoints for liveness,
readiness, keyset-paginated run history, run details including their timeline,
and fixed workflow metadata. Pydantic schemas map the application DTOs rather
than ORM rows. The current synchronous CLI command needs local private inputs,
so run creation, cancellation, and retry are deliberately deferred instead of
pretending to offer safe HTTP commands.

#### 3.6 Operator Control Plane

Status: Foundation complete through Phase 4.2.

A separate Vite, React, and TypeScript control plane now reads dashboard
history, run details, stage checkpoints, timeline events, and fixed workflow
metadata from the versioned FastAPI API. It is intentionally read-only: no
authentication, run commands, artifact viewer, approval action, provider
configuration, or publication capability is implied by this first surface.
The static learning site remains separate from the control plane.

#### 3.7 Model, Prompt, Tool, And Credential Configuration

Status: Planned.

Replace direct provider construction in the CLI with application-level model
selection and provider ports. Add model settings, versioned prompts, tool
configuration, integration accounts, and encrypted credential storage. Initial
scope is one configured model per stage or workflow; routing and evaluation
experiments come later.

#### 3.8 Publishing Foundation And WordPress

Status: Planned.

Add content statuses, publication records, a publisher port, and a WordPress
adapter. The first integration should create a controlled draft or preview;
it must not bypass human approval or silently publish.

#### 3.9 LinkedIn And X Integrations

Status: Planned.

Build on the publisher port and credential model after WordPress has proved
the approval, audit, and retry flow. Add platform-specific validation and
explicit operator confirmation before every external action.

#### 3.10 Background Jobs And Idempotent Execution

Status: Planned.

Introduce Redis and Dramatiq only when API-driven or publishing work can no
longer run safely inside a request. Add job identity, retry policy, and
idempotency records before enabling automatic retries of paid model calls or
external publishing operations.

#### 3.11 Observability

Status: Planned.

Add structured logs, metrics, and OpenTelemetry traces across API requests,
jobs, model calls, tool calls, workflow transitions, and publisher attempts.
Run events remain the business audit trail; telemetry is diagnostic data.

#### 3.12 Configuration Governance And Platform Hardening

Status: Planned.

Add safe configuration editing, version visibility, permissions, rate limits,
backup/recovery guidance, deployment checks, and production operations
documentation. Add pgvector only if a concrete retrieval feature needs semantic
search; it is not a default platform dependency.

## Next Phase 3 Implementation Task

**Phase 4.3 — Provider, Model, And Credential Control Plane.**

The local topology and read-only control plane are now stable enough to add the
next missing application boundary: a provider/model configuration port with
credential *references*, never raw values exposed through the API or browser.
This should begin with one configured model per stage or workflow, explicit
validation, audit records, and an authenticated write policy. Do not add a
worker, Redis, or publishing integration in that task; those need a real
asynchronous execution or external-action use case.

## Phase 4: Admin GUI / Agent Control Plane

Status: Phase 4.1 and Phase 4.2 complete; later operator capabilities remain planned.
See [Phase 4 Admin Plan](phase-4-admin-plan.md).

Phase 4 is a separate operator application, not an extension of the static
learning site. The audit found that the current runtime has no HTTP interface,
database query API, configurable providers, credential store, tool registry,
or publishing adapter. Building editable dashboard pages now would therefore
create controls with no safe source of truth.

### Phase 4.1 — React Admin Foundation + Read-Only Control Plane

Status: Complete.

The `admin/` Vite workspace consumes only the FastAPI OpenAPI-facing API. It
contains dashboard, run list, run detail, stage timeline, and workflow pages,
with typed response parsing, loading/error/empty states, and no mutable actions.

### Phase 4.2 — Local Runtime Package + Developer Control Plane

Status: Complete.

`compose.yml`, the root `Makefile`, named PostgreSQL/artifact volumes, health
checks, migration-before-API startup, and local operations documentation run
the actual stack: PostgreSQL, FastAPI, React admin, and learning site. No
placeholder Redis, worker, model service, or publisher was added.

## Future-Session Handoff

Before beginning Phase 3 implementation, read in this order:

1. [Phase 3 Platform Plan](phase-3-platform-plan.md)
2. [Architecture Notes](architecture.md)
3. [ADR index](adr/README.md)
4. [Runtime Walkthrough](learning/runtime-walkthrough.md)
5. `personal_ai_agent/runtime.py`, `state.py`, and `stages.py`
6. `tests/test_runtime.py`

Start with the Milestone 3.3 task above. Preserve behavior first, run the
existing checks, update the architecture and learning guides with each material
change, and do not introduce a Phase 3 service or publishing integration before
the relevant milestone.
