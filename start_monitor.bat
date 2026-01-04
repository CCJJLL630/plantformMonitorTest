@echo off
chcp 65001 >nul
echo ========================================
echo 价格监控程序启动
echo ========================================
echo.

REM 激活conda环境（如果需要）
REM call conda activate base

REM 运行监控程序
python main.py

pause
