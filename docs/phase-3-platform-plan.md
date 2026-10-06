# Phase 3 Platform Plan

## Scope

Phase 3 evolves the completed Phase 2 local runtime into a small,
production-style agent platform. Milestones 3.1 and 3.2 are complete, and the
foundations of 3.3 and 3.4 are implemented: SQLAlchemy mappings, Alembic
migrations, a PostgreSQL-targeted run repository, immutable execution events,
and storage-neutral run queries. The remaining milestones are a plan. It does
not include an API, worker, or publisher yet.

The Phase 3 backend target is Python 3.12+ with FastAPI, Pydantic v2,
SQLAlchemy 2, and Alembic introduced at the boundaries that need them.

The desired platform capabilities are:

- PostgreSQL-backed state and queryable run history;
- durable stage, event, artifact, and approval records;
- configurable model, prompt, and tool selection;
- an API and separate operator control plane;
- carefully controlled WordPress, LinkedIn, and X publishing integrations;
- encrypted integration credentials;
- background work for long-running and external actions; and
- observability with traces, logs, and metrics.

The non-negotiable constraint is draft-first operation: generation, review,
approval, and external publication remain distinct decisions.

## Evidence-Led Current-State Assessment

### What Phase 1 Established

Phase 1 used Codex Skills to define the content workflow. Its most important
contribution was separation of responsibilities: research found evidence,
context building selected it, writing created drafts, review checked them, a
human approved downstream transformations, and social skills adapted an
approved canonical article.

Those skills are the behavioral reference. They are external Codex Skill
definitions, not application source maintained in this repository. Phase 3
should preserve their intent through tests and explicit workflow contracts
rather than attempting to copy a conversational runtime into the application.

### What Phase 2 Implemented

Phase 2 is a compact Python 3.11+ package with no runtime dependencies. Its
entry point is the CLI in `personal_ai_agent/cli.py`. `Orchestrator` in
`personal_ai_agent/runtime.py` advances the fixed workflow from
`personal_ai_agent/stages.py`.

`personal_ai_agent/state.py` persists an isolated run under `runs/<run-id>/`:

- `state.json` is the shareable checkpoint for workflow status and stage
  outcomes;
- Markdown artifacts carry the stage hand-off contracts and human-readable
  evidence trail;
- ignored owner-only local configuration stores machine-specific resume inputs;
  and
- a file lock and atomic writes protect one local run.

The model boundary is already disciplined. `ModelClient` is a protocol, while
`OpenAIResponsesClient` is one infrastructure implementation. Research
collectors bound repository and supplied-resource input before it reaches a
model. Writers and reviewers consume prior artifacts, validate structured
outputs, and preserve evidence identifiers. Social writers require a
fingerprint-matched review and approval artifact.

### What Must Not Be Lost

Phase 3 must retain these tested guarantees:

1. A stage cannot be recorded as successful without its expected non-empty
   artifact.
2. A resumed run does not silently repeat completed stages.
3. Missing or tampered prior artifacts stop a resume.
4. `blocked` means unsafe or insufficient inputs, while `failed` means an
   execution problem.
5. A review that needs revision cannot produce social content.
6. An owner approval is explicit and tied to the reviewed article identity.
7. Run state and shareable artifacts do not store machine paths or API keys.
8. Publication is never an incidental side effect of drafting.

## Target Boundaries

Phase 3 should become a modular monolith. A module boundary is an ownership and
dependency rule, not an excuse to move every file at once.

```text
interfaces
  CLI | FastAPI routes | admin UI adapters | worker entry points
      -> application
          run use cases | approval | publication commands | queries
              -> domain
                  workflow policy | run/step records | contracts | ports
              -> infrastructure
                  PostgreSQL | Alembic | filesystem | OpenAI | HTTP publishers
```

### Domain

Own concepts that are meaningful even without a web framework or database:

- run lifecycle and legal state transitions;
- stage and attempt outcomes;
- artifact identity and traceability requirements;
- review and approval policy;
- publication status and idempotency policy; and
- ports such as run repository, artifact store, model provider, publisher, and
  event recorder.

