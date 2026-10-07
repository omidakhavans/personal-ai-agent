#!/bin/sh
set -eu

if [ ! -f .env ]; then
  echo "Missing .env. Copy .env.example to .env before using local commands." >&2
  exit 1
fi

set -a
. ./.env
set +a

docker compose --env-file .env ps
printf '\nEndpoint checks:\n'
for endpoint in "API|http://127.0.0.1:${API_PORT}/api/v1/ready" "Admin|http://127.0.0.1:${ADMIN_PORT}/" "Learning site|http://127.0.0.1:${DOCS_PORT}/"; do
  label=${endpoint%%|*}
  url=${endpoint#*|}
  if curl --fail --silent "$url" >/dev/null; then
    printf '%s: ready\n' "$label"
  else
    printf '%s: unavailable\n' "$label"
  fi
done
