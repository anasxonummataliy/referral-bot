.PHONY: help install dev test test-cov lint format clean docker-build docker-up docker-down docker-logs

help:
	@echo "Referral Bot - Available Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install production dependencies"
	@echo "  make dev            Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-cov       Run tests with coverage report"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-int       Run integration tests only"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run linters (ruff, mypy, pylint)"
	@echo "  make format         Format code with ruff and black"
	@echo "  make check          Run linters and type checks (non-blocking)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-up      Start Docker Compose stack"
	@echo "  make docker-down    Stop Docker Compose stack"
	@echo "  make docker-logs    View Docker logs"
	@echo "  make docker-test    Run tests in Docker container"
	@echo ""
	@echo "Development:"
	@echo "  make run            Run FastAPI development server"
	@echo "  make clean          Remove temporary files"
	@echo "  make db-migrate     Create database tables (requires DB running)"
	@echo ""

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=app --cov=api --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

test-unit:
	pytest tests/ -v -m "not integration"

test-int:
	pytest tests/ -v -m integration

lint:
	@echo "Running Ruff..."
	ruff check app/ api/ tests/ --show-source
	@echo "Running MyPy..."
	mypy app/ api/ --ignore-missing-imports --no-implicit-optional
	@echo "Running Pylint..."
	pylint app/ api/ --exit-zero --max-line-length=120

format:
	@echo "Formatting code with ruff..."
	ruff format app/ api/ tests/
	@echo "Checking format with ruff..."
	ruff check app/ api/ tests/ --fix

check:
	@echo "Linting with Ruff..."
	ruff check app/ api/ tests/ || true
	@echo "Type checking with MyPy..."
	mypy app/ api/ --ignore-missing-imports || true

run:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

clean:
	@echo "Cleaning temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage
	@echo "Cleanup complete!"

docker-build:
	@echo "Building Docker image..."
	docker build -t referral-bot:latest .
	@echo "Build complete!"

docker-up:
	@echo "Starting Docker Compose stack..."
	docker-compose up -d
	@echo "Stack started! Services:"
	@echo "  - Bot: http://localhost:8000"
	@echo "  - PostgreSQL: localhost:5435"
	@echo "  - Redis: localhost:6379"

docker-down:
	@echo "Stopping Docker Compose stack..."
	docker-compose down

docker-logs:
	docker-compose logs -f bot

docker-test:
	@echo "Running tests in Docker..."
	docker-compose exec bot pytest tests/ -v

db-migrate:
	@echo "Creating database tables..."
	python -c "import asyncio; from app.database.session import init_db; asyncio.run(init_db())"
	@echo "Database tables created!"

.DEFAULT_GOAL := help
