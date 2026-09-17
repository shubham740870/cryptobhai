"""Channel STORY post try (daily views boost). Fail = silently skip."""
import glob
import os

import requests

BOT = os.environ.get("TELEGRAM_TOKEN", "")
CHAT = os.environ.get("CHANNEL_ID", "")
CAP = ("\\U0001f947 FREE Gold/Silver/FX/NSE/Crypto signals \\u2014 AI tracked, "
       "win/loss proof public. Join: t.me/caporatetrader")

cands = sorted(glob.glob("data/reports/charts/*.png"),
               key=os.path.getmtime, reverse=True)
img = cands[0] if cands else "channel_logo.png"
if not os.path.exists(img):
    raise SystemExit(0)
try:
    r = requests.post(
        f"https://api.telegram.org/bot{BOT}/postStory",
        files={"img": open(img, "rb")},
        data={"chat_id": CH,
              "content": '{"type":"photo","photo":"attach://img"}',
              "caption": CAP, "active_period": "43200"},
        timeout=30)
    print("story:", r.status_code, r.text[:200])
except Exception as ex:
    print("story skip:", ex)
