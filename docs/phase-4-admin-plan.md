# Phase 4 Admin GUI / Agent Control Plane Plan

## Decision

Phase 4 will be a separate React and TypeScript operator application. It will
call a FastAPI service; it will never read the database, call a model provider,
or handle provider credentials directly. The existing Next.js/Fumadocs project
remains a public learning site, not an administration surface.

The audit found an important prerequisite: Phase 3.2 introduced only a
filesystem persistence boundary. The repository did not yet have PostgreSQL,
Alembic, HTTP routes, query use cases, configuration records, or credentials.
This means a useful Phase 4.1 cannot safely be an editable dashboard yet. The
PostgreSQL persistence, queryable history, and the read-only versioned API are
complete. Phase 4.1 can now consume stable backend read models without reaching
into infrastructure.

## Capability Map

| Existing capability | Current owner | Needed before GUI | Future operator surface |
| --- | --- | --- | --- |
| Start and resume a run | CLI and `Orchestrator` | Start/resume use cases and API commands | Run launch and resume actions |
| Checkpoint status | file-backed `RunRepository` | queryable repository and read API | Dashboard and run history |
| Stage artifacts | `FileArtifactStore` | artifact metadata/read API with authorization | Artifact viewer |
| Social approval | CLI and approval artifact | approval command and audit event API | Approval action |
| OpenAI structured output | direct client construction | provider port, model configuration, secret reference | Provider/model settings |
| Fixed workflow and prompts | Python constants/functions | versioned workflow/prompt configuration | Workflow and prompt views |
| Local research tools | stage implementation | tool registry and safe configuration schema | Tool configuration |
| Draft-only social content | stage artifacts | publisher port and approval/audit records | Publishing status and controls |

## Current Configuration Assessment

The following values are currently hard-coded or supplied only through the
CLI: stage order, artifact names, prompt instructions, the OpenAI endpoint,
the default model, retries, timeout, output limits, and the direct composition
of model clients and stage executors. The file repository persists a run
snapshot; a private, owner-only resume file holds local repository/resource
inputs. It does not persist API keys.

Safe future UI configuration includes bounded per-run model selection,
timeouts, retry limits, output limits, explicit resource references, and later
versioned prompts or tools. The UI must not edit code-level workflow invariants,
credential values, filesystem paths, or approval/publishing policy without a
dedicated backend policy and audit record.

## Missing APIs And Risks

Before an operator UI can be functional, the platform needs typed APIs for
starting, listing, reading, validating, resuming, and approving runs; artifact
metadata and content reads; and a health/version endpoint. Configuration pages
also need provider, model, prompt, tool, integration, and credential-reference
APIs. They cannot be inferred from Python implementation details.

Other risks are equally material: there is no operator authentication or
authorization, no encrypted credential store, no model usage/cost records, no
append-only audit history, and no remote-safe policy for local resource paths.
The UI must not obscure these gaps with placeholders that imply they work.

## Target Architecture

```text
Vite React operator UI
  -> typed HTTP client
  -> FastAPI routes and Pydantic boundary models
  -> application use cases
  -> domain workflow policy and ports
  -> PostgreSQL / artifact store / provider and publisher adapters
```

The implemented UI uses React, TypeScript, Vite, TanStack Query, Zod, and a
small handwritten typed API client. It intentionally does not add a component
framework or form system before there are editable commands. Response parsing
is a client-side boundary check, not a duplicate of backend business rules.
The local composition includes the database, API, admin, and learning site
because all four exist. The documentation site remains independently deployable
as static content.

## Milestones And Pull Requests

1. **3.3 Persistence foundation (complete):** SQLAlchemy mapping, Alembic
   migration, and a PostgreSQL-targeted repository adapter behind the current
   port. File artifacts and private resume configuration remain separate.
2. **3.4 Execution history (complete):** append-only transition events,
   existing stage-attempt counts, keyset-paginated run-list queries, and safe
   run-detail DTOs.
3. **3.5 API contracts (complete):** FastAPI liveness/readiness, run-list,
   run-detail, and fixed-workflow metadata routes with Pydantic schemas,
   configurable local CORS, and no browser-visible secrets.
4. **4.1 React admin foundation + read-only control plane (complete):** separate
   Vite workspace, application shell, typed API client, query/error states,
   dashboard, run list, detail/timeline, and workflows. Authentication is not
   claimed; this is localhost-only and read-only.
5. **4.2 Local runtime package + developer control plane (complete):** Compose,
   Make targets, migrations-before-API startup, health checks, durable local
   volumes, and documentation for the actual PostgreSQL/API/admin/docs stack.
6. **4.3 Provider, model, and credential-reference control plane (complete):**
   one supported OpenAI Responses provider record, an `env:NAME` credential
   reference, one model assignment for the content workflow, local token-gated
   writes, and append-only audit history. It stores no credential value.
7. **4.4 Integrations and publishing:** credential references, publication
   records, explicit confirmations, retries, and audit visibility.

## Phase 4.1 Page Plan

The implemented shell exposes Dashboard, Runs, and Workflows because those are
backed by the API. It intentionally omits Agents, Tools, Prompts, Providers,
Integrations, and Settings rather than showing non-functional controls. The
dashboard, runs page, run detail page, stage timeline, and workflow page are
all read models. Artifact bytes and approval actions remain absent because the
backend does not safely support them yet.

## Local Package

Phase 4.2 standardizes development around `make local-up`, `make local-down`,
`make local-status`, `make local-logs`, and `make local-check`. PostgreSQL and
artifacts use named volumes; normal shutdown preserves them, and the reset
target requires explicit destructive confirmation. The API runs Alembic before
serving, so readiness is not reported against an outdated schema.

## Phase 4.3 Boundary

The Model settings page sends only safe provider metadata, an environment
variable credential reference, and a model name. The local control token is
held in browser memory for one session; it is not an API key and is never
stored in the database. This milestone does not add generic provider URLs,
prompt editing, tool editing, encrypted secrets, or browser-launched runs
because those require their own policy and audit models.

## Learning Note

An admin interface is an adapter, just like a CLI. It should translate
operator intent into tested application commands and render query results. It
should not become a second orchestrator, a database client, or a secret store.
That boundary keeps an agent system inspectable: the same rules apply whether
an operator uses the terminal, an API, or a browser.
