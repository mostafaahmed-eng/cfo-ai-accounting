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
ENCRYPTION_KEY=<32-byte-base64>
POSTGRES_PASSWORD=<strong-password>
OPENROUTER_API_KEY=<your-key>
TELEGRAM_BOT_TOKEN=<your-token>
TELEGRAM_BOT_USERNAME=<your-bot-username>
TELEGRAM_WEBHOOK_SECRET=<random-webhook-secret>
TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK=false
```

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
```

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

Once you have a public HTTPS URL:
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourdomain.com/api/v1/telegram/webhook", "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"}'
```

`TELEGRAM_WEBHOOK_SECRET` is mandatory outside the explicit local-development
bypass. Keep `TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK=false` in staging and production.
To connect a company, request a pairing link from Telegram Settings and send the
generated `/start <single-use-code>` command to the configured bot before the code
expires. Pairing codes are returned once and only their hashes are stored.

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
