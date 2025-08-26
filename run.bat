@echo off
chcp 65001 > nul
title OrionEventsToTelegram - Monitoring URV

echo.
echo ========================================
echo   OrionEventsToTelegram - Run
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo [INFO] Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [INFO] Python found: 
python --version

REM Create app directory if it doesn't exist
if not exist app (
    mkdir app
    echo [INFO] Created app directory
)

REM Create virtual environment if it doesn't exist
if not exist app\.venv (
    echo [INFO] Creating virtual environment...
    cd app
    python -m venv .venv
    cd ..
    echo [SUCCESS] Virtual environment created
) else (
    echo [INFO] Virtual environment found
)

REM Create db directory if it doesn't exist
if not exist db (
    mkdir db
    echo [INFO] Created db directory
)

REM Create config.ini if it doesn't exist
if not exist config.ini (
    echo [INFO] Creating config.ini...
    echo [Telegram] > config.ini
    echo bot_token = your_telegram_bot_token_here >> config.ini
    echo. >> config.ini
    echo [Paths] >> config.ini
    echo authorized_users_file = db/authorized_users.txt >> config.ini
    echo user_filters_file = db/user_filters.txt >> config.ini
    echo [SUCCESS] config.ini created
    echo [INFO] Please edit config.ini and set your Telegram bot token
    echo [INFO] Then run this script again
    pause
    exit /b 1
)

REM Check if config.ini has default token
findstr /C:"your_telegram_bot_token_here" config.ini >nul
if not errorlevel 1 (
    echo [ERROR] Please configure your Telegram bot token in config.ini
    echo [INFO] Replace "your_telegram_bot_token_here" with your actual token
    pause
    exit /b 1
)

REM Check for BOM in config.ini and fix if needed
echo [INFO] Checking config.ini for encoding issues...
python fix_bom_simple.py
if errorlevel 1 (
    echo [WARNING] Could not check config.ini encoding, continuing...
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call app\.venv\Scripts\activate.bat

REM Check if requirements.txt exists
if not exist app\requirements.txt (
    echo [ERROR] requirements.txt not found in app directory!
    pause
    exit /b 1
)

REM Check if main.py exists
if not exist app\main.py (
    echo [ERROR] main.py not found in app directory!
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist app\.venv\Scripts\python.exe (
    echo [ERROR] Python not found in virtual environment!
    echo [INFO] Expected path: app\.venv\Scripts\python.exe
    pause
    exit /b 1
)



REM Check if packages are installed and up to date
echo [INFO] Checking dependencies...
cd app

REM Get current requirements hash
for /f "delims=" %%i in ('certutil -hashfile requirements.txt MD5 2^>nul') do set "REQ_HASH=%%i"
set "REQ_HASH=%REQ_HASH:~0,32%"

REM Check if .venv/requirements_hash.txt exists and matches
if exist .venv\requirements_hash.txt (
    set /p "CACHED_HASH=" < .venv\requirements_hash.txt
    if "%CACHED_HASH%"=="%REQ_HASH%" (
        echo [INFO] Dependencies are up to date
    ) else (
        echo [INFO] Requirements changed, updating dependencies...
        pip install -r requirements.txt --upgrade
        echo %REQ_HASH% > .venv\requirements_hash.txt
        echo [SUCCESS] Dependencies updated
    )
) else (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    echo %REQ_HASH% > .venv\requirements_hash.txt
    echo [SUCCESS] Dependencies installed
)

cd ..

echo.
echo [INFO] Starting application...
echo [INFO] Press Ctrl+C to stop
echo.

REM Run the application with error handling
echo [INFO] Current directory: %CD%
echo [INFO] Starting from app directory...
cd app
echo [INFO] App directory: %CD%
echo [INFO] Python path: .venv\Scripts\python.exe
echo [INFO] Main file: main.py
echo [INFO] Testing Python in virtual environment...
.venv\Scripts\python.exe --version
echo [INFO] Starting main.py...

REM Запускаем приложение
.venv\Scripts\python.exe main.py
set "EXIT_CODE=%errorlevel%"



cd ..

if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Application crashed with exit code %EXIT_CODE%
    echo [INFO] Check the error messages above for details
    echo [INFO] Common issues:
    echo [INFO] - BOM in config.ini (should be fixed automatically)
    echo [INFO] - Invalid bot token
    echo [INFO] - Missing database files
    echo [INFO] - Network connectivity issues
    echo.
    echo [INFO] If the problem persists, try:
    echo [INFO] 1. Delete config.ini and run this script again
    echo [INFO] 2. Check your internet connection
    echo [INFO] 3. Verify your bot token is correct
    echo.
    pause
    exit /b 1
)

echo.
echo [INFO] Application stopped normally
pause 