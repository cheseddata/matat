@echo off
REM ============================================================
REM Matat + ZTorm + Gemach — Sandbox desktop launcher
REM
REM Opens the app in a native desktop window (WebView2), not a browser.
REM No port popup, no browser tabs, no "which port is free" guessing.
REM SANDBOX_MODE=1: no real charges, no real emails, no real SMS.
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
    echo     Run install.bat to create it.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Matat ^| ZTorm ^| Gemach  (SANDBOX MODE)
echo.
echo   Opening in desktop window...
echo   Login: admin  /  admin123
echo.
echo   *** NO LIVE TRANSACTIONS WILL BE SENT ***
echo   (No real bank charges, no real emails, no real SMS)
echo.
echo   Close the app window (or this console) to stop.
echo ============================================================
echo.

REM Make sure Flask picks up its normal one-process mode.
REM (WERKZEUG_RUN_MAIN must NOT be set here — it triggers reloader-child
REM behavior in werkzeug which then crashes looking for a server FD.)
set WERKZEUG_RUN_MAIN=
set FLASK_DEBUG=0

REM Launch desktop.py — creates a pywebview window + Flask on random port.
venv\Scripts\python.exe desktop.py

echo.
echo App closed. Window will close in 5 seconds...
timeout /t 5 /nobreak >nul
