@echo off
chcp 65001 > nul
echo ========================================
echo OrionEventsToTelegram - Setup
echo ========================================
echo.

REM Check Python availability
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.8+ and try again.
    pause
    exit /b 1
)

echo [INFO] Python found
python --version

echo.
echo [INFO] Creating virtual environment...
if exist .venv (
    echo [INFO] Virtual environment already exists
) else (
    python -m venv .venv
    echo [SUCCESS] Virtual environment created
)

echo.
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [INFO] Updating pip...
python -m pip install --upgrade pip

echo.
echo [INFO] Installing dependencies...
pip install -r requirements.txt

echo.
echo [INFO] Checking .env file...
if exist .env (
    echo [SUCCESS] .env file found
) else (
    echo [WARNING] .env file not found!
    echo [INFO] Copy .env.example to .env and configure TELEGRAM_BOT_TOKEN
    copy .env.example .env > nul 2>&1
    if exist .env (
        echo [SUCCESS] .env file created from .env.example
    )
)

echo.
echo ========================================
echo [SUCCESS] Setup completed!
echo ========================================
echo.
echo To run the application use: run.bat
echo.
pause 