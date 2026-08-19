@echo off
rem ============================================================
rem  AI4SE PaperTracker - one-click launcher (for research group)
rem  PRODUCTION: if frontend\dist exists, backend serves the site
rem    (single port 8000, LAN accessible at http://<this-ip>:8000)
rem  DEV: otherwise starts backend + vite dev server (port 5173)
rem  Close services: close the popup command windows.
rem  NOTE: all-ASCII text (GBK-safe on Windows cmd).
rem ============================================================
cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
    echo [ERROR] backend\.venv not found. Install deps first.
    pause
    exit /b 1
)

if exist frontend\dist\index.html goto :production

rem ---------------- DEV MODE (no dist) ----------------
echo [DEV] frontend\dist not found, starting dev servers...

netstat -ano | findstr /c:":8000" | findstr /c:"LISTENING" >nul
if %errorlevel% equ 0 (
    echo [SKIP] Backend already running on port 8000.
    goto :dev_frontend
)
echo Starting backend on port 8000 ...
start "AI4SE-Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:dev_frontend
netstat -ano | findstr /c:":5173" | findstr /c:"LISTENING" >nul
if %errorlevel% equ 0 (
    echo [SKIP] Frontend already running on port 5173.
    goto :open_local
)
echo Starting frontend on port 5173 ...
start "AI4SE-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --host"

:open_local
timeout /t 8 /nobreak >nul
start http://localhost:5173
echo.
echo Opened http://localhost:5173
pause
exit /b 0

rem ---------------- PRODUCTION MODE (single port 8000) ----------------
:production
echo [PROD] Serving built frontend via backend on port 8000.

netstat -ano | findstr /c:":8000" | findstr /c:"LISTENING" >nul
if %errorlevel% equ 0 (
    echo [SKIP] Backend already running on port 8000.
    goto :show_lan
)
echo Starting backend (LAN-accessible) on port 8000 ...
start "AI4SE-Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:show_lan
timeout /t 6 /nobreak >nul
echo.
echo ============================================================
echo  Local:      http://localhost:8000
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /c:"IPv4"') do (
    echo  LAN:       http://%%i:8000   ^<- share this with group members
)
echo ============================================================
echo  NOTE: share the LAN address; all members browse it and register.
echo  (If members cannot connect, allow port 8000 in Windows Firewall:
echo   netsh advfirewall firewall add rule name="AI4SE" dir=in action=allow protocol=TCP localport=8000)
echo.
start http://localhost:8000
pause
exit /b 0
