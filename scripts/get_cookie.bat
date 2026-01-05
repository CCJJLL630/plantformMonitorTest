@echo off
chcp 65001 >nul
title Cookie获取工具

echo ============================================================
echo Cookie获取工具
echo ============================================================
echo.

REM 检查是否在虚拟环境中
if exist "%~dp0..\venv\Scripts\python.exe" (
    echo 使用虚拟环境中的Python...
    "%~dp0..\venv\Scripts\python.exe" "%~dp0get_cookie.py"
) else (
    echo 使用系统Python...
    python "%~dp0get_cookie.py"
)

echo.
echo ============================================================
pause
