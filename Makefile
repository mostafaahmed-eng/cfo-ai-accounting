.PHONY: help dev test lint typecheck build clean docker-up docker-down docker-test deploy rollback

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Development ---
dev: ## Start all services in development mode
	docker compose up --build

dev-d: ## Start all services in development mode (detached)
	docker compose up --build -d

dev-down: ## Stop development services
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f

logs-backend: ## Tail backend logs
	docker compose logs -f backend

logs-worker: ## Tail celery worker logs
	docker compose logs -f celery-worker

# --- Testing ---
test: ## Run backend tests (Docker)
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from backend-test

test-local: ## Run backend tests locally (requires running postgres/redis)
	cd cfo-backend && python -m pytest tests/ -v --tb=short -x

test-cov: ## Run backend tests with coverage
	cd cfo-backend && python -m pytest tests/ -v --tb=short --cov=app --cov-report=html --cov-report=term -x

test-e2e: ## Run E2E tests only
	cd cfo-backend && python -m pytest tests/e2e/ -v --tb=short -x

test-integration: ## Run integration tests only
	cd cfo-backend && python -m pytest tests/integration/ -v --tb=short -x

test-unit: ## Run unit tests only
	cd cfo-backend && python -m pytest tests/unit/ -v --tb=short -x

# --- Linting ---
lint: ## Run linter (ruff)
	cd cfo-backend && python -m ruff check app/ tests/

lint-fix: ## Auto-fix lint issues
	cd cfo-backend && python -m ruff check app/ tests/ --fix

format: ## Format code
	cd cfo-backend && python -m ruff format app/ tests/

# --- Type Checking ---
typecheck: ## Run mypy type checking
	cd cfo-backend && python -m mypy app/ --ignore-missing-imports

# --- Frontend ---
fe-install: ## Install frontend dependencies
	cd cfo-dashboard && npm install

fe-lint: ## Lint frontend
	cd cfo-dashboard && npm run lint

fe-typecheck: ## Type-check frontend
	cd cfo-dashboard && npm run typecheck

fe-build: ## Build frontend
	cd cfo-dashboard && npm run build

# --- Database ---
db-migrate: ## Create a new Alembic migration
	cd cfo-backend && alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## Apply all pending migrations
	cd cfo-backend && alembic upgrade head

db-downgrade: ## Rollback last migration
	cd cfo-backend && alembic downgrade -1

db-history: ## Show migration history
	cd cfo-backend && alembic history

# --- Docker Production ---
docker-build: ## Build production images
	docker compose -f docker-compose.prod.yml build

docker-up: ## Start production services
	docker compose -f docker-compose.prod.yml up -d

docker-down: ## Stop production services
	docker compose -f docker-compose.prod.yml down

docker-ps: ## Show running production services
	docker compose -f docker-compose.prod.yml ps

docker-logs: ## Tail production logs
	docker compose -f docker-compose.prod.yml logs -f

# --- Docker Testing ---
docker-test: ## Run tests in Docker
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from backend-test

docker-test-down: ## Stop test containers
	docker compose -f docker-compose.test.yml down -v

# --- Deployment ---
deploy-staging: ## Deploy to staging
	./scripts/deploy.sh staging

deploy-production: ## Deploy to production
	./scripts/deploy.sh production

rollback: ## Rollback to previous version
	./scripts/rollback.sh

health-check: ## Check service health
	./scripts/health-check.sh

# --- Cleanup ---
clean: ## Clean build artifacts
	cd cfo-backend && rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov .coverage
	cd cfo-dashboard && rm -rf .next out
	docker compose -f docker-compose.test.yml down -v 2>/dev/null || true

clean-docker: ## Remove all Docker images and volumes
	docker compose down -v --rmi local 2>/dev/null || true
	docker system prune -f
