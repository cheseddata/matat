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

echo.
echo ============================================================
echo   Matat ^| ZTorm ^| Gemach  (SANDBOX MODE)
echo.
echo   Opening in desktop window...
echo   Login: admin  /  admin123
echo.
echo   Database: matattest @ 178.128.83.220 (via SSH tunnel)
echo   *** NO LIVE TRANSACTIONS WILL BE SENT ***
echo   (No real bank charges, no real emails, no real SMS)
echo.
echo   Close the app window (or this console) to stop.
echo ============================================================
echo.

REM --- Kill any orphaned tunnel from a previous run ---
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":33306 .*LISTENING"') do taskkill /PID %%a /F >nul 2>&1

REM --- Open SSH tunnel to matattest MySQL on 178.128.83.220 ---
REM Forwards local 127.0.0.1:33306 -> server localhost:3306
REM ExitOnForwardFailure: bail if the port can't be bound (prevents silent failure)
REM ServerAliveInterval: keep the tunnel alive through idle periods
echo Opening SSH tunnel to matattest...
start "MATAT_SSH_TUNNEL" /MIN ssh -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o StrictHostKeyChecking=accept-new -N -L 33306:localhost:3306 root@178.128.83.220
timeout /t 3 /nobreak >nul

REM Make sure Flask picks up its normal one-process mode.
REM (WERKZEUG_RUN_MAIN must NOT be set here — it triggers reloader-child
REM behavior in werkzeug which then crashes looking for a server FD.)
set WERKZEUG_RUN_MAIN=
set FLASK_DEBUG=0

REM Launch desktop.py — creates a pywebview window + Flask on random port.
venv\Scripts\python.exe desktop.py

REM --- Tear down tunnel ---
taskkill /FI "WINDOWTITLE eq MATAT_SSH_TUNNEL*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":33306 .*LISTENING"') do taskkill /PID %%a /F >nul 2>&1

echo.
echo App closed. Window will close in 5 seconds...
timeout /t 5 /nobreak >nul
