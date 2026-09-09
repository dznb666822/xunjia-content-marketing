@echo off
title DouYin_Spider - Start All Services
cd /d "%~dp0"

echo ==============================================
echo    DouYin_Spider - Start All Services
echo ==============================================
echo.

echo [1/4] Starting Web Console ...  http://127.0.0.1:5000
start "WebConsole-5000" cmd /k "python web_server.py"
timeout /t 2 /nobreak >nul

echo [2/4] Starting Live Monitor ...
start "LiveMonitor" cmd /k "python dy_live/server.py"
timeout /t 2 /nobreak >nul

echo [3/4] Starting Campaign Agent ...  http://127.0.0.1:8686
start "CampaignAgent-8686" cmd /k "campaign_creator\.venv\Scripts\python.exe campaign_creator\web\server.py"
timeout /t 2 /nobreak >nul

echo [4/4] Starting DM Receiver ...
start "DMReceiver" cmd /k "python dy_apis/douyin_recv_msg.py"

echo.
echo All services started. Close each window to stop its service.
echo   - Live monitor default live_id=432433667143 (dy_live/server.py line 178)
echo   - DM receiver needs valid DY_COOKIES in .env
echo.
pause
