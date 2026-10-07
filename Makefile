.DEFAULT_GOAL := help
COMPOSE := docker compose --env-file .env

.PHONY: help validate-env local-up local-down local-restart local-status local-logs local-check local-reset db-shell db-migrate db-current db-history test lint typecheck docs-check admin-check check

help:
	@printf '%s\n' 'Local runtime commands:' '  make local-up' '  make local-down' '  make local-restart' '  make local-status' '  make local-logs' '  make local-check' '  make local-reset CONFIRM=reset' '  make db-shell|db-migrate|db-current|db-history' '  make test|lint|typecheck|docs-check|admin-check|check'

validate-env:
	@test -f .env || (echo 'Missing .env. Copy .env.example to .env first.' >&2; exit 1)

local-up: validate-env
	$(COMPOSE) up --build --detach
	$(MAKE) local-check
local-down: validate-env
	$(COMPOSE) down
local-restart: local-down local-up
local-status: validate-env
	./scripts/local-status.sh
local-logs: validate-env
	$(COMPOSE) logs --follow --tail=200
local-check: validate-env
	./scripts/local-check.sh
local-reset: validate-env
	@test "$(CONFIRM)" = "reset" || (echo 'This deletes local database and artifact volumes. Re-run with CONFIRM=reset.' >&2; exit 1)
	$(COMPOSE) down --volumes --remove-orphans
	$(COMPOSE) up --build --detach
	$(MAKE) local-check
db-shell: validate-env
	$(COMPOSE) exec postgres psql --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB"
db-migrate: validate-env
	$(COMPOSE) exec api alembic upgrade head
db-current: validate-env
	$(COMPOSE) exec api alembic current
db-history: validate-env
	$(COMPOSE) exec api alembic history
test: validate-env
	$(COMPOSE) run --rm --no-deps api python -m unittest discover -s tests
lint: validate-env
	$(COMPOSE) run --rm --no-deps api python -m ruff check personal_ai_agent tests
typecheck: validate-env
	$(COMPOSE) run --rm --no-deps api python -m mypy
	$(COMPOSE) run --rm --no-deps admin npm run typecheck
docs-check: validate-env
	$(COMPOSE) run --rm --no-deps docs npm run typecheck
	$(COMPOSE) run --rm --no-deps docs npm run build
admin-check: validate-env
	$(COMPOSE) run --rm --no-deps admin npm run test
	$(COMPOSE) run --rm --no-deps admin npm run build
check: lint typecheck test admin-check docs-check
