@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting with console window (for troubleshooting)...
".venv\Scripts\python.exe" "%~dp0app.py"
pause
