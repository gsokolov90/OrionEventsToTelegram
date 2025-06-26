@echo off
chcp 65001 > nul
echo ========================================
echo OrionEventsToTelegram - Check .env
echo ========================================
echo.

echo [INFO] Checking .env file...

if exist .env (
    echo [INFO] .env file exists
    echo [INFO] Content of .env file:
    echo ----------------------------------------
    type .env
    echo ----------------------------------------
) else (
    echo [WARNING] .env file not found!
)

echo.
echo [INFO] Creating/updating .env file...
echo TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here > .env

echo.
echo [SUCCESS] .env file created/updated
echo [INFO] Please edit .env file and replace 'your_telegram_bot_token_here' with your actual token
echo.
echo [INFO] Current .env content:
echo ----------------------------------------
type .env
echo ----------------------------------------
echo.
echo [INFO] To edit .env file, you can:
echo 1. Open it in Notepad: notepad .env
echo 2. Or edit manually and replace the token
echo.
pause 