# Register bot to auto-start when you log into Windows
# Run: powershell -ExecutionPolicy Bypass -File register_startup.ps1

$scriptPath = Join-Path $PSScriptRoot "run_forever.bat"
$shortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\SearchSleepingBot.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $scriptPath
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = "SearchSleeping Telegram Bot - Auto-starts on login"
$shortcut.WindowStyle = 7  # Minimized
$shortcut.Save()

Write-Host "✅ Startup shortcut created at: $shortcutPath"
Write-Host "   The bot will auto-start when you log into Windows."

# Also verify bot is running now
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*telegram_bot*' }
if (-not $running) {
    Write-Host "⚠ Bot is not running. Starting now..."
    Start-Process -FilePath $scriptPath -WindowStyle Minimized
    Write-Host "✅ Bot started."
} else {
    Write-Host "✅ Bot is already running (PID $($running.ProcessId))."
}
