@echo off
:: wa_setup.bat — First-time WhatsApp QR scan setup
:: Run this ONCE to save the Baileys session before starting PM2.
::
:: What it does:
::   1. Starts whatsapp_watcher.js in --setup mode
::   2. Baileys prints QR code in this terminal window
::   3. Scan QR with WhatsApp mobile (Linked Devices)
::   4. Process exits automatically once session is saved
::   5. Verifies creds.json was created

cd /d "%~dp0"

echo.
echo [WA Setup] Starting WhatsApp QR scan...
echo [WA Setup] Scan the QR code below with WhatsApp mobile (Settings > Linked Devices)
echo [WA Setup] The process will exit automatically after a successful scan.
echo.

node whatsapp_watcher.js --setup

echo.
echo [WA Setup] Verifying session files...

if exist ".secrets\whatsapp_session\creds.json" (
    echo [WA Setup] SUCCESS — creds.json found. Session is saved.
    echo [WA Setup] You can now start PM2: pm2 start ecosystem.config.cjs
) else (
    echo [WA Setup] WARNING — creds.json NOT found.
    echo [WA Setup] The QR scan may not have completed. Run wa_setup.bat again.
)

echo.
pause
