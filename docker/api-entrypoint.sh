#!/bin/sh
set -eu

# Alembic is idempotent. The API does not serve an unmigrated schema.
alembic upgrade head

exec uvicorn personal_ai_agent.api.app:app --host 0.0.0.0 --port 8000
