@echo off
chcp 65001 > nul
title ImpulseCatcher v5 - global production mode

cd /d "%~dp0"

for /d /r %%i in (__pycache__) do if exist "%%i" rmdir /s /q "%%i"

if not exist hft_env (
    echo [INFO] Virtual environment not found. Creating hft_env...
    python -m venv hft_env
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Make sure Python is installed and added to PATH!
        pause
        exit /b
    )
    echo [INFO] Installing requirements...
    call hft_env\Scripts\activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call hft_env\Scripts\activate
)

if not exist config.json (
    echo [WARNING] config.json is missing!
    echo [WARNING] Please create config.json from config.example.json and insert your Bybit API keys.
    pause
    exit /b
)

echo [SUCCESS] Starting main.py...
python -B main.py
pause
