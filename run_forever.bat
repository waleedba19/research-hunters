@echo off
title SearchSleeping Bot (Auto-Restart)
cd /d "%~dp0"
echo ========================================
echo  SearchSleeping Bot — Auto-Restart Mode
echo  Will restart automatically if it crashes
echo  Close this window to stop permanently
echo ========================================

:RESTART
echo [%date% %time%] Starting bot...

call with_env.bat python telegram_bot.py

echo [%date% %time%] Bot exited with code %ERRORLEVEL%.
if %ERRORLEVEL% EQU 0 (
    echo Bot exited cleanly. Not restarting.
    goto :END
)

echo Bot crashed or stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto :RESTART

:END
pause
