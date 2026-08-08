# Session Summary

## Goal
Implement dashboard-based Telegram bot setup (user enters bot username + token manually on the website, stored encrypted in DB instead of env-only), fix all failing GitHub Actions checks, and deploy to local + production.

## Status
**FEATURE COMPLETE + DEPLOYED LOCALLY + PUSHED to wuzzify/main (eb2ecb8 + dep fix commit)**

## Latest: python-jose → PyJWT swap (ecdsa vuln fixed)
- **Problem**: `pip-audit` found `ecdsa 0.19.2` / PYSEC-2026-1325 (Minerva timing attack) — no upstream fix exists (python-ecdsa treats side-channels out of scope). CI `dependency-audit` job would fail with exit 1.
- **Fix (root cause removal)**: replaced `python-jose[cryptography]>=3.3.0` with `pyjwt[crypto]>=2.8.0` in `cfo-backend/pyproject.toml`. PyJWT does not depend on `ecdsa`.
- Code changes (3 files, HS256 usage identical API):
  - `cfo-backend/app/services/auth.py`: `from jose import jwt` → `import jwt`
  - `cfo-backend/app/dependencies.py`: `from jose import JWTError` → `from jwt import InvalidTokenError`; `except JWTError` → `except InvalidTokenError`
  - `cfo-backend/app/api/v1/auth.py`: same exception swap
- **Verification** (all local, matching CI commands):
  - Test container rebuilt → `ecdsa` gone, PyJWT 2.13.0 present
  - Full suite: **221 passed** (1 warning: pre-existing passlib `crypt` deprecation)
  - Ruff scoped as CI (`ruff check app/ tests/` + `ruff format --check app/ tests/`): clean (143 files) — note host ruff 0.16.0 flags 44 import-sort issues in `alembic/` but CI never checks that dir
  - `pip-audit -r <(pip freeze)` → **No known vulnerabilities found**
  - Both `Dockerfile.prod` builds OK; prod backend smoke: PyJWT 2.13.0, ecdsa absent, token create/decode + app imports work
  - **Bonus**: PyJWT emits `InsecureKeyLengthWarning` for test HS256 keys <32 bytes → lengthened test-only `SECRET_KEY` in `docker-compose.test.yml` and `.github/workflows/tests.yml` (both single-use, not referenced elsewhere)

## Local Re-verification (after PyJWT swap, ccaa0b4)
- Rebuilt local stack (`up -d --build backend celery-worker frontend`) → all healthy; running backend reports PyJWT 2.13.0, ecdsa absent
- DB at alembic 008 (head); `telegram_bot_config` empty at start
- **Gotcha found & fixed**: after rebuilding/recreating `backend`, nginx kept the OLD cached upstream IP (`172.23.0.4`) → 502 on /health and /api. Fix: `docker compose ... restart nginx` (re-resolves upstream). **Important for server deploy: restart nginx after rebuilding backend** (or include it in the `up` command), else the app 502s.
- E2E via nginx :8090 (all exercised the new PyJWT code path):
  - `GET /health` → 200
  - login `verify-e2e@wuzzify.ai` → access+refresh tokens (187/188 chars); `GET /auth/me` → 200
  - `GET bot-config` unconfigured → configured=True (env fallback), username=Yourchatgptmostafabot
  - `PUT bot-config` with real token → 200 verified_username=Yourchatgptmostafabot (real getMe)
  - `POST /companies` → created "Verify Co"; `POST telegram/connect` → pairing_link `https://t.me/Yourchatgptmostafabot?start=...` (pending_chat_id)
  - Frontend :8090 → 200
  - DB: token stored Fernet-encrypted (`gAAAAA...`), webhook_secret auto-generated
- Cleanup: deleted all throwaway rows (pairing, connection, 9 accounts, member, 5 audit logs, bot-config, company, user) → DB back to baseline: 2 users, 2 companies, 2 connections, 0 members, 0 bot-config (pairings=9 are pre-existing from earlier local testing, left alone)

