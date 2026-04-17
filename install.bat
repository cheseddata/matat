@echo off
REM ============================================================
REM Matat + ZTorm + Gemach — One-time installer for operator PC
REM
REM Creates venv, installs Python deps, creates a fresh SQLite DB
REM via Alembic migrations, seeds an admin user, then pulls the
REM operator's live data from C:\Gmach and C:\ztorm.
REM
REM This does NOT ship any database. Everything is built from the
REM Python code + the operator's local Access files.
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo    Matat ^| ZTorm ^| Gemach  Installer
echo ============================================================
echo.

REM --- [1/7] Check Python 3.12+ ---
where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python is not installed or not in PATH.
    echo     Download from https://www.python.org/downloads/
    echo     During install, CHECK the "Add Python to PATH" box.
    pause
    exit /b 1
)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo [1/7] Found Python !PYVER!

REM --- [2/7] Create venv ---
if exist venv (
    echo [2/7] Using existing venv
) else (
    echo [2/7] Creating Python virtual environment ^(venv^)...
    python -m venv venv
    if errorlevel 1 (
        echo [X] Failed to create venv. Re-run as administrator?
        pause
        exit /b 1
    )
)

REM --- [3/7] Install deps ---
echo [3/7] Installing Python packages into venv ^(takes ~2 minutes^)...
call venv\Scripts\python.exe -m pip install --upgrade pip --quiet
call venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [X] pip install failed. See above for details.
    pause
    exit /b 1
)
call venv\Scripts\python.exe -m pip install access-parser --quiet 2>nul

REM --- [4/7] Write local .env (SQLite + SANDBOX_MODE=1) ---
echo [4/7] Writing local .env config...
echo DATABASE_URL=sqlite:///%cd:\=/%/instance/matat.db> .env
echo SECRET_KEY=operator-sandbox-local-key>> .env
echo FLASK_APP=run.py>> .env
echo FLASK_DEBUG=0>> .env
echo SANDBOX_MODE=1>> .env
echo APP_DOMAIN=http://localhost:5060>> .env
echo ORG_NAME=Matat Mordechai>> .env
echo STRIPE_MODE=test>> .env
echo MAIL_PROVIDER=none>> .env

REM --- [5/7] Create DB from migrations + seed admin ---
if not exist instance mkdir instance
if exist instance\matat.db (
    echo [5/7] Database already exists, upgrading schema if needed...
    call venv\Scripts\python.exe -m flask db upgrade
) else (
    echo [5/7] Creating fresh database via Alembic migrations...
    call venv\Scripts\python.exe -m flask db upgrade
    if errorlevel 1 (
        echo [X] flask db upgrade failed. See errors above.
        pause
        exit /b 1
    )
    echo       Seeding admin user and default settings...
    call venv\Scripts\python.exe sync\seed_admin.py
)

REM --- [6/7] Pull operator's live data from C:\Gmach and C:\ztorm ---
echo [6/7] Refreshing data from C:\Gmach and C:\ztorm ...
if exist "C:\Gmach\MttData.mdb" (
    echo     Found C:\Gmach\MttData.mdb
    if exist "C:\ztorm\ztormdata.mdb" (
        echo     Found C:\ztorm\ztormdata.mdb
    )
    call "%~dp0sync_live_data.bat"
) else (
    echo     C:\Gmach\MttData.mdb not found.
    echo     The app will start with an empty database.
    echo     You can run sync_live_data.bat later when the Access files are available.
)

REM --- [7/7] Create Desktop shortcut ---
echo [7/7] Creating "Matat (Sandbox)" shortcut on the Desktop...
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Matat (Sandbox).lnk
powershell -NoProfile -Command "$w = New-Object -ComObject WScript.Shell; $s = $w.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%cd%\start.bat'; $s.WorkingDirectory = '%cd%'; $s.Save()" 2>nul

echo.
echo ============================================================
echo    Install complete.
echo    Double-click "Matat (Sandbox)" on your Desktop,
echo    or run start.bat from this folder.
echo.
echo    Login:    admin
echo    Password: admin123
echo.
echo    The browser will open to http://localhost:5060/login
echo    Every page shows an amber "SANDBOX MODE" banner.
echo ============================================================
echo.
pause
