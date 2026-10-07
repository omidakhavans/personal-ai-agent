#!/bin/sh
set -eu

# Compose quality targets use this image for one-off commands. Do not start a
# second API process when Docker has supplied an explicit command.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# Alembic is idempotent. The API does not serve an unmigrated schema.
alembic upgrade head

exec uvicorn personal_ai_agent.api.app:app --host 0.0.0.0 --port 8000
