# Production Deployment Guide

## Prerequisites
- Docker Engine 24+ and Docker Compose v2
- Git
- A Linux server (Ubuntu 22.04+ recommended) or cloud VM
- Domain name with DNS pointed to your server
- SSL certificate (Let's Encrypt recommended)

## Quick Start

### 1. Clone and configure
```bash
git clone <repo-url> && cd cfo-manager
cp .env.example .env
# Edit .env with production values
```

### 2. Required secrets in .env
```bash
# Generate with: openssl rand -hex 32
SECRET_KEY=<32-byte-hex>
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# The backend refuses to start in production without a valid Fernet key.
ENCRYPTION_KEY=<valid-fernet-key-ending-in-equals>
POSTGRES_PASSWORD=<strong-password>
# MinIO root credentials (used by both MinIO and the backend's S3 client).
# Generate with: openssl rand -hex 16
MINIO_ROOT_USER=<minio-user>
MINIO_ROOT_PASSWORD=<minio-strong-password>
# Browser origin(s) allowed to call the API, comma-separated. Must match the
# frontend URL exactly (e.g. https://yourdomain.com). No wildcard in production.
CORS_ALLOWED_ORIGINS=https://yourdomain.com
OPENROUTER_API_KEY=<your-key>
TELEGRAM_BOT_TOKEN=<your-token>
TELEGRAM_BOT_USERNAME=<your-bot-username>
TELEGRAM_WEBHOOK_SECRET=<random-webhook-secret>
TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK=false
# Only needed if you generate presigned document download links from outside the
# server. If left empty, downloads fall back to the internal MinIO endpoint.
# S3_PUBLIC_ENDPOINT_URL=https://yourdomain.com
```

The minimum set of variables that will fail deployment if missing:
`POSTGRES_PASSWORD`, `SECRET_KEY`, `ENCRYPTION_KEY`, `MINIO_ROOT_PASSWORD`,
`CORS_ALLOWED_ORIGINS`, `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_WEBHOOK_SECRET`.

### 3. Deploy
```bash
chmod +x scripts/*.sh
./scripts/deploy.sh production
```

## Architecture

```
Internet → Nginx (80/443) → Frontend (3000)
                           → Backend API (8000)
                           → Celery Worker (internal)
                           → PostgreSQL (internal)
                           → Redis (internal)
                           → MinIO (internal, object storage)
```

MinIO runs on the internal `backend` network only — no public ports. Receipts
are uploaded by the backend and processed by the Celery worker over that
network. The `minio-init` one-shot service creates the bucket on first boot.
To inspect the MinIO console from the server, forward the console port:
`docker compose -f docker-compose.prod.yml exec minio sh` or use
`docker compose -f docker-compose.prod.yml run --rm -p 9001:9001 minio server /data --console-address ":9001"`.

## CI/CD Pipelines

### GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `tests.yml` | Push/PR to main/develop | Run pytest suite + ruff/mypy lint |
| `frontend.yml` | Push/PR touching cfo-dashboard/ | Type-check + lint + build frontend |
| `docker.yml` | Push to main or tags | Build & push Docker images to GHCR |
| `security.yml` | Push/PR + weekly schedule | Dependency audit, Trivy scan, secret scan |
| `deploy.yml` | Push to main (staging), tags (production) | SSH deploy with health checks |

### Required GitHub Secrets

**Staging:**
- `STAGING_SSH_KEY` — SSH private key for staging server
- `STAGING_HOST` — staging server IP/hostname
- `STAGING_USER` — SSH username

**Production:**
- `PRODUCTION_SSH_KEY` — SSH private key for production server
- `PRODUCTION_HOST` — production server IP/hostname
- `PRODUCTION_USER` — SSH username

### Required GitHub Environments
Create `staging` and `production` environments in repo Settings → Environments with deployment protection rules.

## Make Commands

```bash
make help              # Show all commands
make dev               # Start development
make test              # Run tests in Docker
make test-cov          # Tests with coverage report
make lint              # Ruff linting
make typecheck         # MyPy type checking
make docker-build      # Build production images
make docker-up         # Start production services
make deploy-staging    # Deploy to staging
make deploy-production # Deploy to production
make rollback          # Rollback to previous version
make health-check      # Check all services
```

## SSL/HTTPS Setup

1. Obtain certificate (e.g., Let's Encrypt):
```bash
certbot certonly --standalone -d yourdomain.com
```

2. Place certs in `nginx/ssl/`:
```bash
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
```

3. Uncomment HTTPS block in `nginx/nginx.conf` and update server_name.

4. Restart nginx:
```bash
docker compose -f docker-compose.prod.yml restart nginx
```

## Telegram Webhook (Production)

The one-command script reads `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` and
`PUBLIC_BASE_URL` from the environment, calls `setWebhook`, then verifies with
`getWebhookInfo`. It can run on the server or anywhere the token is available:

```bash
# From the repo root, against the running backend container:
docker compose -f docker-compose.prod.yml exec backend python -m app.scripts.telegram_setup

# Or locally, against a reachable public URL:
PUBLIC_BASE_URL=https://yourdomain.com python -m app.scripts.telegram_setup
```

The webhook URL is `PUBLIC_BASE_URL + /api/v1/telegram/webhook`. The script
prints a clear success or failure summary (including whether Telegram reports
`last_error`/pending updates). Equivalent raw curl:

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourdomain.com/api/v1/telegram/webhook", "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"}'
```

`TELEGRAM_WEBHOOK_SECRET` is mandatory outside the explicit local-development
bypass, and the webhook endpoint is rate-limited (`RATE_LIMIT_WEBHOOK`, default
30/minute per IP) as an extra abuse guard. Keep
`TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK=false` in staging and production.
To connect a company, request a pairing link from Telegram Settings and send the
generated `/start <single-use-code>` command to the configured bot before the code
expires. Pairing codes are returned once and only their hashes are stored.

## Backup & Restore

Database and object storage are both persisted in named volumes (`pgdata`,
`redisdata`, `miniodata`). Back up the database daily and the volumes as needed.

```bash
# Backup database to a file
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore (drop/recreate as needed)
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backup_20260101_120000.sql
```

> `ENCRYPTION_KEY` and `SECRET_KEY` are not recoverable from backups. Store them
> safely (password manager / secret manager); losing `ENCRYPTION_KEY` makes any
> encrypted-at-rest values unreadable, and losing `SECRET_KEY` invalidates all
> issued JWTs.

## Firewall

Only expose Nginx. Everything else lives on the internal `backend`/`frontend`
networks and must not be published.

| Port | Protocol | Purpose | Public? |
|---|---|---|---|
| 22 | TCP | SSH (admin) | Optional / VPN-only |
| 80 | TCP | HTTP → HTTPS redirect | Yes |
| 443 | TCP | HTTPS | Yes |

```bash
# ufw example
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

Do not open 5432 (Postgres), 6379 (Redis), 9000/9001 (MinIO), 3000 (frontend)
or 8000 (backend) to the public internet.

## Monitoring

- Health endpoint: `GET /health`
- Run `./scripts/health-check.sh` for full status
- Check logs: `make docker-logs`
- Container status: `make docker-ps`

## Rollback

```bash
# Automatic rollback to previous git version
./scripts/rollback.sh

# Or manual
git checkout <previous-tag>
make docker-build
make docker-up
```

## Troubleshooting

**Backend won't start:**
```bash
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

**Celery tasks not running:**
```bash
docker compose -f docker-compose.prod.yml logs celery-worker
docker compose -f docker-compose.prod.yml restart celery-worker
```

**Database connection refused:**
```bash
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U postgres
docker compose -f docker-compose.prod.yml restart postgres
```
