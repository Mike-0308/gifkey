@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto nopy
start "" ".venv\Scripts\pythonw.exe" "%~dp0app.py"
exit /b 0

:nopy
echo.
echo   [!] 还没有安装运行环境（第一次使用要先装一次）。
echo.
echo   请先双击运行「安装依赖.bat」，装完再双击本文件。
echo.
pause
exit /b 0
