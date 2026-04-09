@echo off
:: ============================================================
:: gmail_poll.bat — Single-shot Gmail poll for Task Scheduler
:: Registered by: schedules\README.md schtasks commands
:: Schedule: Every 2 minutes via Task Scheduler
:: ============================================================

setlocal

:: Resolve script location to level-silver root
set SCRIPT_DIR=%~dp0
set SILVER_DIR=%SCRIPT_DIR%..
set LOG_FILE=%SCRIPT_DIR%gmail_poll.log

:: Activate uv environment and run a single Gmail poll
echo [%DATE% %TIME%] Starting gmail_poll >> "%LOG_FILE%"

cd /d "%SILVER_DIR%"
uv run python gmail_watcher.py --once >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] gmail_poll completed OK >> "%LOG_FILE%"
) else (
    echo [%DATE% %TIME%] gmail_poll FAILED with exit code %ERRORLEVEL% >> "%LOG_FILE%"
)

endlocal
