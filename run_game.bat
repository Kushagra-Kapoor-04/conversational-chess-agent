@echo off
echo Starting Chess Agent...
echo.

REM Check if python is in path
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b
)

REM Optional: Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
   call venv\Scripts\activate.bat
)

REM Run main script
python main.py %*

if %errorlevel% neq 0 (
    echo.
    echo Game exited with error code %errorlevel%.
    pause
)
