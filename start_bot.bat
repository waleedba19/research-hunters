@echo off
title SearchSleeping Bot
cd /d "%~dp0"
call with_env.bat python telegram_bot.py
pause
