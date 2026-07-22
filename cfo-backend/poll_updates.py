import httpx
import os
import sys

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN environment variable not set")
    sys.exit(1)

r = httpx.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=20",
    timeout=15,
)
data = r.json()
results = data.get("result", [])
print(f"Total updates: {len(results)}")
for u in results:
    uid = u["update_id"]
    cb = u.get("callback_query")
    msg = u.get("message")
    if cb:
        print(
            f"  {uid} CALLBACK data={cb.get('data')} from={cb['from'].get('username', '?')}"
        )
    elif msg:
        txt = msg.get("text", "")
        print(
            f"  {uid} MESSAGE text={txt[:80]} from={msg['from'].get('username', '?')}"
        )
