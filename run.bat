@echo off
REM SalesOps AI Assistant - Windows Quick Start Script

echo ================================================
echo SalesOps AI Assistant - Starting...
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9 or higher from python.org
    pause
    exit /b 1
)

echo [OK] Python found
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

REM Install dependencies
if exist "requirements.txt" (
    echo Installing dependencies...
    pip install -r requirements.txt >nul 2>&1
    echo [OK] Dependencies installed
    echo.
) else (
    echo ERROR: requirements.txt not found
    pause
    exit /b 1
)

REM Check for .env file
if not exist ".env" (
    echo WARNING: .env file not found
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [OK] Created .env from template
        echo.
        echo IMPORTANT: Please update .env with your credentials before running
        echo Press any key to exit...
        pause >nul
        exit /b 1
    )
)

REM Check for service account
if not exist "service_account.json" (
    echo WARNING: service_account.json not found
    echo CRM features will be disabled
    echo.
)

REM Run the application
echo ================================================
echo Starting Streamlit application...
echo ================================================
echo.

streamlit run app.py

pause