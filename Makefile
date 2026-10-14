.PHONY: help dev api-dev web-dev lint test migrate build up down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Development ---
api-dev: ## Run API server locally (hot reload)
	cd apps/api && uvicorn app.main:app --reload --port 8000

web-dev: ## Run React dev server
	cd apps/web && npm run dev

dev: ## Run both API and web dev servers (requires two terminals)
	@echo "Run in separate terminals:"
	@echo "  make api-dev"
	@echo "  make web-dev"

# --- Quality ---
lint: ## Run all linters
	cd apps/api && ruff check . && ruff format --check .
	cd apps/web && npm run lint

lint-fix: ## Auto-fix lint issues
	cd apps/api && ruff check --fix . && ruff format .

test: ## Run backend tests
	cd apps/api && pytest -v

test-cov: ## Run tests with coverage
	cd apps/api && pytest --cov=app --cov-report=term-missing

# --- Database ---
migrate: ## Run Alembic migrations (uses DIRECT_DATABASE_URL)
	cd apps/api && alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new msg="description")
	cd apps/api && alembic revision --autogenerate -m "$(msg)"

# --- Docker ---
build: ## Build Docker images
	docker compose build

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail service logs
	docker compose logs -f

# --- CLI ---
create-business: ## Create a business (usage: make create-business name="Biz" email="a@b.com" password="secret")
	cd apps/api && python -m app.cli create-business --name "$(name)" --email "$(email)" --password "$(password)"
