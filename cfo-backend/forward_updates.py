import httpx
import os
import sys

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN environment variable not set")
    sys.exit(1)

WEBHOOK_URL = "http://localhost:8000/api/v1/telegram/webhook"

r = httpx.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=20",
    timeout=15,
)
data = r.json()
results = data.get("result", [])
print(f"Forwarding {len(results)} updates to webhook...")

for u in results:
    resp = httpx.post(
        WEBHOOK_URL,
        json=u,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    print(f"  update {u['update_id']}: {resp.status_code} {resp.json()}")

# Delete the updates from Telegram queue after forwarding
if results:
    last_id = results[-1]["update_id"]
    httpx.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_id + 1}&limit=1",
        timeout=10,
    )
    print(f"Cleared updates up to {last_id}")