The Phase 2 `Stage`, `StageResult`, status values, artifact checks, and approval
fingerprint rules are the natural starting material. They need typed records and
clear ownership, not an immediate rewrite of each capability.

### Application

Own use cases that coordinate domain rules and ports:

- start, resume, inspect, validate, approve, and cancel a run;
- execute one eligible stage;
- request or inspect a publication;
- choose an approved model/prompt/tool configuration; and
- expose safe query views for the CLI and API.

The current `Orchestrator` is mostly application logic. It is currently coupled
to dictionary-shaped state and filesystem helpers, so this is the first place
to introduce ports carefully.

### Infrastructure

Own external details and adapters:

- existing JSON state and local artifacts;
- PostgreSQL/SQLAlchemy/Alembic;
- the OpenAI Responses API and future providers;
- local Git and supplied-resource collection;
- WordPress and social APIs;
- encrypted credential storage;
- Redis/Dramatiq; and
- OpenTelemetry exporters and logging configuration.

`OpenAIResponsesClient`, `resource_fetch.py`, filesystem state helpers, and
the direct CLI composition root are existing infrastructure-shaped code. They
should be moved only as their consuming port becomes real.

### Interfaces

Own input/output translation, not workflow policy:

- the existing CLI;
- future FastAPI request and response models;
- a separate operator UI;
- worker task entry points; and
- later MCP or API clients if there is an actual consumer.

The current static Fumadocs/Next site is learning documentation. It is not a
candidate location for run administration, credentials, or publishing actions.

## Data Ownership And Storage Plan

The file system currently holds several different kinds of information. Phase 3
must not move all of it into one unstructured JSON column.

| Category | Examples | Phase 3 storage direction | Why |
| --- | --- | --- | --- |
| Domain data | agents, workflows, stage definitions, publication policy | relational tables once user-editable | relationships and versioning matter |
| Execution state | run status, current stage, step attempts, checkpoints | relational rows plus bounded JSONB checkpoints | queryable lifecycle with flexible stage payloads |
| Artifacts | Markdown draft, report, approval artifact, checksums | metadata in PostgreSQL; bytes in a controlled artifact store | large content and metadata have different lifecycles |
| Configuration | model choice, prompt version, tool settings | relational versions; JSONB only for variable provider options | reproducibility and review |
| Integration secrets | provider tokens, publishing credentials | encrypted credential store with key references | secrets must not appear in ordinary run records |
| Run history/audit | transition, approval, publish request, operator action | append-only event records | explain what changed and who initiated it |
| Logs/telemetry | request timings, errors, trace IDs, token usage | structured logs, metrics, OpenTelemetry backend | diagnostics, not business truth |
| Transient runtime data | in-flight job payload, lock, retry lease | worker/queue storage or short-lived process memory | should not become permanent workflow state |

### Minimal First PostgreSQL Model

The first database milestone should not attempt every future entity. Start with:

- `runs` for identity, subject, status, workflow version, timestamps, and
  selected configuration references;
- `run_steps` for stage status, attempt number, timestamps, outcome summary,
  and artifact reference;
- `run_checkpoints` for bounded, versioned JSON needed to resume safely;
- `artifacts` for name, media type, checksum, size, storage key, and provenance;
- `run_events` for append-only lifecycle and operator events; and
- `approvals` for the human decision, reviewed-artifact fingerprint, note, and
  timestamp.

Keep artifact content in the existing local filesystem adapter at first, with
metadata in the database only when the PostgreSQL adapter is introduced. Object
storage can be considered later when deployment requirements prove it is
needed. Avoid adding an object-store dependency merely to make the diagram look
more distributed.

`agents`, `workflows`, `prompts`, `models`, `tool_configs`, integration
accounts, encrypted credentials, publications, and publication attempts belong
to later milestones when the system actually exposes those configuration or
publishing capabilities.

Do **not** add pgvector in the persistence milestone. The current workflow has
no retrieval feature, corpus, or semantic-search query. Introduce it only with
a specific knowledge/retrieval use case and evaluation plan.

## Incremental Migration Path

