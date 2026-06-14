.PHONY: setup db-up db-down test test-unit test-integration lint dev

setup:
	.venv/Scripts/pip install -e ".[dev]"

db-up:
	docker compose up -d postgres
	@echo "Waiting for PostgreSQL..."
	@timeout 30 bash -c 'until docker compose exec -T postgres pg_isready -U storeagent 2>/dev/null; do sleep 1; done'
	@echo "PostgreSQL is ready."

db-down:
	docker compose down

migrate:
	.venv/Scripts/python -m src.db.migrations.runner

test-unit:
	.venv/Scripts/pytest tests/unit/ -v

test-integration:
	.venv/Scripts/pytest tests/integration/ -v

test:
	.venv/Scripts/pytest tests/ -v

dev:
	.venv/Scripts/langgraph dev --no-browser
