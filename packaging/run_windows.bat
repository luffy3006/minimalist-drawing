@echo off
setlocal enabledelayedexpansion
title Minimalist Drawing
cd /d "%~dp0\.."

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in your PATH. Please install Python 3.10+ from python.org.
    pause
    exit /b 1
)

python -c "import PyQt6" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing required dependencies (PyQt6)...
    python -m pip install -r requirements.txt
)

echo Starting Minimalist Drawing...
python main.py
if %ERRORLEVEL% neq 0 (
    echo Application exited with an error.
    pause
)
