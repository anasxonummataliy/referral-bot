# Development Setup Guide

## Prerequisites
- Python 3.13+
- Docker and Docker Compose (for containerized setup)
- PostgreSQL 16+ (if running without Docker)
- Redis 7+ (if running without Docker)

## Local Development Setup (without Docker)

### 1. Install Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install project and dev dependencies
pip install -e ".[dev]"
```

### 2. Setup Environment
```bash
# Copy example environment
cp .env.example .env

# Edit .env with your values
nano .env  # Or use your editor
```

Required environment variables:
- `BOT_TOKEN`: Your Telegram bot token
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: PostgreSQL credentials
- `WEBHOOK_HOST`: Your bot's webhook URL
- `ADMIN`: Comma-separated admin user IDs

### 3. Setup Database
```bash
# PostgreSQL must be running on localhost:5435
# Create database and run migrations
python -m pytest tests/test_models.py  # This will create test tables
```

### 4. Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=api --cov-report=html

# Run specific test file
pytest tests/test_models.py -v

# Run specific test
pytest tests/test_models.py::TestUserModel::test_user_creation -v

# Run only integration tests
pytest -m integration

# Run with detailed output
pytest -v --tb=long
```

### 5. Run the Bot (Development Mode)
```bash
# Option 1: Direct with uvicorn
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Option 2: With Python
python -m uvicorn api.main:app --reload
```

### 6. Linting and Code Quality
```bash
# Run all linters
ruff check app/ api/ tests/
ruff format app/ api/ tests/

# Type checking
mypy app/ api/ --ignore-missing-imports

# Advanced linting
pylint app/ api/ --exit-zero
```

---

## Docker Setup

### 1. Using Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up -d

# Check logs
docker-compose logs -f bot

# Stop services
docker-compose down

# Remove volumes (careful - deletes data)
docker-compose down -v
```

**Services running:**
- PostgreSQL on localhost:5435
- Redis on localhost:6379
- FastAPI bot on localhost:8000

### 2. Build Docker Image Manually

```bash
# Build image
docker build -t referral-bot:latest .

# Run container
docker run -it --rm \
  -e BOT_TOKEN=your_token \
  -e DB_HOST=localhost \
  -p 8000:8000 \
  referral-bot:latest
```

### 3. Run Tests in Docker

```bash
# With docker-compose
docker-compose exec bot pytest tests/ -v

# Build test image
docker build -t referral-bot:test --target builder .
docker run --rm referral-bot:test pytest tests/
```

---

## CI/CD Pipeline

The project includes GitHub Actions workflows in `.github/workflows/`:

### 1. Tests (`.github/workflows/tests.yml`)
- Runs on push and pull requests
- Tests against PostgreSQL and Redis services
- Generates coverage reports
- Uploads to Codecov

### 2. Docker Build (`.github/workflows/docker-build.yml`)
- Builds Docker image
- Scans for vulnerabilities with Trivy
- Caches layers for faster builds

### 3. Linting (`.github/workflows/lint.yml`)
- Runs Ruff, MyPy, Pylint
- Checks code formatting
- Non-blocking (uses `continue-on-error`)

### View Results
- Push code to trigger workflows
- Check GitHub > Actions tab
- Download artifacts (coverage reports)

---

## Project Structure

```
referral-bot/
├── app/
│   ├── bot/                 # Telegram bot handlers
│   │   ├── handlers/        # Message and callback handlers
│   │   ├── middlewares/     # DB and subscription middlewares
│   │   └── commands.py      # Bot commands setup
│   ├── core/
│   │   └── config.py        # Environment settings
│   ├── database/
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── base.py          # Base model class
│   │   └── session.py       # Database session setup
│   ├── repositories/        # Data access layer
│   └── services/            # Business logic
├── api/
│   └── main.py             # FastAPI webhook endpoint
├── tests/
│   ├── conftest.py         # pytest fixtures
│   ├── test_models.py      # Model tests
│   ├── test_repositories.py # Repository tests
│   ├── test_services.py    # Service tests
│   ├── test_integration.py # Integration tests
│   └── test_config.py      # Configuration tests
├── Dockerfile              # Multi-stage production image
├── docker-compose.yml      # Complete stack definition
├── pyproject.toml          # Dependencies and tool config
└── pytest.ini              # Pytest configuration
```

---

## Common Commands

```bash
# Development
pytest                      # Run all tests
pytest -v                   # Verbose output
pytest --cov              # With coverage
pytest -k test_name       # Run specific tests
pytest -m integration     # Run integration tests only
pytest --lf               # Run last failed

# Code quality
ruff check .              # Lint check
ruff format .             # Auto format
mypy app/                 # Type checking

# Docker
docker-compose up -d      # Start services
docker-compose logs -f    # View logs
docker-compose down       # Stop services

# Database
# (Inside docker-compose)
docker-compose exec postgres psql -U referral_user -d referral_bot

# Linting with all tools
pytest && ruff check . && mypy app/
```

---

## Troubleshooting

### Tests fail with "database connection refused"
```bash
# Make sure PostgreSQL is running
# Docker: docker-compose up postgres
# Or configure DB_HOST in .env
```

### Import errors in tests
```bash
# Ensure you installed dev dependencies
pip install -e ".[dev]"
```

### Docker container exits
```bash
# Check logs
docker-compose logs bot

# Check bot token is set
echo $BOT_TOKEN
```

### Port already in use
```bash
# Change port in docker-compose.yml or .env
# Or kill existing process: lsof -i :8000
```

---

## Additional Resources

- [Aiogram Documentation](https://docs.aiogram.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [pytest Documentation](https://docs.pytest.org/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
