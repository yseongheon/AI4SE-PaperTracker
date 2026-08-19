@echo off
rem ============================================================
rem  AI4SE PaperTracker - one-click launcher (for research group)
rem  Double-click to start backend + frontend + open browser.
rem  Close services: close the two popup command windows.
rem  NOTE: all-ASCII text (GBK-safe on Windows cmd).
rem ============================================================
cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
    echo [ERROR] backend\.venv not found. Install deps first.
    pause
    exit /b 1
)

rem --- port 8000 already in use? (backend already running) ---
netstat -ano | findstr /c:":8000" | findstr /c:"LISTENING" >nul
if %errorlevel% equ 0 (
    echo [SKIP] Backend already running on port 8000.
    goto :frontend
)

echo Starting backend on port 8000 ...
start "AI4SE-Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

:frontend
rem --- port 5173 already in use? ---
netstat -ano | findstr /c:":5173" | findstr /c:"LISTENING" >nul
if %errorlevel% equ 0 (
    echo [SKIP] Frontend already running on port 5173.
    goto :open
)

echo Starting frontend on port 5173 ...
start "AI4SE-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:open
echo Waiting for services to be ready ...
timeout /t 8 /nobreak >nul
start http://localhost:5173

echo.
echo Opened http://localhost:5173
echo (If page not loaded yet, refresh in a few seconds.)
pause
