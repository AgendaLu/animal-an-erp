@echo off
REM Web application startup script for Animal-AN ERP (Windows)

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR:~0,-1%
for /f "delims=" %%a in ("%PROJECT_ROOT%") do set PROJECT_ROOT=%%~dpa
set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%

REM Check Python
where python3 >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    if not defined PYTHON (
        where python >nul 2>nul
        if %ERRORLEVEL% NEQ 0 (
            echo [ERROR] Python not found. Please install Python 3.9+
            exit /b 1
        )
        set PYTHON=python
    )
) else (
    set PYTHON=python3
)

echo [INFO] Python found: %PYTHON%

REM Check virtual environment
if not exist "%PROJECT_ROOT%\.venv" (
    echo [INFO] Virtual environment not found. Creating...
    %PYTHON% -m venv "%PROJECT_ROOT%\.venv"
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"

REM Install dependencies
if not exist "%PROJECT_ROOT%\.venv\INSTALLED" (
    echo [INFO] Installing dependencies...
    pip install -q -e "%PROJECT_ROOT%"
    type nul > "%PROJECT_ROOT%\.venv\INSTALLED"
)

REM Get environment
if not defined ANIMAL_AN_ENV (
    set ANIMAL_AN_ENV=development
)
echo [INFO] Running in %ANIMAL_AN_ENV% environment

REM Initialize database
echo [INFO] Initializing database...
python -c "from models.database import db_manager; db_manager.init_db()"

REM Start web server
if "%ANIMAL_AN_ENV%"=="production" (
    echo [INFO] Production mode: listening on 0.0.0.0:8000
    echo [INFO] Starting FastAPI web server...
    python -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --workers 4
) else (
    echo [INFO] Development mode: auto-reload enabled
    echo [INFO] Starting FastAPI web server...
    echo [INFO] Open browser: http://127.0.0.1:8000
    echo [INFO] API docs:     http://127.0.0.1:8000/api/docs
    python -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload
)
