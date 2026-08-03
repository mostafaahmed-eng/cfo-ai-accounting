# Production Deployment Guide — IP-based (no domain, no SSL yet)

This guide deploys the stack to a VPS reached directly by IP + port over plain HTTP,
e.g. `http://<VPS_IP>:8080`. HTTPS/Let's Encrypt is intentionally **not** configured yet
because no domain exists to issue a certificate for. That is a separate future task.

The stack uses a **single nginx entrypoint**: one port proxies both the frontend and the
API. This means no cross-origin issues in the browser and only one port to open in the
firewall.

---

## Prerequisites (on the server)

```bash
# Ubuntu 22.04+ recommended
sudo apt update && sudo apt install -y git curl docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
# Log out and back in so the docker group applies, then continue.
```

Verify:
```bash
docker --version
docker compose version
```

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/Wuzzify-Traniers/ai-cfo-manager.git
cd ai-cfo-manager
```

---

## Step 2 — Create the real `.env` file (never committed)

Copy the template and edit it on the server. Values below are placeholders — replace them.

```bash
cp .env.example .env
nano .env
```

The **required** variables for a working production deployment (backend refuses to boot
if these are missing/wrong):

| Variable | Value to use | Generate with |
|---|---|---|
| `POSTGRES_PASSWORD` | strong random password | `openssl rand -hex 32` |
| `SECRET_KEY` | strong random string | `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ENCRYPTION_KEY` | valid Fernet key (must end in `=`) | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `MINIO_ROOT_USER` | minio admin user | e.g. `minioadmin` (or `openssl rand -hex 8`) |
| `MINIO_ROOT_PASSWORD` | strong random password | `openssl rand -hex 32` |
| `CORS_ALLOWED_ORIGINS` | `http://<VPS_IP>:8080` | your server IP — must match the browser origin exactly |
| `OPENROUTER_API_KEY` | from https://openrouter.ai/keys | optional unless you want AI extraction |
| `NEXT_PUBLIC_API_BASE_URL` | `http://<VPS_IP>:8080/api/v1` | your server IP — note the `/api/v1` suffix |
| `TELEGRAM_BOT_TOKEN` | from @BotFather | optional unless you use Telegram |
| `TELEGRAM_WEBHOOK_SECRET` | random string | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `TELEGRAM_BOT_USERNAME` | bot username (no `@`) | from @BotFather |
| `NGINX_PORT` | `8080` | the single public port |

> `ENCRYPTION_KEY` and `SECRET_KEY` are unrecoverable if lost — they are **not** stored in
> the database. Back them up in a password manager before relying on this deployment.
>
> `NEXT_PUBLIC_API_BASE_URL` is baked into the frontend **at build time** (Next.js). If you
> change your IP/port, you must rebuild the frontend (`docker compose ... up --build -d`).
>
> **Finalize `POSTGRES_PASSWORD` and `MINIO_ROOT_PASSWORD` BEFORE the first `up`.** Those
> credentials are only applied when their data volumes are first initialized. Changing them
> later does not take effect (the container keeps the old ones) and the backend fails with
> `password authentication failed`. If you must change them after the first start, delete
> the volumes first — see Troubleshooting.

Everything else in `.env.example` has a working default. For the full inventory of every
variable and how to obtain it, see `MANUAL_SETUP_CHECKLIST.md`.

---

## Step 3 — Start the stack (first deploy, includes migrations)

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

This pulls/builds images, starts PostgreSQL + Redis + MinIO, runs the `minio-init`
one-shot (creates the bucket), then starts backend, celery-worker, frontend, and nginx.

Run migrations explicitly (the backend also runs them on boot, but do it once explicitly
to see the output):

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

Restart the backend so it is fully in sync with the migrated schema:

```bash
docker compose -f docker-compose.prod.yml restart backend celery-worker
```

---

## Step 4 — Open the firewall

Only these ports need to be reachable:

| Port | Protocol | Purpose | Public? |
|---|---|---|---|
| 22 | TCP | SSH (administration) | Yes (or restrict to your IP) |
| **8080** | TCP | **HTTP — the app (nginx entrypoint)** | **Yes** |

Do **not** open 5432 (Postgres), 6379 (Redis), 9000/9001 (MinIO), 3000 (frontend) or 8000
(backend) — those services have no published host ports and are only reachable on the
internal Docker networks.

```bash
# ufw example
sudo ufw allow OpenSSH
sudo ufw allow 8080/tcp
sudo ufw enable
sudo ufw status verbose
```

If you are on a cloud provider, also open **8080/tcp** (and 22/tcp) in its Security Group
/ firewall panel.

---

## Step 5 — Verify it works

```bash
# API health
curl -f http://<VPS_IP>:8080/health

# Frontend (returns the HTML page)
curl -f -I http://<VPS_IP>:8080/

# API behind nginx
curl -f http://<VPS_IP>:8080/api/v1/auth/me -H "Authorization: Bearer <token>"
```

Expected API health response:
```json
{"status":"ok"}
```

### Create the first admin user (required — there is no registration API)

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
import asyncio
from app.database import async_session
from app.models.user import User
from app.core.security import hash_password
from uuid import uuid4

async def create():
    async with async_session() as s:
        u = User(id=uuid4(), email='admin@example.com', name='Admin',
                 password_hash=hash_password('ChangeMe123!'),
                 language='en', timezone='UTC', status='active')
        s.add(u)
        await s.commit()
        print('User created: admin@example.com')

asyncio.run(create())
"
```

Then log in to confirm auth works:
```bash
curl -X POST http://<VPS_IP>:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'
```

After logging in on the dashboard, create your company — this auto-seeds the default
chart of accounts.

---

## Step 6 — View logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# A single service (backend, celery-worker, frontend, nginx, postgres, redis, minio,
# telegram-poll when the profile is enabled)
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f celery-worker
docker compose -f docker-compose.prod.yml --profile telegram-poll logs -f telegram-poll

# Service status / health
docker compose -f docker-compose.prod.yml ps
```

---

## Step 7 — Redeploy after a code update

```bash
git pull
docker compose -f docker-compose.prod.yml up --build -d
# If you use the Telegram polling worker, add its profile:
# docker compose -f docker-compose.prod.yml --profile telegram-poll up --build -d
docker compose -f docker-compose.prod.yml ps
curl -f http://<VPS_IP>:8080/health
```

If a new migration was added in the update, run it first:

```bash
git pull
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up --build -d
```

---

## Architecture (IP-based)

```
Internet ── http://<VPS_IP>:8080 ──► nginx ──► frontend (3000, internal)
                                └──► backend API (8000, internal)
                                      ├── celery-worker (internal)
                                      ├── telegram-poll (optional, internal)
                                      ├── PostgreSQL (internal)
                                      ├── Redis (internal)
                                      └── MinIO (internal object storage)
```

Only nginx publishes a host port (`NGINX_PORT`, default 8080). Everything else stays on
the internal `backend`/`frontend` networks. MinIO has no public ports; the `minio-init`
service creates the bucket on first boot.

---

## Telegram Webhook (optional)

Once you have a public reachable URL, register the webhook with the one-command script
(runs inside the backend container, reading `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`
and `PUBLIC_BASE_URL`):

```bash
docker compose -f docker-compose.prod.yml exec backend python -m app.scripts.telegram_setup
```

The webhook URL is `PUBLIC_BASE_URL + /api/v1/telegram/webhook`. Keep
`TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK=false` in production.

> Note: plain HTTP on a bare IP works for manual verification. Telegram requires a public
> HTTPS webhook URL, so the webhook can only be fully registered once a domain + SSL exist.

---

## Telegram Bot over plain HTTP (long-polling — recommended until HTTPS exists)