1. Characterize current behavior with tests before moving code.
2. Add framework-independent typed domain records and ports.
3. Wrap the current JSON/filesystem behavior in a `FileRunRepository` and
   `FileArtifactStore`; keep existing run folders valid.
4. Make `Orchestrator` depend on ports, retaining its current deterministic
   stage order and validation rules.
5. Add PostgreSQL and Alembic as a second adapter, with a small migration and a
   deliberate import/compatibility command for existing local runs.
6. Add application use cases, then expose them through FastAPI while preserving
   the CLI as another interface.
7. Add the operator UI against stable API contracts.
8. Add credentials and publisher ports before individual publishing adapters.
9. Add workers only when run duration or external publishing makes synchronous
   execution unsuitable.
10. Instrument the stable boundaries and harden operations.

This order avoids a risky all-at-once migration. It also keeps a runnable local
learning system while a platform capability is being added.

## Milestone Delivery Detail

### 3.2 Typed Runtime And Persistence Boundary

Status: Complete.

**Objective:** decouple workflow logic from JSON files without changing user
visible behavior.

**Reuse:** `Orchestrator`, stage status vocabulary, artifact validation,
`ModelClient`, private-config handling, locks, and behavioral tests.

**Refactor:** dictionary-shaped state access in `runtime.py` and direct calls to
state-file helpers. Keep parser contracts and Markdown artifacts unchanged.

**New components:** typed run/step/event records; `RunRepository` and
`ArtifactStore` ports; file-backed adapters; an explicit composition root.

**Database/migration:** none. This milestone prepares the seam.

**Dependencies:** set Python 3.12+ as the Phase 3 baseline and update CI in a
small, explicit compatibility pull request; do not add FastAPI or database
dependencies to this boundary-only milestone.

**Risks:** an accidental behavior change in resume, status, artifact, or local
private-input handling.

**Tests:** characterization tests for all terminal outcomes, resume after an
interrupted stage, tampered artifacts, approval fingerprints, and file-adapter
round trips.

**Done means:** complete. The CLI's existing commands retain their state and
artifact behavior, and `Orchestrator` checkpoints through a `RunRepository`
instead of knowing a `state.json` path.

**Delivered:** typed run/stage/artifact records, a future event contract,
repository and artifact-store ports, filesystem adapters, Python 3.12+ CI, and
42 behavioral/contract tests.

**Learning objective:** hexagonal architecture is a way to protect business
rules from external details, not a rule that every class needs an interface.

### 3.3 PostgreSQL Persistence Foundation

**Objective:** add durable, queryable run records without changing stage logic.

**Reuse:** domain records and ports from 3.2.

**New components:** SQLAlchemy 2 mappings, Alembic environment and first
migration, PostgreSQL repository, database settings, and a local integration
test fixture.

**Database/migration:** create the minimal tables described above. Make all
migrations forward-only and reversible by an explicit down migration only when
safe; do not silently rewrite historical run payloads.

**Dependencies:** PostgreSQL driver, SQLAlchemy 2, Alembic, and Pydantic v2
only where settings or external data validation needs it.

**Risks:** mixing ORM entities into domain logic, storing secrets in checkpoints,
or importing incomplete file runs as completed.

**Tests:** migration upgrade test, repository contract suite run against file
and PostgreSQL adapters, transaction rollback, and a migration/import scenario
for a completed and an approval-paused run.

**Done means:** a run can be created, inspected, resumed, and audited through
the PostgreSQL adapter with equivalent gate behavior.

**Learning objective:** a database is a consistency and query boundary, not
automatically the right place for every blob or transient value.

### 3.4 Execution History And Recovery

**Status:** Complete.

**Objective:** turn current lifecycle changes into a queryable audit trail.

**Reuse:** run/step states and `validate_run` invariants.

**Delivered components:** an append-only `run_events` table, a small
transition-derived event vocabulary, a per-run unique sequence, event payload
schema versioning, and `RunQueryService` read DTOs for list and detail queries.

**Database/migration:** migration `20261006_0002` adds event rows with a
per-run sequence constraint and indexes. The existing `run_stages.attempts`
counter remains the meaningful stage-attempt record; a separate whole-run
attempt identity is deferred until a worker retry has defined semantics.

