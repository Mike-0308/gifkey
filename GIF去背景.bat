@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto nopy
start "" ".venv\Scripts\pythonw.exe" "%~dp0app.py"
exit /b 0

:nopy
echo [!] Python environment missing. Run "install.bat" first.
pause
