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
PostgreSQL persistence foundation and queryable history are complete; the next
required boundary is the API.

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

The UI will use React, TypeScript, Vite, shadcn/ui, TanStack Query, React Hook
Form, and Zod after stable API schemas exist. Generated or manually maintained
types must derive from the API contract, not duplicate backend business rules.
The development composition will add a database, API, and admin service only
when those services exist; the documentation site stays independently
deployable as static content.

## Milestones And Pull Requests

1. **3.3 Persistence foundation (complete):** SQLAlchemy mapping, Alembic
   migration, and a PostgreSQL-targeted repository adapter behind the current
   port. File artifacts and private resume configuration remain separate.
2. **3.4 Execution history (complete):** append-only transition events,
   existing stage-attempt counts, keyset-paginated run-list queries, and safe
   run-detail DTOs.
3. **3.5 API contracts:** FastAPI routes for existing safe actions, typed
   schemas, API tests, and no browser-visible secrets.
4. **4.1 Admin foundation:** separate Vite workspace, application shell,
   navigation, authenticated API client, query/error states, and local service
   composition. Only pages backed by the API ship.
5. **4.2 Runs:** dashboard, run list, stage timeline, artifact viewer, and
   approval actions.
6. **4.3 Configuration:** providers, models, workflows, tools, and prompts as
   versioned backend resources.
7. **4.4 Integrations and publishing:** credential references, publication
   records, explicit confirmations, retries, and audit visibility.

## Phase 4.1 Page Plan

The eventual shell will reserve navigation for Dashboard, Runs, Agents,
Workflows, Tools, Prompts, Providers, Integrations, and Settings. At launch it
will expose only Dashboard and Runs if the API supports them; unsupported
sections remain absent rather than appearing as non-functional controls.

## Learning Note

An admin interface is an adapter, just like a CLI. It should translate
operator intent into tested application commands and render query results. It
should not become a second orchestrator, a database client, or a secret store.
That boundary keeps an agent system inspectable: the same rules apply whether
an operator uses the terminal, an API, or a browser.
