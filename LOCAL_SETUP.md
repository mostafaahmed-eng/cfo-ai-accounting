# Local Development & Test Environment

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | ≥ 24.0 | Containers for all services |
| Docker Compose | ≥ 2.22 | Multi-service orchestration |

No local Python, Node.js, or PostgreSQL installation is required — everything runs inside containers.

---

## Quick Start

### 1. Create your `.env` files

```bash
cp cfo-backend/.env.example cfo-backend/.env
cp cfo-dashboard/.env.local.example cfo-dashboard/.env.local
```

The `.env` files contain safe local placeholders. You do **not** need real API keys
for basic development — only `SECRET_KEY` and database/Redis URLs matter locally.

### 2. Build and start all services

```bash
docker compose up --build
```

What happens, step by step:

1. **postgres** starts and waits for `pg_isready` to confirm the database is accepting connections.
2. **redis** starts and waits for `redis-cli ping` to confirm it is responsive.
3. **backend** builds the Python image (installs deps from `pyproject.toml` via pip),
   then runs `alembic upgrade head` to apply all migrations, and finally starts
   `uvicorn app.main:app --reload` on port **8000**.
4. **celery-worker** builds the same Python image, then starts a Celery worker
   listening on all 3 queues: `receipt-processing`, `ai-extraction`,
   `telegram-responses`.
5. **frontend** builds the Node.js image (`npm ci` from lockfile + `npm run dev`) and starts
   Next.js on port **3000**.

Once all services are healthy, you have:

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8000 | FastAPI backend |
| OpenAPI Docs | http://localhost:8000/docs | Swagger UI (interactive) |
| ReDoc | http://localhost:8000/redoc | ReDoc documentation |
| Dashboard | http://localhost:3000 | Next.js frontend |

---

## Running the Test Suite

The backend has **59 unit tests** (no database required) and **25 integration/e2e tests**
that require a running PostgreSQL instance with the test schema applied.

### Unit tests only (no PostgreSQL needed)

Run locally (requires Python 3.11+ and pip):

```bash
cd cfo-backend
python -m venv .venv && .venv/Scripts/activate   # or: python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/unit/ -v
```

### Full test suite (requires PostgreSQL)

Inside the running Docker Compose environment (PostgreSQL + backend are both up):

```bash
docker compose exec backend pytest -v
```

The conftest automatically creates a `cfo_manager_test` database, applies all tables,
runs the tests, then tears everything down. When PostgreSQL is not reachable, integration
and e2e tests are automatically **skipped** (unit tests still run).

To force re-creating the test database:

```bash
docker compose exec backend pytest -v --tb=short
```

---

## API Examples (curl)

The `/api/v1/intake/text` endpoint requires a valid JWT. For quick testing without a
full user flow, you can first create a user and company via the API, then log in to get
a token. Below are two examples assuming you have a valid token in `$TOKEN`.

### English expense

```bash
curl -s -X POST http://localhost:8000/api/v1/intake/text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text": "I spent $100 for VPS hosting"}'
```

Expected (200):

```json
{
  "id": "...",
  "company_id": "...",
  "source": "web_text",
  "content_type": "text",
  "original_text": "I spent $100 for VPS hosting",
  "detected_language": "en",
  "status": "received",
  ...
}
```

### Arabic expense

```bash
curl -s -X POST http://localhost:8000/api/v1/intake/text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text": "دفعت ٥٠٠ جنيه إعلانات"}'
```

Expected (200):

```json
{
  "id": "...",
  "company_id": "...",
  "source": "web_text",
  "content_type": "text",
  "original_text": "دفعت ٥٠٠ جنيه إعلانات",
  "detected_language": "ar",
  "status": "received",
  ...
}
```

**Without a token**, both return `401 Unauthorized` — which confirms auth is enforced.

---

## Frontend Decoupling Check

The spec requires all API calls to go through the single file
`src/lib/api-client.ts`. Verify no stray `fetch(` calls exist elsewhere:

```bash
rg "fetch\(" cfo-dashboard/src --include="*.ts" --include="*.tsx" \
  --glob="!src/lib/api-client.ts" -n
```

**Expected result:** no matches (exit code 1 from `rg`).

If this returns any matches, the frontend decoupling rule has been violated.

---

## Stopping and Cleanup

### Stop all services (preserves data volumes)

```bash
docker compose down
```

### Stop all services AND wipe the database volume

```bash
docker compose down -v
```

The `-v` flag removes the named `pgdata` volume, so the next `docker compose up`
starts with a fresh empty PostgreSQL database.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `backend` exits immediately with Alembic error | `postgres` healthcheck passed but DB isn't fully ready yet | Run `docker compose up backend` again; or increase the `retries` in the postgres healthcheck |
| Frontend shows "Failed to fetch" or CORS error in browser | `NEXT_PUBLIC_API_BASE_URL` doesn't match the backend URL | Ensure `.env.local` contains `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` (with `/api/v1`) |
| Celery worker shows "none of the queues are available" | Redis hasn't started yet | `celery-worker` depends on `redis` being healthy — this should not happen with the compose file as-is; restart with `docker compose restart celery-worker` |
| Port 8000 or 3000 already in use | Another process occupies the port | `lsof -i :8000` (or `:3000`) to find the process, then stop it; or change the port mapping in `docker-compose.yml` |
| `pyproject.toml` build fails during Docker build | Package discovery error — multiple top-level dirs (`app` + `alembic`) | `pyproject.toml` includes `[tool.setuptools.packages.find] include = ["app*"]` to resolve this. Rebuild with `docker compose build --no-cache backend` |
| Integration tests all skip locally | PostgreSQL not running on localhost:5432 | Expected outside Docker. Run `docker compose up -d postgres` first, or run tests inside the container: `docker compose exec backend pytest` |
| `asyncpg` or `psycopg` compilation fails | Missing system C compiler | The Dockerfile installs `gcc`; if building on ARM you may need `build-essential` instead |
| `npm ci` fails in frontend container | Lockfile mismatch or missing | Regenerate lockfile: `cd cfo-dashboard && npm install`, then rebuild |
