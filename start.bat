@echo off
REM Quick Start Script for Cerebellar SDC Extraction System (Windows)
REM Double-click this file to start the system

echo ============================================================
echo 🧠 Cerebellar SDC Extraction System - Quick Start
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed
    echo Please install Python 3.8 or higher from python.org
    pause
    exit /b 1
)

echo ✅ Python found
echo.

REM Check dependencies
echo 📦 Checking dependencies...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ❌ Dependencies not installed
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        pause
        exit /b 1
    )
    echo ✅ Dependencies installed
) else (
    echo ✅ Dependencies already installed
)
echo.

REM Check API key
if "%ANTHROPIC_API_KEY%"=="" (
    echo ⚠️ ANTHROPIC_API_KEY not set
    echo.
    echo Please set your API key:
    echo   set ANTHROPIC_API_KEY=your-key-here
    echo.
    echo Or create a .env file with:
    echo   ANTHROPIC_API_KEY=your-key-here
    echo.
    set /p continue="Continue anyway? (Mock data only) [y/N]: "
    if /i not "%continue%"=="y" exit /b 1
) else (
    echo ✅ API key found
)
echo.

echo 🚀 Starting system...
echo.
echo 📡 Starting API server on http://localhost:5000
echo.
echo Opening browser in 3 seconds...
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

REM Open browser after delay
timeout /t 3 /nobreak >nul
start "" "cerebellar_extraction_pro.html"

REM Start API server
python api_server.py

pause