A Telegram webhook needs a **public HTTPS** endpoint that Telegram can reach. On the
IP-based HTTP deployment above, the bot silently receives nothing, so `/start` pairing and
chat messages never arrive. The fix is a **polling worker**: it calls Telegram's
`getUpdates` (outbound only — no inbound port needed) and forwards every update to the
local webhook endpoint, so the existing bot logic (pairing, extraction, drafts) is used
unchanged.

1. **Delete any existing webhook** (polling and webhook cannot run at the same time):

   ```bash
   curl -s https://api.telegram.org/bot<TOKEN>/deleteWebhook
   ```

2. In `.env`, confirm the bot variables are set:

   ```
   TELEGRAM_BOT_TOKEN=<token>
   TELEGRAM_WEBHOOK_SECRET=<random string>
   TELEGRAM_POLLING_ENABLED=true
   # defaults are fine if unset:
   # TELEGRAM_POLLING_INTERNAL_WEBHOOK_URL=http://backend:8000/api/v1/telegram/webhook
   # TELEGRAM_POLLING_OFFSET_FILE=/tmp/telegram_poll_offset
   ```

3. Start the stack **with the `telegram-poll` profile**:

   ```bash
   docker compose -f docker-compose.prod.yml --profile telegram-poll up --build -d
   ```

   (Every later `up --build -d` that touches the stack should include `--profile
   telegram-poll` so the poller is recreated too.)

4. Verify the worker is running and connected:

   ```bash
   docker compose -f docker-compose.prod.yml --profile telegram-poll ps
   docker compose -f docker-compose.prod.yml --profile telegram-poll logs -f telegram-poll
   ```

Expected logs show `Telegram polling started (offset=... webhook=...)`. If you see a
`409` conflict message, a webhook is still registered on the token — run
`deleteWebhook` again.

Then open Telegram, press **Start** on the bot, and send the pairing code from the
dashboard. The worker delivers the update to the backend and the bot replies.

> If you later add HTTPS, stop the poller (run `up -d` without `--profile telegram-poll`),
> delete any leftover polling offset is fine, and register the webhook with
> `python -m app.scripts.telegram_setup` instead. Only one of the two can be active.

---

## Backup & Restore

```bash
# Backup database to a file
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backup_20260101_120000.sql
```

Object storage and the database live in named volumes (`pgdata`, `redisdata`,
`miniodata`). Back up the database daily; copy the SQL dump off the server.

---

## Troubleshooting

**Backend won't start:**
```bash
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

**`password authentication failed for user "postgres"` (or S3 auth errors from MinIO):**
The data volumes were initialized with older credentials and changing them in `.env` does
not apply retroactively. Reset the volumes — **only safe when you have no data you need**:

```bash
docker compose -f docker-compose.prod.yml down
docker volume rm ai-cfo-manager_pgdata ai-cfo-manager_miniodata
docker compose -f docker-compose.prod.yml up --build -d
```

(If your project folder/name differs, check the exact names with `docker volume ls`.)

**Celery tasks not running:**
```bash
docker compose -f docker-compose.prod.yml logs celery-worker
docker compose -f docker-compose.prod.yml restart celery-worker
```

**Frontend calls the API but gets network/CORS errors:**
Check that `NEXT_PUBLIC_API_BASE_URL=http://<VPS_IP>:8080/api/v1` and
`CORS_ALLOWED_ORIGINS=http://<VPS_IP>:8080` match what you type in the browser. If the IP
changed, rebuild the frontend — the value is baked in at build time.

**Database connection refused:**
```bash
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U postgres
docker compose -f docker-compose.prod.yml restart postgres
```

---

## Next tasks (when you have a domain)

1. Point DNS at the VPS.
2. Configure HTTPS (Let's Encrypt/certbot or a reverse proxy).
3. Switch the bot from polling to webhooks: stop `telegram-poll` (redeploy without
   `--profile telegram-poll`), then register the webhook against the HTTPS URL with
   `python -m app.scripts.telegram_setup`.
4. Set `S3_PUBLIC_ENDPOINT_URL` to the public endpoint for presigned download links.
