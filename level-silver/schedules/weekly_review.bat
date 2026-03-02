@echo off
:: ============================================================
:: weekly_review.bat — Weekly LinkedIn draft + review trigger
:: Registered by: schedules\README.md schtasks commands
:: Schedule: Every Sunday at 09:00 AM via Task Scheduler
:: ============================================================

setlocal

:: Resolve script location to level-silver root
set SCRIPT_DIR=%~dp0
set SILVER_DIR=%SCRIPT_DIR%..
set LOG_FILE=%SCRIPT_DIR%weekly_review.log

echo [%DATE% %TIME%] Starting weekly review >> "%LOG_FILE%"

cd /d "%SILVER_DIR%"

:: Primary path: invoke fte-linkedin-draft skill via Claude CLI
where claude >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Invoking /fte-linkedin-draft via claude CLI >> "%LOG_FILE%"
    claude --print "/fte-linkedin-draft" >> "%LOG_FILE%" 2>&1
) else (
    :: Fallback: write a trigger file the orchestrator will detect
    echo [%DATE% %TIME%] claude CLI not found — writing trigger file >> "%LOG_FILE%"
    echo type: linkedin_draft_trigger > "AI_Employee_Vault\Needs_Action\LINKEDIN_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
    echo triggered_at: %DATE% %TIME% >> "AI_Employee_Vault\Needs_Action\LINKEDIN_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
    echo skill: fte-linkedin-draft >> "AI_Employee_Vault\Needs_Action\LINKEDIN_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
)

if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] weekly_review completed OK >> "%LOG_FILE%"
) else (
    echo [%DATE% %TIME%] weekly_review FAILED with exit code %ERRORLEVEL% >> "%LOG_FILE%"
)

endlocal
