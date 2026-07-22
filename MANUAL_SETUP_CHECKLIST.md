# Manual Setup Checklist

Every value a human operator must obtain, generate, or configure before this project
can run. Nothing is assumed or filled in for you.

---

## Section 1 — Required before `docker compose up` will work at all

These must be set (or confirmed) before any service starts successfully.

| Variable / Item | File & path | Where to get it | Exact steps to obtain it | Required for local dev? |
|---|---|---|---|---|
| `SECRET_KEY` | `cfo-backend/.env.example` line 2 (copy to `cfo-backend/.env`) | Generate locally | `python -c "import secrets; print(secrets.token_urlsafe(64))"` — paste the output as the value. This signs JWT tokens; a leaked/insecure value means anyone can forge login tokens. | **Required** — app starts but all auth is broken without a real value |
| `ENCRYPTION_KEY` | `cfo-backend/.env.example` line 34 | Generate locally | `python -c "import secrets; print(secrets.token_urlsafe(32))"` — must be exactly 32 bytes of random data. Currently defined in `config.py` but not yet consumed by any code; set it now so it is ready when encryption logic is added. | **Required** — placeholder value is a security risk if deployed |
| `JWT_ALGORITHM` | `cfo-backend/.env.example` line 3 | Leave as-is | Value `HS256` is correct and matches the `python-jose` library usage in `app/services/auth.py:12`, `app/api/v1/auth.py:30`, and `app/dependencies.py:21`. Do not change unless you replace the JWT library. | Safe as-is |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `cfo-backend/.env.example` line 4 | Leave as-is | Value `30` means tokens expire after 30 minutes. Used in `app/services/auth.py:11` and `app/api/v1/auth.py:29`. Change only if you want shorter/longer sessions. | Safe as-is |
| `DATABASE_URL` | `cfo-backend/.env.example` line 9 | Leave as-is for Docker Compose | Value `postgresql+asyncpg://postgres:postgres@localhost:5432/cfo_db` is overridden by `docker-compose.yml` line 38 to `postgresql+asyncpg://postgres:postgres@postgres:5432/cfo_db` (note `postgres` hostname instead of `localhost`). Used by `app/database.py:7` (async engine) and `alembic/env.py:17` (migrations). | Safe as-is for Docker |
| `REDIS_URL` | `cfo-backend/.env.example` line 13 | Leave as-is for Docker Compose | Value `redis://localhost:6379/0` is overridden by `docker-compose.yml` line 39 to `redis://redis:6379/0`. Used by `app/tasks/celery_app.py:8-9` as Celery broker and result backend. | Safe as-is for Docker |
| `NEXT_PUBLIC_API_BASE_URL` | `cfo-dashboard/.env.local.example` line 1 (copy to `cfo-dashboard/.env.local`) | Leave as-is | Value `http://localhost:8000/api/v1` is correct for local Docker Compose dev. Read by `cfo-dashboard/src/lib/api-client.ts:4` as the Axios base URL. Must include the `/api/v1` suffix. | Safe as-is |
| **First user account** | No file — must be created directly in the database | Create manually in PostgreSQL | There is no user registration API endpoint (only login at `POST /api/v1/auth/login`). After `docker compose up`, create a user by running: `docker compose exec backend python -c " import asyncio from app.database import async_session, Base from app.models.user import User from uuid import uuid4 from passlib.context import CryptContext ctx = CryptContext(schemes=['bcrypt'], deprecated='auto') async def create(): async with async_session() as s: u = User(id=uuid4(), email='admin@example.com', name='Admin', password_hash=ctx.hash('changeme123'), status='active'); s.add(u); await s.commit(); print('User created: admin@example.com / changeme123') asyncio.run(create()) "`. Change the email and password to your own values. | **Required** — login endpoint returns 401 for every request without a seeded user |
| **Docker Compose env overrides** | `docker-compose.yml` lines 37-55 (backend), lines 70-87 (celery-worker) | Already configured | `docker-compose.yml` already provides all required env vars for both the `backend` and `celery-worker` services, including `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ENCRYPTION_KEY`, `OPENROUTER_*`, `S3_*`, and `TELEGRAM_*`. The `.env` file values are used only when running outside Docker. | Safe as-is |

---

