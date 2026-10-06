# Phase 3 Platform Planning

Phase 2 gave the project a working local runtime. Phase 3 should not throw it
away because it uses files. Instead, it should make the workflow's important
rules durable, queryable, and operable while preserving the behavior that makes
the current content pipeline trustworthy.

Read [the detailed Phase 3 Platform Plan](../phase-3-platform-plan.md) beside
this guide. This page explains the learning ideas behind the plan.

## The Key Architectural Move

Today the runtime is compact:

```text
CLI -> Orchestrator -> state.json -> stage executor -> Markdown artifacts
```

That is enough for one local operator. It becomes limiting when you need run
history, an API, a dashboard, credentials, jobs, or publishing integrations.

The tempting response is to add a database directly inside the current
orchestrator. That would make the workflow rules depend on SQLAlchemy and make
later interfaces repeat the same logic. Instead, Phase 3 begins by extracting
the concepts that already exist:

```text
workflow rules -> repository and artifact ports -> file or PostgreSQL adapters
```

This is ordinary software architecture, but it has special value for agents.
Agent runs combine model calls, tools, intermediate evidence, and human pauses.
Those steps can be expensive, slow, and non-deterministic, so the policy that
protects them must not be accidentally rewritten by every new interface.

## What Stays The Same

The first Phase 3 task must keep the following Phase 2 behavior intact:

- completed work is not silently rerun on resume;
- artifacts are checked before later stages trust them;
- `blocked` is different from `failed`;
- social transformations still need a passing review and explicit approval;
- generated content remains draft-only; and
- model keys and local machine paths stay out of shareable run state.

These are not cosmetic details. Together, they make the system inspectable and
safe to interrupt.

## Why PostgreSQL Comes After The Boundary

A database is useful when the platform needs durable queries and coordination:

- list runs across time;
- show every stage attempt and approval;
- serve an API and a dashboard;
- coordinate workers safely; and
- record publication attempts and external identifiers.

It is not automatically better storage for every value. The plan separates:

| Kind of information | Best initial home |
| --- | --- |
| run status and approvals | relational records |
| variable, versioned resume payload | bounded JSONB checkpoint |
| Markdown artifact bytes | artifact store |
| publish/model credentials | encrypted credential storage |
| timings and traces | logs, metrics, OpenTelemetry |

The first task leaves files in place as an adapter. That lets tests prove the
new interface matches current behavior before PostgreSQL is asked to replace it.

Phase 3 also raises the backend baseline to Python 3.12+ through an explicit
compatibility and CI change. FastAPI, Pydantic v2, SQLAlchemy 2, and Alembic
arrive later when the API and PostgreSQL adapters need them.

## Agent-System Concepts

### Business Audit Versus Telemetry

A run event such as "owner approved article fingerprint X" is business history.
It must be durable and understandable even if a log service is unavailable.
A trace span such as "model call took 2.4 seconds" is telemetry. It helps
diagnose performance and failures but is not proof that approval occurred.

### Idempotency

Model calls and publisher calls can have side effects or cost money. A retry
must have an identity and a recorded outcome. Otherwise, a worker can create a
second external post because it cannot tell whether the first request finished.
That is why jobs and publishing are later milestones, after run history and
approval artifacts exist.

### Configuration Provenance

An agent's behavior depends on more than code. Model selection, prompt version,
tool settings, and input artifacts influence the result. Phase 3 will record
approved configuration versions without exposing credentials. That makes a run
explainable: "which model and instruction set produced this draft?"

### Human Control At The Action Boundary

Generating a draft is reversible. Publishing is not. The workflow therefore
keeps review, approval, and publication as separate actions. A publisher is not
allowed to infer permission merely because an article exists.

## What Was Implemented In Phase 3.2

The first implementation task is complete. The new `domain.py` contains typed
run, stage, and artifact snapshots. `persistence.py` defines the repository and
artifact-store ports plus filesystem adapters that continue to use the proven
JSON state, lock, private-config, and Markdown artifact behavior.

`Orchestrator` now depends on those ports. It still returns the same shareable
state dictionary to the CLI, and stage executors still receive their workspace
directory, so this was a boundary refactor rather than a workflow rewrite.

The next milestone is PostgreSQL persistence. It must implement the same
repository contract before the CLI, API, or UI is changed.

## First Exercise In Phase 3

The first implementation task was **Typed Runtime And Persistence Boundary**.
Its goal was not to add a database. Its goal was to make it possible to swap
the file implementation for a database without changing workflow rules.

Before implementing it, answer these questions from the current code:

1. Which filesystem functions now live behind `FileRunRepository`?
2. Which fields in `state.json` represent workflow policy rather than storage?
3. Which artifacts must survive a resume, and why?
4. Which existing tests describe behavior that a file and PostgreSQL adapter
   must both pass?
5. Which input is deliberately outside shareable state, and why?

The detailed plan and proposed decisions are the handoff for the next session:

- [Phase 3 Platform Plan](../phase-3-platform-plan.md)
- [Roadmap](../roadmap.md)
- [Architecture Decision Records](../adr/README.md)
