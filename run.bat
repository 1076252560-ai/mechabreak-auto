@echo off
chcp 65001 >nul
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 (
    PowerShell -Command "Start-Process '%~dpnx0' -Verb RunAs -WorkingDirectory '%~dp0'"
    exit /b
)
python main.py
pause
