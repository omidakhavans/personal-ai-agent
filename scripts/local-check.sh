#!/bin/sh
set -eu

if [ ! -f .env ]; then
  echo "Missing .env. Copy .env.example to .env before using local commands." >&2
  exit 1
fi

set -a
. ./.env
set +a

for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error "http://127.0.0.1:${API_PORT}/api/v1/ready" >/dev/null \
    && curl --fail --silent --show-error "http://127.0.0.1:${ADMIN_PORT}/" >/dev/null \
    && curl --fail --silent --show-error "http://127.0.0.1:${DOCS_PORT}/" >/dev/null; then
    echo "Local runtime is ready: API, admin, and learning site responded."
    exit 0
  fi
  [ "$attempt" -eq 30 ] && break
  sleep 2
done

echo "Local runtime did not become ready. Inspect service status and logs." >&2
docker compose --env-file .env ps >&2
exit 1
