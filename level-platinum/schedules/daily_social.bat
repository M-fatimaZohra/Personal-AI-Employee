@echo off
:: ============================================================
:: daily_social.bat — Daily social post drafting trigger
:: Registered by: schedules\README.md schtasks commands
:: Schedule: Daily at 07:00 AM via Task Scheduler
:: Drafts FB/IG/TW posts → Pending_Approval/ → user approves
:: JitterScheduler posts at random time 09:00-18:00
:: ============================================================

setlocal

:: Resolve script location to level-gold root
set SCRIPT_DIR=%~dp0
set GOLD_DIR=%SCRIPT_DIR%..
set LOG_FILE=%SCRIPT_DIR%daily_social.log

echo [%DATE% %TIME%] Starting daily social post drafting >> "%LOG_FILE%"

cd /d "%GOLD_DIR%"

:: Primary path: invoke fte-social-post skill via Claude CLI
where claude >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Invoking /fte-social-post all via claude CLI >> "%LOG_FILE%"
    claude -p "/fte-social-post all" >> "%LOG_FILE%" 2>&1
) else (
    :: Fallback: write a trigger file the orchestrator will detect
    echo [%DATE% %TIME%] claude CLI not found — writing trigger file >> "%LOG_FILE%"
    echo type: social_draft_trigger > "AI_Employee_Vault\Needs_Action\SOCIAL_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
    echo triggered_at: %DATE% %TIME% >> "AI_Employee_Vault\Needs_Action\SOCIAL_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
    echo skill: fte-social-post >> "AI_Employee_Vault\Needs_Action\SOCIAL_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
    echo arguments: all >> "AI_Employee_Vault\Needs_Action\SOCIAL_TRIGGER_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.md"
)

if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] daily_social completed OK >> "%LOG_FILE%"
) else (
    echo [%DATE% %TIME%] daily_social FAILED with exit code %ERRORLEVEL% >> "%LOG_FILE%"
)

endlocal
