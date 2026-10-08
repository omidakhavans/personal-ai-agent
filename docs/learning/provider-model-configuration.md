# Provider And Model Configuration

Phase 4.3 adds a small configuration boundary between the runtime and a model
provider. It does not add a credential vault, a model gateway, background jobs,
or publishing.

## What Is Stored

PostgreSQL stores a provider identifier, display name, fixed provider kind,
enabled state, and a credential reference such as `env:OPENAI_API_KEY`. It also
stores one selected provider/model pair for the `content` workflow. An
append-only audit row records each successful provider or model change.

The database does **not** contain an API key. The API does not accept an API
key. The React application does not display or persist an API key. During an
actual model call, the provider factory resolves the environment reference at
the execution edge.

## Write Authorization

Configuration writes require the `X-Admin-Token` header. The local React page
asks the operator for this token and keeps it only in page memory. The token is
not written to browser storage or committed configuration. If
`PERSONAL_AI_AGENT_ADMIN_TOKEN` is unset, all write routes are disabled.

This is a deliberately local development control, not multi-user
authentication. Before exposing the control plane beyond localhost, the system
needs real identity, authorization, session management, and audit attribution.

## What The Model Setting Means Today

The configuration record establishes the future source of truth for an
API-launched workflow. The existing Phase 2 CLI remains explicit: its `--model`
argument chooses the current run, while its provider client is now created
through the provider/credential-reference abstraction. Connecting API run
launch to the stored model configuration belongs with a later command/worker
milestone, not this configuration milestone.

## Try It Locally

1. Put a unique local control token in `.env` as
   `PERSONAL_AI_AGENT_ADMIN_TOKEN`.
2. Run `make local-restart` after changing `.env`.
3. Open the control plane and choose **Model settings**.
4. Enter the local control token, save the OpenAI provider reference, then save
   the content workflow’s model assignment.
5. Confirm the audit table records both changes without revealing a credential.
