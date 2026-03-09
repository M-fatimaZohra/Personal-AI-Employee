@echo off
:: Gold FTE — Weekly CEO Briefing (Sunday 9 AM)
:: Triggers fte-audit skill to generate CEO_BRIEFING_*.md in /Plans
::
:: Register with Task Scheduler:
::   schtasks /create /tn "GoldFTE-WeeklyAudit" /tr "D:\mirab_important\code\Q4_Era_of_New_AICLI\Hackathon\Hackathon2025-2026\Hackathon-0\fte-Autonomus-employ\level-gold\schedules\weekly_audit.bat" /sc weekly /d SUN /st 09:00

cd /d D:\mirab_important\code\Q4_Era_of_New_AICLI\Hackathon\Hackathon2025-2026\Hackathon-0\fte-Autonomus-employ\level-gold
ccr code -p "/fte-audit" >> AI_Employee_Vault\Logs\scheduler.log 2>&1
