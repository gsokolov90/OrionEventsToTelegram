@echo off
chcp 65001 > nul
echo ========================================
echo OrionEventsToTelegram - Update
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
echo [INFO] Updating pip...
python -m pip install --upgrade pip

echo.
echo [INFO] Updating dependencies...
pip install -r requirements.txt --upgrade

echo.
echo [INFO] Clearing pip cache...
pip cache purge

echo.
echo ========================================
echo [SUCCESS] Update completed!
echo ========================================
echo.
pause 