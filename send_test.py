"""Quick test: send /start to the bot and check the log."""
import json
import os
import time
import urllib.request
import urllib.parse

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = "6792230101"

# Send /start
data = urllib.parse.urlencode({"chat_id": chat_id, "text": "/start"}).encode()
req = urllib.request.Request(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data=data, method="POST",
)
r = json.loads(urllib.request.urlopen(req).read().decode())
print(f"send /start: ok={r.get('ok')} msg_id={r.get('result', {}).get('message_id')}")

time.sleep(2)

# Check the bot's last log lines
print()
print("=== bot_v66.log tail ===")
with open("D:/Openwork_Projects/literature-review-verifier/bot_v66.log", "r") as f:
    lines = f.readlines()
for line in lines[-10:]:
    print(line.rstrip())
