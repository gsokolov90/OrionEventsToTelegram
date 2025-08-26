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
python fix_bom.py
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

REM Check system compatibility
echo [INFO] Checking system compatibility...
echo [INFO] Windows version:
ver
echo [INFO] System architecture:
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo [INFO] 64-bit system detected
) else (
    echo [INFO] 32-bit system detected
)
echo [INFO] Available memory:
wmic computersystem get TotalPhysicalMemory /value 2>nul | find "="
echo [INFO] Python architecture:
app\.venv\Scripts\python.exe -c "import platform; print('[INFO] Python arch:', platform.architecture()[0])" 2>nul

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
echo [INFO] Starting main.py with detailed error capture...

REM Запускаем с перенаправлением вывода для захвата всех ошибок
echo [DEBUG] Starting Python with error capture...
.venv\Scripts\python.exe -u main.py 2>&1
set "EXIT_CODE=%errorlevel%"
echo [DEBUG] Python process finished with exit code: %EXIT_CODE%

REM Если приложение упало, попробуем запустить с отладкой
if %EXIT_CODE% neq 0 (
    echo [DEBUG] ========================================
    echo [DEBUG] ATTEMPTING DEBUG MODE
    echo [DEBUG] ========================================
    echo [DEBUG] Trying to run with verbose error reporting...
    .venv\Scripts\python.exe -v main.py 2>&1
    echo [DEBUG] Verbose mode finished
    echo [DEBUG] ========================================
    
    echo [DEBUG] ========================================
    echo [DEBUG] TESTING MINIMAL PYTHON CODE
    echo [DEBUG] ========================================
    echo [DEBUG] Testing basic Python functionality...
    .venv\Scripts\python.exe -c "print('Python basic test: OK')" 2>&1
    echo [DEBUG] Testing imports...
    .venv\Scripts\python.exe -c "import sys; print('Python sys import: OK')" 2>&1
    .venv\Scripts\python.exe -c "import os; print('Python os import: OK')" 2>&1
    .venv\Scripts\python.exe -c "import telebot; print('Telebot import: OK')" 2>&1
    echo [DEBUG] ========================================
)

echo.
echo [DEBUG] ========================================
echo [DEBUG] DETAILED ERROR ANALYSIS
echo [DEBUG] ========================================
echo [DEBUG] Exit code: %EXIT_CODE%
echo [DEBUG] Current time: %date% %time%
echo [DEBUG] Python version: 
.venv\Scripts\python.exe --version 2>&1
echo [DEBUG] Python path: %CD%\.venv\Scripts\python.exe
echo [DEBUG] Main file: %CD%\main.py
echo [DEBUG] Config file exists: 
if exist ..\config.ini (echo [DEBUG] YES) else (echo [DEBUG] NO)
echo [DEBUG] Database directory exists:
if exist ..\db (echo [DEBUG] YES) else (echo [DEBUG] NO)
echo [DEBUG] Log directory exists:
if exist ..\log (echo [DEBUG] YES) else (echo [DEBUG] NO)
echo [DEBUG] ========================================

cd ..

if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Application crashed with exit code %EXIT_CODE%
    echo [ERROR] Exit code -1073740940 usually means memory access violation or DLL issue
    echo [INFO] Check the error messages above for details
    echo [INFO] Common issues:
    echo [INFO] - BOM in config.ini (should be fixed automatically)
    echo [INFO] - Invalid bot token
    echo [INFO] - Missing database files
    echo [INFO] - Network connectivity issues
    echo [INFO] - Memory/DLL compatibility issues
    echo.
    echo [INFO] If the problem persists, try:
    echo [INFO] 1. Delete config.ini and run this script again
    echo [INFO] 2. Check your internet connection
    echo [INFO] 3. Verify your bot token is correct
    echo [INFO] 4. Check Windows Event Viewer for system errors
    echo [INFO] 5. Try running as Administrator
    echo.
    pause
    exit /b 1
)

echo.
echo [INFO] Application stopped normally
pause 