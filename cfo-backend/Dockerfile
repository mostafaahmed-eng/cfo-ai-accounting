FROM python:3.11-slim

WORKDIR /app

# System deps: libmagic for python-magic, gcc for C extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libmagic1 \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"

# Copy application code
COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
