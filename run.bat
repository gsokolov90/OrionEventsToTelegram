@echo off
chcp 65001 > nul
title OrionEventsToTelegram - Monitoring URV

echo.
echo ========================================
echo   OrionEventsToTelegram - Run
echo ========================================
echo.

REM Check if virtual environment exists
if not exist .venv (
    echo [ERROR] Virtual environment not found!
    echo [INFO] Run setup.bat for installation
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist .env (
    echo [ERROR] .env file not found!
    echo [INFO] Run setup.bat for configuration
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [INFO] Starting application...
echo [INFO] Press Ctrl+C to stop
echo.

REM Run the application
python main.py

echo.
echo [INFO] Application stopped
pause 