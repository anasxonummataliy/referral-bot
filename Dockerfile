FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependency fayllarni ko'chirish (layer caching uchun)
COPY pyproject.toml uv.lock* ./

# Dependencies o'rnatish (system install, venv yo'q)
RUN uv pip install --system --no-cache \
    "aiogram>=3.28.2" \
    "aiosqlite>=0.22.1" \
    "fastapi>=0.136.1" \
    "uvicorn>=0.47.0" \
    "sqlalchemy>=2.0.49" \
    "pydantic-settings>=2.14.1" \
    "greenlet>=3.5.0"

# Source code
COPY . .

# SQLite data papkasi
RUN mkdir -p /app/data

EXPOSE 8011

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8011"]
