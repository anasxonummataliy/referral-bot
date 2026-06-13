FROM python:3.13-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files (layer caching uchun)
COPY pyproject.toml uv.lock* ./

# Dependencies o'rnatish (uv venv ishlatmasdan, system install)
RUN uv pip install --system --no-cache -r pyproject.toml 2>/dev/null || \
    uv pip install --system --no-cache \
        "aiogram>=3.28.2" \
        "aiosqlite>=0.22.1" \
        "fastapi>=0.136.1" \
        "uvicorn>=0.47.0" \
        "sqlalchemy>=2.0.49" \
        "pydantic-settings>=2.14.1" \
        "greenlet>=3.5.0"

# Source code nusxalash
COPY . .

# SQLite uchun data papkasi
RUN mkdir -p /app/data

EXPOSE 8011

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8011"]