## Section 2 — Required for specific features (Telegram, OpenRouter AI extraction, file storage)

These can be left as empty strings in `docker-compose.yml` / `.env` — the app will start
and all non-integration features will work. Set them only when you want that feature.

| Variable / Item | File & path | Where to get it | Exact steps to obtain it | Required for local dev? |
|---|---|---|---|---|
| `OPENROUTER_API_KEY` | `cfo-backend/.env.example` line 16 | OpenRouter dashboard | 1. Go to https://openrouter.ai/ and create an account (free tier available). 2. Navigate to https://openrouter.ai/keys and click "Create Key". 3. Copy the key (starts with `sk-or-...`). 4. Set it as `OPENROUTER_API_KEY` in your `.env` file or `docker-compose.yml`. Used by `app/services/ai_extraction.py:35` as the Bearer token in the Authorization header when calling the OpenRouter chat completions API. Without this, any call to `POST /api/v1/ai-extraction/{inbox_item_id}/extract` will fail with a 401 from OpenRouter. | **Optional** — AI extraction is not required for the app to start or for manual expense entry |
| `OPENROUTER_MODEL` | `cfo-backend/.env.example` line 17 | OpenRouter dashboard | Default `google/gemini-2.0-flash-001` is a free-tier model on OpenRouter. To use a different model, browse https://openrouter.ai/models, pick one, and use its full ID (e.g. `anthropic/claude-3-haiku`). Used by `app/services/ai_extraction.py:39` in the API request body. **Note:** The model name is also hardcoded as `"gemini-2.0-flash-001"` in `app/api/v1/ai_extraction.py:34` for the database record — changing the env var alone will not update that audit field. | Safe as-is for free-tier testing |
| `OPENROUTER_BASE_URL` | `cfo-backend/.env.example` line 18 | Leave as-is | Value `https://openrouter.ai/api/v1` is the correct OpenRouter API base URL. Used by `app/services/ai_extraction.py:33` to construct the full endpoint `{BASE_URL}/chat/completions`. | Safe as-is |
| `TELEGRAM_BOT_TOKEN` | `cfo-backend/.env.example` line 21 | Telegram — @BotFather | 1. Open Telegram and search for `@BotFather`. 2. Send `/newbot`. 3. Follow prompts: choose a display name (e.g. "CFO Manager Bot") and a username (must end in `bot`, e.g. `mycompany_cfo_bot`). 4. BotFather will reply with a token like `123456789:ABCdefGHIjklMNOpqr...` — copy it. 5. Set it as `TELEGRAM_BOT_TOKEN`. **Note:** This variable is defined in `config.py:19` but is currently **not consumed** by any code — no Telegram `sendMessage` or `getUpdates` calls exist yet. Set it now so it is ready when Telegram sending is implemented. | **Optional** — Telegram integration is not needed for core features |
| `TELEGRAM_WEBHOOK_SECRET` | `cfo-backend/.env.example` line 22 | Generate locally | `python -c "import secrets; print(secrets.token_urlsafe(32))"` — this is a shared secret that Telegram includes in the `X-Telegram-Bot-Api-Secret-Token` header of every webhook request. The backend validates it at `app/api/v1/telegram.py:23`. Must match the secret you give to Telegram when registering the webhook (see Section 3). | **Optional** — webhook returns 403 without it (safe default) |
| `TELEGRAM_BOT_USERNAME` | `cfo-backend/.env.example` line 23 | Telegram — from @BotFather | Use the username you chose when creating the bot with @BotFather (e.g. `mycompany_cfo_bot`). Do not include the `@` prefix. Used by `app/api/v1/integrations.py:33` when storing the Telegram connection record in the database. | **Optional** — only needed when a company connects their Telegram bot |
| `S3_ENDPOINT_URL` | `cfo-backend/.env.example` line 26 | AWS S3 or Cloudflare R2 dashboard | For **AWS S3**: leave empty (boto3 defaults to `https://s3.amazonaws.com`). For **Cloudflare R2**: set to `https://<YOUR_ACCOUNT_ID>.r2.cloudflarestorage.com` — find your Account ID in the R2 dashboard at https://dash.cloudflare.com/ under "Account ID" in the sidebar. For **MinIO** (local): set to `http://localhost:9000`. Used by `app/core/storage.py:11` as the `endpoint_url` for the boto3 S3 client. | **Optional** — document upload will fail without S3, but all other features work |
| `S3_ACCESS_KEY_ID` | `cfo-backend/.env.example` line 27 | AWS IAM console or Cloudflare R2 API tokens | **AWS**: https://console.aws.amazon.com/iam/ → Users → Create user → Attach `AmazonS3FullAccess` policy → Security credentials → Create access key. **Cloudflare R2**: https://dash.cloudflare.com/ → R2 → Manage R2 API tokens → Create API token → Permissions: Object Read & Write → Copy the Access Key ID. Used by `app/core/storage.py:12`. | **Optional** |
| `S3_SECRET_ACCESS_KEY` | `cfo-backend/.env.example` line 28 | Same source as `S3_ACCESS_KEY_ID` | This is the secret key shown once when you create the access key above. If you lost it, create a new access key pair. Used by `app/core/storage.py:13`. | **Optional** |
| `S3_BUCKET_NAME` | `cfo-backend/.env.example` line 29 | AWS S3 console or Cloudflare R2 dashboard | **AWS**: https://console.aws.amazon.com/s3/ → Create bucket → choose a globally unique name (e.g. `mycompany-cfo-documents`). **Cloudflare R2**: https://dash.cloudflare.com/ → R2 → Create bucket → enter a name. Set `S3_BUCKET_NAME` to that name. Used by `app/core/storage.py:16` as the target bucket for all upload/delete/presign operations. Default `cfo-documents` is fine if you create a bucket with that name. | **Optional** |
| `S3_REGION` | `cfo-backend/.env.example` line 30 | AWS S3 console | For AWS: the region of your bucket (e.g. `us-east-1`, `eu-west-1`). For Cloudflare R2: leave as `auto` (R2 is globally routed). For MinIO: leave as `auto`. Used by `app/core/storage.py:14` as `region_name` for the boto3 client. | Safe as-is (`auto`) for Cloudflare R2 and MinIO |

