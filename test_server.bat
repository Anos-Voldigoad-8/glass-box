@echo off
echo Starting server...
cd /d C:\Projects\New folder\server
start "" cmd /k python -m server.app
timeout /t 3 >nul
echo Testing server...
curl -s http://localhost:8000/health
echo.
echo Test complete.