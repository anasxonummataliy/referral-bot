FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    aiogram \
    fastapi \
    uvicorn \
    sqlalchemy \
    asyncpg \
    pydantic-settings \
    aiohttp

COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8011"]
