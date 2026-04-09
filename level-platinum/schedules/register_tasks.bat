@echo off
set BASE=D:\mirab_important\code\Q4_Era_of_New_AICLI\Hackathon\Hackathon2025-2026\Hackathon-0\fte-Autonomus-employ\level-gold\schedules

schtasks /create /tn "GoldFTE-MorningBriefing" /tr "%BASE%\morning_briefing.bat" /sc daily /st 08:00 /f
schtasks /create /tn "GoldFTE-WeeklyAudit" /tr "%BASE%\weekly_audit.bat" /sc weekly /d SUN /st 09:00 /f
schtasks /create /tn "GoldFTE-DailySocial" /tr "%BASE%\daily_social.bat" /sc daily /st 07:00 /f

echo Done.
