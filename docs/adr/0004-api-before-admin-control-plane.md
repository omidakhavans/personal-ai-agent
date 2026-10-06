# ADR 0004: Build A Typed API Before The Admin Control Plane

## Status

Accepted.

## Context

The runtime currently has a CLI, deterministic orchestration, a file-backed
adapter, and a PostgreSQL-targeted persistence adapter. It does not have
queryable history, HTTP endpoints, browser authentication, configuration
records, or credential management. A separate operator UI is a Phase 4 goal.

## Decision

Finish queryable execution history and add typed FastAPI application contracts
before building the React operator UI. The UI will call those contracts through
an API client. It will not access PostgreSQL directly, recreate orchestration
rules, invoke model providers, or receive credential values.

The static learning documentation site stays separate from the operator UI.

## Consequences

- The first control-plane pages can show only backend-supported capabilities.
- API tests and application use cases become the shared behavior for both CLI
  and browser interfaces.
- Provider, prompt, tool, integration, and credential management wait for
  explicit backend resources and authorization policies.
- The delivery sequence takes more small steps, but avoids a dashboard whose
  visible controls have no safe implementation behind them.
