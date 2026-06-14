@echo off
title Restart SearchSleeping Bot
cd /d "%~dp0"

echo Stopping any running bot instances...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*telegram_bot*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
timeout /t 2 /nobreak >nul

echo Starting bot...
start "SearchSleeping Bot" "%~dp0with_env.bat" python telegram_bot.py
timeout /t 3 /nobreak >nul

echo Verifying...
powershell -Command "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*telegram_bot*' }; if ($p) { Write-Host ('Bot started. PID: ' + $p.ProcessId) } else { Write-Host 'Bot did not start!' }"
echo Done.
