@echo off
chcp 65001 > nul
echo ========================================
echo OrionEventsToTelegram - Fix Dependencies
echo ========================================
echo.

REM Check if virtual environment exists
if not exist .venv (
    echo [ERROR] Virtual environment not found!
    echo [INFO] Run setup.bat for installation
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [INFO] Uninstalling all packages...
pip freeze | pip uninstall -y

echo.
echo [INFO] Updating pip...
python -m pip install --upgrade pip

echo.
echo [INFO] Installing dependencies...
pip install -r requirements.txt

echo.
echo [INFO] Verifying installation...
python -c "import dotenv; print('[SUCCESS] python-dotenv imported successfully')"
python -c "import telebot; print('[SUCCESS] telebot imported successfully')"
python -c "import colorama; print('[SUCCESS] colorama imported successfully')"

echo.
echo ========================================
echo [SUCCESS] Dependencies fixed!
echo ========================================
echo.
pause 