---

## Section 3 — One-time external setup steps (not env vars — actions to take)

These are things you must configure in an external service, not just "get an API key".

| Variable / Item | File & path | Where to get it | Exact steps to obtain it | Required for local dev? |
|---|---|---|---|---|
| **Register Telegram webhook URL** | `cfo-backend/app/api/v1/telegram.py` line 17 (endpoint: `POST /api/v1/telegram/webhook`) | Telegram Bot API | After the backend is running and `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` are set, register the webhook by calling: `curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" -H "Content-Type: application/json" -d '{"url": "https://<YOUR_PUBLIC_URL>/api/v1/telegram/webhook", "secret_token": "<YOUR_TELEGRAM_WEBHOOK_SECRET>"}'`. For local development you will need a tunnel (e.g. `ngrok http 8000`) to expose the backend publicly, since Telegram must reach your server over HTTPS. Without this, Telegram messages will not reach the webhook. **Note:** There is no webhook registration logic in the codebase — you must call the Telegram API manually. | **Optional** |
| **Create initial user account** | No file — database operation | PostgreSQL (inside Docker) | As described in Section 1, there is no `/api/v1/auth/register` endpoint. The only way to create a user is to insert a row directly into the `users` table with a bcrypt-hashed password. The login endpoint at `POST /api/v1/auth/login` validates `email` + `password` against `users.password_hash` and `users.status == "active"` (`app/api/v1/auth.py:18-27`). | **Required** |
| **Create company + default chart of accounts** | `cfo-backend/app/api/v1/companies.py` lines 16-26, 43-49 | API call after user is created | After logging in, call `POST /api/v1/companies` with a JSON body like `{"name": "My Company", "country_code": "US", "base_currency": "USD", "fiscal_year_start": 1, "timezone": "UTC"}`. This automatically creates the user as OWNER and seeds 9 default accounts (Cash, Bank, AR, AP, Revenue, Hosting/Software/Marketing/Payroll Expenses). No manual database insert is needed for this step. | **Required** (for any feature that creates transactions) |
| **Create S3 / R2 bucket** | `cfo-backend/app/core/storage.py` line 16 | AWS S3 or Cloudflare R2 | See the `S3_BUCKET_NAME` row in Section 2 for instructions. The bucket must exist before any document upload — `boto3` does not auto-create buckets. | **Optional** |
| **CORS origins for production** | `cfo-backend/app/main.py` line 13 | Code change | Currently hardcoded to `allow_origins=["*"]` (accepts requests from any origin). Before deploying to production, change this to a specific list of allowed origins, e.g. `["https://yourdomain.com"]`. For local Docker Compose dev the wildcard is fine. | Safe as-is for local dev |

