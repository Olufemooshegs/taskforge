.PHONY: help up up-all down logs logs-db logs-worker logs-dashboard ps migrate revision test lint fmt typecheck shell-db shell-redis dashboard dashboard-logs

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Start postgres + redis only
	docker compose up -d postgres redis
	@sleep 2
	@docker compose ps

up-all: ## Start the full stack (postgres, redis, backend, worker, dashboard)
	docker compose up -d --build
	@sleep 3
	@docker compose ps

down: ## Stop and remove containers (keeps volumes)
	docker compose down

logs: ## Tail backend logs
	docker compose logs -f backend

logs-db: ## Tail postgres logs
	docker compose logs -f postgres

logs-worker: ## Tail worker logs
	docker compose logs -f worker

logs-dashboard: ## Tail dashboard logs
	docker compose logs -f dashboard

ps: ## Show running services
	docker compose ps

migrate: ## Run alembic migrations (inside backend container)
	docker compose exec backend alembic upgrade head

revision: ## Create migration (usage: make revision m="message")
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

test: ## Run backend tests
	docker compose exec backend pytest -q

lint: ## Ruff lint
	docker compose exec backend ruff check app tests

fmt: ## Ruff format
	docker compose exec backend ruff format app tests

typecheck: ## mypy
	docker compose exec backend mypy app

shell-db: ## Open psql in TaskForge postgres
	docker compose exec postgres psql -U taskforge -d taskforge

shell-redis: ## Open redis-cli in TaskForge redis
	docker compose exec redis redis-cli

dashboard: ## Open the dashboard in your browser
	@echo "Dashboard: http://localhost:3001"