## Constraints & Preferences
- Push to `wuzzify` (Wuzzify-Traniers/ai-cfo-manager) only; never touch archived `origin` (personal `mostafaahmed-eng/cfo-ai-accounting`, tracking `main`)
- No SSH/server access; user deploys manually from `root@vmi3475439:~/ai-cfo-manager`
- Never commit `backup_pre_prod_prep_20260802_183811.sql` (intentionally untracked)
- Telegram webhook is impossible on production: `http://cfo.crypking.com:8080` is plain HTTP (no TLS); Cloudflare 443 serves a *different* app → production must use the `telegram-poll` service, not webhook/`telegram_setup`
- `docker-compose.prod.override.yml` is local-only (gitignored) — does not exist on server (user's `-f` command there fails)
- Only one poller may run per bot (Telegram 409 conflict) — local poller stays STOPPED while server poller runs
- User-facing UX must be simple: enter token + username from the website, pairing then works
- Keep all backend tests passing (now 221); ruff format/check clean
- Local stack uses `.env` values: bot token `8516711736:AAEGZdnZgy5EX7Ww-m1iYTNsBmQ4R7yLc80` (@Yourchatgptmostafabot), valid ENCRYPTION_KEY Fernet key

## What Was Done This Session (feature completion)
1. **Fixed PUT endpoint**: auto-generates a webhook secret (secrets.token_urlsafe(32)) on save when none exists, so a fully DB-configured bot works with NO TELEGRAM_* env values; keeps existing secret on re-save; imports `secrets`
2. **Bot Setup card UX**: Connect button disabled with amber hint "Set up the bot above first" when bot not configured
3. **Added 7 integration tests** (`tests/integration/test_telegram_bot_config.py`):
   - auth required; unconfigured GET; invalid token → 422; valid PUT+GET roundtrip (encryption verified via `config.bot_token`); manual username kept; connect uses stored username; webhook verifies stored secret (200/403)
   - Async fakes for `_telegram_get_me`; autouse `_stub_fernet` fixture with a fixed valid Fernet key (CI's ENCRYPTION_KEY `test_encryption_key_for_ci_only!!` is not a valid Fernet key)
4. **Fixed existing test**: `fake_download` in `test_telegram_photo_uses_shared_document_intake` now accepts `token=None` (download_file signature changed)
5. **Ruff**: formatted 3 files, fixed import sort in integrations.py → `ruff format --check` + `ruff check` clean (143 files)
6. **Full suite**: `docker compose -f docker-compose.test.yml ... pytest` → **221 passed** (alembic 008 applied in test DB)
7. **Local deploy**:
   - Rebuilt backend + frontend images, recreated backend, celery-worker, frontend (all healthy)
   - Ran `alembic upgrade head` on local DB → 008 applied (table exists, alembic_version=008); note: an earlier duplicate-key traceback occurred but state ended consistent
   - End-to-end verification script inside backend container: GET unconfigured 200 (env fallback), PUT with real token → 200 with getMe-verified username `Yourchatgptmostafabot`, GET configured 200, CONNECT → pairing_link `https://t.me/Yourchatgptmostafabot?start=...` ✓
   - Cleaned up all throwaway rows (verify user/company/connection/pairing/audit/bot-config) → local DB back to: 2 users (Admin-1, Admin-2), 2 companies ("test" pending_chat_id, "Test Company"), 2 connections, 0 members, 0 bot-config rows
   - Frontend: `npm run typecheck` + `npm run lint` clean; built bundle contains bot-config + "Bot Setup" markers in settings/telegram page chunk; :8090 serves 200, /api proxied (status → 401 unauth as expected)
8. **Committed + pushed**: `eb2ecb8` "Add dashboard-managed Telegram bot credentials" → wuzzify/main `f90908a..eb2ecb8`

## Remaining / Next Steps
1. **CI re-run**: GitHub Actions previously failed at infra step (`Getting action download info` → `Service Unavailable`/timeout), unrelated to code. After this dep-fix commit is pushed, ask user to `Re-run failed jobs` from the GitHub UI once infra recovers; if any job still fails, paste the logs (repo is private, no `gh` auth locally)
2. **Production deploy** (user does this): on `root@vmi3475439:~/ai-cfo-manager`:
   - `git pull`
   - `docker compose -f docker-compose.prod.yml up -d --build backend celery-worker frontend`
   - `docker compose -f docker-compose.prod.yml restart nginx` (or `up -d nginx`) — refreshes upstream IP after backend recreate, otherwise 502s
   - `docker compose -f docker-compose.prod.yml exec backend alembic upgrade head`
   - `docker compose -f docker-compose.prod.yml --profile telegram-poll up -d telegram-poll`
   - Ensure local poller stays stopped; verify server poller logs show getUpdates 200
3. Test on production: open `http://cfo.crypking.com:8080/settings/telegram`, enter token in Bot Setup card, connect a company, pair via Telegram
4. Note: prod env still has TELEGRAM_BOT_TOKEN/USERNAME set (harmless; DB config takes precedence once saved from dashboard)

## Key Files
- `cfo-backend/app/models/telegram.py` — TelegramBotConfig (encrypted token, username, webhook_secret, updated_by, `bot_token` property via decrypt_secret)
- `cfo-backend/alembic/versions/008_add_telegram_bot_config.py` — singleton config table
- `cfo-backend/app/services/telegram_bot_config.py` — get/resolve_bot_token/resolve_bot_username/resolve_webhook_secret/save + make_session_factory + db_bot_token
- `cfo-backend/app/api/v1/integrations.py` — GET/PUT `/telegram/bot-config`, `_telegram_get_me`, connect/status resolve DB-first; auto webhook secret
- `cfo-backend/app/api/v1/telegram.py` — async DB-resolved webhook secret check; download_file uses resolved token
- `cfo-backend/app/services/telegram_polling.py` — per-cycle credential reload; only webhook URL env-required
- `cfo-backend/app/tasks/telegram_responses.py` — rewritten: DB token per task
- `cfo-dashboard/src/app/settings/telegram/page.tsx` — Bot Setup card (token+username, getMe-verified username, error display) + Connect disabled hint
- `cfo-dashboard/src/lib/types.ts` / `api-client.ts` — TelegramBotConfig; bot-config in NON_COMPANY_PREFIXES

## Git History (main)
- `ccaa0b4` Replace python-jose with PyJWT to remove vulnerable ecdsa dependency (pushed wuzzify)
- `eb2ecb8` Add dashboard-managed Telegram bot credentials (pushed wuzzify)
- `f90908a` Fix telegram-poll healthcheck to work without ps in image (pushed)
- `01f50fb` Apply ruff format to telegram bot message strings (pushed)
- `a3b4bfd` Improve Telegram bot messages for bare /start and invalid pairing links (pushed)
- `676dd14` Improve Telegram pairing UX with auto-poll and deep-link button
- `3f48169` Fix company-context race causing 409 on fresh login
