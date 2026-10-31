@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Creating virtual environment...
python -m venv .venv || goto err
echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -i https://mirrors.huaweicloud.com/repository/pypi/simple --retries 8 --timeout 90 -r requirements.txt || goto err
echo.
echo Done! Double-click "GIF去背景.bat" to start.
pause
exit /b 0

:err
echo.
echo [!] Install failed. Check your network and Python installation.
pause
