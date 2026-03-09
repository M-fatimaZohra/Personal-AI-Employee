@echo off
:: ============================================================
:: morning_briefing.bat — Daily morning briefing trigger
:: Registered by: schedules\README.md schtasks commands
:: Schedule: Daily at 08:00 AM via Task Scheduler
:: ============================================================

setlocal

:: Resolve script location to level-silver root
set SCRIPT_DIR=%~dp0
set SILVER_DIR=%SCRIPT_DIR%..
set LOG_FILE=%SCRIPT_DIR%morning_briefing.log

echo [%DATE% %TIME%] Starting morning briefing >> "%LOG_FILE%"

cd /d "%SILVER_DIR%"

:: Primary path: invoke fte-briefing skill via CCR Code CLI
where ccr >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Invoking /fte-briefing via ccr code CLI >> "%LOG_FILE%"
    ccr code -p "/fte-briefing" >> "%LOG_FILE%" 2>&1
) else (
    :: Fallback: write a trigger file the orchestrator will detect
    echo [%DATE% %TIME%] ccr code CLI not found — writing trigger file >> "%LOG_FILE%"
    echo type: briefing_trigger > "AI_Employee_Vault\Needs_Action\BRIEFING_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
    echo triggered_at: %DATE% %TIME% >> "AI_Employee_Vault\Needs_Action\BRIEFING_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
    echo skill: fte-briefing >> "AI_Employee_Vault\Needs_Action\BRIEFING_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
)

if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] morning_briefing completed OK >> "%LOG_FILE%"
) else (
    echo [%DATE% %TIME%] morning_briefing FAILED with exit code %ERRORLEVEL% >> "%LOG_FILE%"
)

endlocal