**Risks:** confusing logs with audit events or claiming exactly-once execution
when external model calls cannot guarantee it.

**Tests:** adapter contract test, normal orchestrator event timeline, event
ordering, status/date filtering, keyset pagination, run detail projection, and
redaction of query-visible failure messages.

**Done means:** an operator-facing adapter can list runs and inspect safe
checkpoint/event history without reading run directories or server logs.

**Learning objective:** agent systems need durable decision history because
model and tool calls are expensive, non-deterministic, and often external.
Snapshots support recovery; events explain transitions; technical logs remain
diagnostic data rather than business truth.

### 3.5 API And Typed Contracts

**Objective:** expose stable application use cases over HTTP.

**Reuse:** application services and ports; retain the CLI as a thin client.

**New components:** FastAPI routes, Pydantic v2 request/response schemas,
authentication design appropriate to the deployment, and API error mapping.

**Database/migration:** no mandatory schema change beyond actor/audit fields if
the chosen authentication model requires them.

**Risks:** leaking artifact content, private references, or credentials through
API responses; making routes own orchestration policy.

**Tests:** API contract tests, authorization tests, pagination/filter tests,
and snapshot-safe serialization tests.

**Done means:** an API can start, inspect, validate, approve, and resume a run
with the same guard behavior as the CLI.

**Learning objective:** an API boundary validates untrusted input and makes a
system usable by multiple interfaces; it is not the business layer itself.

### 3.6 Operator Control Plane

**Objective:** make run state and approval understandable without shell access.

**Reuse:** stable API contracts and audit/event views.

**New components:** a separate Vite React TypeScript app, shadcn/ui components,
TanStack Query/Table, run list, run detail, artifact viewer, approval action,
and configuration read views.

**Database/migration:** none required beyond API needs.

**Risks:** treating the documentation site as an authenticated dashboard,
missing authorization/CSRF protections, or hiding blocked/uncertain outcomes.

**Tests:** UI component tests, API integration tests, and manual workflow checks
for a blocked, approval-paused, and completed run.

**Done means:** an operator can trace a run, inspect evidence-facing artifacts,
and make an explicit approval without direct filesystem access.

**Learning objective:** a control plane is an interface for operating a system;
it is different from both the runtime and the public learning documentation.

### 3.7 Model, Prompt, Tool, And Credential Configuration

**Objective:** make approved runtime configuration explicit and reproducible.

**Reuse:** `ModelClient` as the initial provider port and stage-specific
instructions/schema functions as prompt inputs.

**Refactor:** direct OpenAI client construction in `cli.py`; model choice stored
as an unconstrained string; prompt text embedded only in Python functions.

**New components:** provider registry, model selection policy, prompt versions,
tool configuration records, integration account metadata, credential envelope
encryption, key-management interface, and redacted settings views.

**Database/migration:** model/prompt/tool configuration tables and encrypted
credential records. Store ciphertext, key reference, version, and rotation
metadata, never plaintext secrets in run state or ordinary application logs.

**Risks:** secret exposure, mutable configuration making runs irreproducible,
or unbounded model routing complexity.

**Tests:** credential encryption/decryption isolation, redaction checks,
configuration-version pinning in a run, provider contract tests, and invalid
configuration rejection.

**Done means:** a run records immutable configuration references and can be
explained/reproduced without revealing credentials.

**Learning objective:** agent behavior is the combination of model, prompt,
tools, and state. Versioning those inputs matters as much as versioning code.

### 3.8 Publishing Foundation And WordPress

**Objective:** add the first controlled external publishing adapter.

**Reuse:** approved article inputs, review fingerprint, approval record, and
artifact provenance.

**New components:** content/publication lifecycle, publisher port, WordPress
adapter, publish-request use case, idempotency key policy, and operator
confirmation screen.

**Database/migration:** publications and publication-attempt records linked to
the approved artifact/configuration/credential versions.

**Risks:** duplicate external posts, publishing a changed article after review,
credential leakage, and API failures leaving ambiguous external state.

**Tests:** fake publisher contract tests, repeated-request idempotency,
fingerprint mismatch rejection, and WordPress sandbox/integration tests.

