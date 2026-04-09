@echo off
REM vault_sync.bat - Windows wrapper for vault_sync.sh
REM Calls vault_sync.sh via Git Bash
REM Usage: Called by Windows Task Scheduler every 2 minutes

cd /d "%~dp0"
"C:\Program Files\Git\bin\bash.exe" scripts/vault_sync.sh >> logs/vault_sync.log 2>&1