---

## Summary of all env vars and their disposition

| Variable | Section | Disposition |
|---|---|---|
| `SECRET_KEY` | 1 | **Generate locally** — `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ENCRYPTION_KEY` | 1 | **Generate locally** — `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `JWT_ALGORITHM` | 1 | Safe as-is (`HS256`) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 1 | Safe as-is (`30`) |
| `DATABASE_URL` | 1 | Safe as-is for Docker (overridden by `docker-compose.yml`) |
| `REDIS_URL` | 1 | Safe as-is for Docker (overridden by `docker-compose.yml`) |
| `NEXT_PUBLIC_API_BASE_URL` | 1 | Safe as-is (`http://localhost:8000/api/v1`) |
| `OPENROUTER_API_KEY` | 2 | Obtain from https://openrouter.ai/keys |
| `OPENROUTER_MODEL` | 2 | Safe as-is (`google/gemini-2.0-flash-001` free tier) |
| `OPENROUTER_BASE_URL` | 2 | Safe as-is (`https://openrouter.ai/api/v1`) |
| `TELEGRAM_BOT_TOKEN` | 2 | Obtain from @BotFather (currently unused in code) |
| `TELEGRAM_WEBHOOK_SECRET` | 2 | **Generate locally** — `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `TELEGRAM_BOT_USERNAME` | 2 | From @BotFather bot creation |
| `S3_ENDPOINT_URL` | 2 | AWS/R2/MinIO dashboard (or leave empty for AWS default) |
| `S3_ACCESS_KEY_ID` | 2 | AWS IAM or R2 API token dashboard |
| `S3_SECRET_ACCESS_KEY` | 2 | Same source as `S3_ACCESS_KEY_ID` |
| `S3_BUCKET_NAME` | 2 | Create in AWS S3 or R2 dashboard |
| `S3_REGION` | 2 | Safe as-is (`auto` for R2/MinIO) |
| **First user** | 1 | **Must create directly in DB** — no registration API exists |
| **Company + accounts** | 1 | API call after login — auto-seeds default chart of accounts |
| **Telegram webhook** | 3 | Manual `curl` to Telegram Bot API (needs public URL) |
| **S3 bucket** | 3 | Create in AWS/R2/MinIO dashboard |
| **CORS policy** | 3 | Code change needed for production (`app/main.py:13`) |

---

## Notes

- **`TELEGRAM_BOT_TOKEN`** is defined in `config.py:19` but is never read by any service or
  endpoint. It appears to be reserved for future Telegram `sendMessage`/`getUpdates`
  functionality. Set it now if you plan to implement Telegram sending soon.

- **`ENCRYPTION_KEY`** is defined in `config.py:22` but is never read by any service or
  endpoint. It appears to be reserved for encrypting sensitive data at rest (e.g. S3 object
  metadata, stored credentials). Set it now if you plan to implement encryption soon.

- **The model name `"gemini-2.0-flash-001"`** is hardcoded in two independent places:
  `config.py:12` (as a Settings default, overridable via env) and
  `app/api/v1/ai_extraction.py:34` (as a raw string literal for the database audit record,
  NOT overridable via env). Changing `OPENROUTER_MODEL` will affect the actual API call but
  not the stored record.

- **`alembic.ini` line 3** contains a hardcoded database URL
  (`postgresql+asyncpg://postgres:postgres@localhost:5432/cfo_db`) that cannot be overridden
  by environment variables. This is harmless because `alembic/env.py:17` overwrites it at
  runtime with `settings.DATABASE_URL`, but the `.ini` value is misleading if someone reads
  it directly.

- **`app/main.py:13`** has `allow_origins=["*"]` for CORS. This is acceptable for local
  development but must be restricted before production deployment.
