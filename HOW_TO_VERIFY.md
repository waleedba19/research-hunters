# How to verify /hunt2 + Drive end-to-end on YOUR machine

## 1. Get the tokens you need

You need TWO environment variables set in PowerShell BEFORE running the bot:

```powershell
# 1. Create a Telegram bot (skip if you already have one)
#    - Open Telegram, message @BotFather
#    - Send /newbot, follow prompts
#    - Copy the token (looks like 123456:ABC-DEF...)

# 2. Get a Google OAuth refresh token (skip if you have one)
#    - See GOOGLE_OAUTH_SETUP.md in repo
#    - Or run: python oauth_flow.py --client-secrets client_secret.json
#    - Copy the refresh token (long string)

# 3. Set the env vars in your current PowerShell session:
$env:TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
$env:GOOGLE_OAUTH_REFRESH = "1//0gXx...long string...XYZ"

# Verify they are set:
echo $env:TELEGRAM_BOT_TOKEN.Substring(0,10)
echo $env:GOOGLE_OAUTH_REFRESH.Substring(0,20)
```

## 2. Start the bot

```powershell
cd D:\Openwork_Projects\literature-review-verifier
python telegram_bot.py
```

You should see:
```
[INFO] telegram_bot: Bot started. Polling...
[INFO] telegram_bot: Authorized as @your_bot_name
```

If you see errors, check the env vars.

## 3. Send /hunt2 in Telegram

Open Telegram, find your bot, send:
```
/hunt2
```

You'll get the 7-step intake. For each step, EITHER pick a button OR type your answer. To test the "skip everything except title" flow:

1. Research type: tap "🌐 General / Other" (or type `general`)
2. Title: type `machine learning in education`
3. Research questions: tap "⏭ Skip" (auto-generates 3 via ollama)
4. Year range: tap "⏭ Skip" (any)
5. Platforms: tap "⚡ Top 20 platforms"
6. Max papers: type `50` (50 papers = ~10-15 min)
7. Download PDFs: tap "✅ Yes, download PDFs"

## 4. Watch progress

You'll see:
- A "All set! Starting your hunt..." message with the config
- Progress updates every 5%: Searching [50%], Deduplicating [60%], etc.
- A "⏳ Still working..." message every 5 min
- Final delivery: PDF + XLSX + DOCX + MD + JSON + top 5 PDFs + Drive folder link

## 5. Check Drive

Open https://drive.google.com/drive/folders/1NjsBcaAb1qtRUl4d7KHNhvfm159ei2C4

You should see a NEW folder: `Literature_Review_Verifier/`
   Inside: a subfolder named after your title
   Inside that: results.json, research_report.pdf, master_database.xlsx, research_report.docx, research_report.md, and a pdfs/ folder with the downloaded PDFs

## Troubleshooting

- **"No module named telegram_bot"** — you're not in the right directory. `cd D:\Openwork_Projects\literature-review-verifier`
- **"401 Unauthorized"** — TELEGRAM_BOT_TOKEN is wrong. Re-check.
- **"Drive upload failed"** — GOOGLE_OAUTH_REFRESH is wrong or expired. Re-run oauth_flow.py.
- **Bot never responds** — check the polling logs. May need to stop + restart.
- **No PDFs downloaded** — that's fine, the red_list_count tells you which papers need manual download.
- **"ollama not running"** — the AI features (RQs, future studies) will use deterministic fallbacks. Pipeline still works.

## What's already verified

| Check | Status |
|---|---|
| 81 platforms registered | ✅ test_health.py |
| Pipeline imports + runs | ✅ test_hunt_smoke.py (in CI) |
| Drive upload logic | ✅ test_drive_integration.py (8 mocked tests) |
| 7-step intake | ✅ test_hunt_intake.py + E2E |
| PDF heavy report | ✅ test_report_pdf.py |
| Future research directions | ✅ test_future_studies.py (16 tests) |
| All health checks | ✅ 13/13 |
| Real /hunt2 with real Drive | ❌ Needs you to run with real tokens |
