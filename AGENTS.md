# Repository Guidance

## Local Runtime

Use the Makefile as the canonical local interface. Copy `.env.example` to
`.env`, then use `make local-up`, `make local-status`, and `make local-down`.
The Compose stack contains only PostgreSQL, the FastAPI read API, the React
control plane, and the learning site. Do not add a worker, Redis, a model
provider, or publishing integration until the runtime actually requires it.

## Security And Public Data

Treat every committed file, documentation page, generated artifact, log, and
screenshot as public. Never commit credentials, `.env` values, local paths,
usernames, private URLs, run artifacts, or private source material. Use
placeholders in examples. Review the staged diff for sensitive data before
committing. The control plane must stay read-only until an authenticated,
audited command API exists.

## Quality

Run the narrow checks for the area changed and use `make check` when the local
stack is available. Preserve the domain/application/infrastructure boundary:
browser and HTTP code must not query PostgreSQL or read artifact files directly.
