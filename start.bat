@echo off
REM ============================================================
REM Matat + ZTorm + Gemach — Sandbox launcher
REM SANDBOX_MODE=1 means NO real charges, NO real emails, NO SMS.
REM Safe for operator sign-off / training / report verification.
REM ============================================================
cd /d "%~dp0"

REM *** SANDBOX KILL-SWITCH — leave this set until operator sign-off ***
set SANDBOX_MODE=1

REM --- Basic sanity checks ---
if not exist venv\Scripts\python.exe (
    echo [X] Python virtual env not found. Run install.bat first.
    pause
    exit /b 1
)
if not exist instance\matat.db (
    echo [X] Database not found at instance\matat.db.
    echo     If this is a fresh install, run create_db.bat.
    pause
    exit /b 1
)

REM --- Pick a port (5050 default, fallback 5051 if busy) ---
set PORT=5050
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul
if not errorlevel 1 (
    set PORT=5051
)

REM --- Open browser to the app after a 2-second delay ---
start "" /b cmd /c "timeout /t 2 >nul & start http://localhost:%PORT%/login"

echo.
echo ============================================================
echo    Matat ^| ZTorm ^| Gemach  ^(SANDBOX MODE^)
echo    http://localhost:%PORT%/
echo    Login: admin  /  admin123
echo.
echo    *** NO LIVE TRANSACTIONS WILL BE SENT ***
echo    ^(No real bank charges, no real emails, no real SMS^)
echo.
echo    Close this window to stop the server.
echo ============================================================
echo.

REM --- Run the Flask app (set PORT so run.py picks it up) ---
set PORT=%PORT%
venv\Scripts\python.exe run.py
pause
