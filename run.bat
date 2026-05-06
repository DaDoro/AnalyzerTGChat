@echo off
setlocal

cd /d "%~dp0"

REM === 1. Create .env from template if missing ===
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo.
        echo .env created from .env.example.
        echo Open .env, fill in API_ID, API_HASH and ANTHROPIC_API_KEY,
        echo then run run.bat again.
        echo.
        pause
        exit /b 0
    ) else (
        echo .env.example not found - installation is broken.
        pause
        exit /b 1
    )
)

REM === 2. Create venv if missing ===
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create venv. Please install Python 3.10+.
        pause
        exit /b 1
    )
)

REM === 3. Activate venv ===
call ".venv\Scripts\activate.bat"

REM Install dependencies if anthropic is not yet installed
if not exist ".venv\Lib\site-packages\anthropic" (
    echo Installing dependencies...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM === 4. Switch console to UTF-8 for Python output, then run ===
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

python main.py

echo.
pause
endlocal
