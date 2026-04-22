@echo off
REM ============================================================
REM Matat TEST desktop launcher
REM
REM Opens the remote test server (/var/www/matat/test on
REM matat-server) in a native WebView2 window — same look as
REM start.bat, but running against the shared test instance so
REM the operator's PC is NOT tied up for testing.
REM
REM Flow:
REM   1. Open SSH tunnel 127.0.0.1:18080 -> matat-server:5051
REM      (Tailscale provides the matat-server hostname)
REM   2. Launch desktop_test.py, which opens the pywebview window
REM   3. On window close, tear the tunnel down.
REM ============================================================
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [X] Python virtual env not found. Run install.bat first.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Matat ^| ZTorm ^| Gemach  (TEST — remote sandbox)
echo.
echo   Opening in desktop window...
echo   Target: matat-server:/var/www/matat/test
echo   Branch: staging (auto-deploys on push)
echo   *** NO LIVE TRANSACTIONS ^(SANDBOX MODE is always on^) ***
echo.
echo   Close the app window (or this console) to stop.
echo ============================================================
echo.

REM Kill any orphaned tunnel on 18080 from a previous run.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":18080 .*LISTENING"') do taskkill /PID %%a /F >nul 2>&1

echo Opening SSH tunnel to matat-server (Tailscale)...
start "MATAT_TEST_TUNNEL" /MIN ssh -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o StrictHostKeyChecking=accept-new -N -L 18080:127.0.0.1:5051 root@matat-server
timeout /t 3 /nobreak >nul

REM Launch the pywebview wrapper.
venv\Scripts\python.exe desktop_test.py

REM Tear down tunnel.
taskkill /FI "WINDOWTITLE eq MATAT_TEST_TUNNEL*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":18080 .*LISTENING"') do taskkill /PID %%a /F >nul 2>&1

echo.
echo Window closed. Console will close in 5 seconds...
timeout /t 5 /nobreak >nul