**Done means:** an approved article can be deliberately sent as a WordPress
draft or preview, with a durable attempt record and no auto-publish path.

**Learning objective:** a tool that changes the outside world needs stronger
identity, approval, retry, and audit controls than a tool that only reads.

### 3.9 Social Publishing Integrations

**Objective:** support LinkedIn and X only after the common publishing controls
are demonstrated with WordPress.

**Reuse:** social draft artifacts and publisher port.

**New components:** platform adapters, OAuth/account connection flow, platform
validation, and per-platform publish confirmation.

**Database/migration:** account connection and platform publication metadata.

**Risks:** platform policy changes, rate limits, OAuth renewal, duplicate posts,
and mismatched draft/article identities.

**Tests:** provider contract suites, token-expiry handling, idempotency, and
approval/artifact identity checks.

**Done means:** no social action can occur without a matching approved draft and
an explicit operator request.

**Learning objective:** adapters make policy differences visible rather than
hiding every external platform behind one vague `publish()` call.

### 3.10 Background Jobs And Idempotent Execution

**Objective:** run long work safely outside API requests without duplicating
model calls or irreversible external actions.

**New components:** Redis/Dramatiq job adapters, leases, job identity,
idempotency handling, retry policy, and worker entry points that call the same
application use cases as the CLI and API.

**Database/migration:** job/publication attempt linkage and any required lease
or outbox records. Do not use a queue as the permanent run-history database.

**Risks:** duplicate execution, orphaned jobs, and paid model calls retried
without intent.

**Tests:** retry policy, stale-worker recovery, idempotent publish request, and
job-to-run event correlation.

**Done means:** API and worker execution share the same application use cases,
and each job can be connected to a durable run and external-action attempt.

**Learning objective:** asynchronous execution changes failure semantics. It is
not merely a performance optimization.

### 3.11 Observability

**Objective:** make runs, jobs, model calls, tools, and publisher attempts
diagnosable without treating telemetry as business truth.

**New components:** structured logging, OpenTelemetry spans, metrics,
correlation identifiers, redaction policy, and dashboard/exporter configuration.

**Database/migration:** no primary business schema change is required. Link
trace and job identifiers to durable run events where useful.

**Risks:** collecting prompts, source text, or credentials in telemetry; using
logs as a substitute for the run event/audit record.

**Tests:** trace-context propagation, redacted logging, metric labels, and a
run-to-trace correlation scenario.

**Done means:** an operator can follow a run through its API request, job,
model/tool/publisher calls, and diagnostic traces without exposing sensitive
content by default.

**Learning objective:** observability explains system behavior; it does not
decide whether a workflow transition or approval is valid.

### 3.12 Configuration Governance And Production Hardening

**Objective:** make the platform safe to operate over time.

**New components:** permissions, rate limits, backup/recovery procedure,
configuration governance, deployment checks, retention policy, and incident
runbooks.

**Risks:** building broad multi-tenancy or retrieval infrastructure before there
is a real product requirement.

**Tests:** authorization matrix, backup restore rehearsal, dependency/security
checks, configuration rollback, and deployment smoke tests.

**Done means:** the platform can be deployed and operated with documented
limits, recovery paths, and explicit human controls.

**Learning objective:** production readiness is operational behavior, not just
the presence of a database and dashboard.

## Recommended ADRs

The following proposed decisions are significant enough to record now:

1. [ADR 0001: Modular-monolith boundaries](adr/0001-modular-monolith-boundaries.md)
2. [ADR 0002: Relational state with file-adapter migration](adr/0002-relational-state-and-file-migration.md)
3. [ADR 0003: Human-approved publication and credential boundaries](adr/0003-human-approved-publishing-and-credentials.md)

## Explicitly Deferred

- LangChain, LangGraph, generic agent frameworks, and a bespoke planner;
- vector databases and pgvector without a real retrieval feature;
- microservices and event-bus architecture;
- automatic web discovery from the runtime;
- automatic publication or scheduling; and
- multiple provider routing/optimization before configuration provenance exists.

The system has useful current behavior. Phase 3 should make it more durable and
operable, not replace its evidence and approval discipline with infrastructure.
