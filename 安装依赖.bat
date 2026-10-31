@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto nopy

echo [1/2] 创建运行环境 .venv ...
python -m venv .venv || goto err

echo [2/2] 安装依赖（联网下载，约 80MB，慢的话等几分钟）...
".venv\Scripts\python.exe" -m pip install -i https://mirrors.huaweicloud.com/repository/pypi/simple --retries 8 --timeout 90 -r requirements.txt || goto err

echo.
echo   装好了！现在双击「GIF去背景.bat」就能用。
echo.
pause
exit /b 0

:nopy
echo.
echo   [!] 没找到 python 命令。
echo.
echo   请先安装 Python 3.10 或更高版本：https://www.python.org/downloads/
echo   安装时务必勾选 "Add python.exe to PATH"。
echo.
pause
exit /b 0

:err
echo.
echo   [!] 安装失败，多半是网络问题。
echo       换个网络重试，或者开手机热点再跑一次本文件。
echo.
pause
exit /b 0
