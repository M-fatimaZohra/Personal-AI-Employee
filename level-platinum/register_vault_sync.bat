@echo off
REM register_vault_sync.bat - Register vault sync with Windows Task Scheduler
REM Run this once to set up automatic vault sync every 2 minutes

echo Registering vault sync task with Windows Task Scheduler...
echo.

schtasks /create /tn "Platinum-Vault-Sync" /tr "%~dp0vault_sync.bat" /sc minute /mo 2 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Vault sync task registered successfully
    echo Task will run every 2 minutes
    echo.
    echo To verify: schtasks /query /tn "Platinum-Vault-Sync"
    echo To delete: schtasks /delete /tn "Platinum-Vault-Sync" /f
) else (
    echo.
    echo ERROR: Failed to register task
    echo Make sure you run this as Administrator
)

pause
