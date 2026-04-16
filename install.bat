@echo off
REM ============================================================
REM Matat + ZTorm + Gemach — One-time installer for operator PC
REM Creates venv, installs Python deps, verifies DB, creates start.bat link
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo    Matat ^| ZTorm ^| Gemach  Installer
echo ============================================================
echo.

REM --- Check Python 3.12+ ---
where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python is not installed or not in PATH.
    echo     Download from https://www.python.org/downloads/ and pick "Add to PATH".
    pause
    exit /b 1
)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo [1/5] Found Python !PYVER!

REM --- Create venv ---
if exist venv (
    echo [2/5] Using existing venv
) else (
    echo [2/5] Creating Python virtual environment ^(venv^)...
    python -m venv venv
    if errorlevel 1 (
        echo [X] Failed to create venv. Re-run as administrator?
        pause
        exit /b 1
    )
)

REM --- Install deps ---
echo [3/5] Installing Python packages into venv ^(may take a minute^)...
call venv\Scripts\python.exe -m pip install --upgrade pip --quiet
call venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [X] pip install failed. See above for details.
    pause
    exit /b 1
)

REM --- Verify DB ---
if exist instance\matat.db (
    echo [4/5] Database found: instance\matat.db
) else (
    echo [!] Database instance\matat.db not found.
    echo     If this is a fresh install, run create_db.bat first.
)

REM --- Create desktop shortcut ---
echo [5/5] Creating start shortcut on the Desktop...
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Matat (Sandbox).lnk
powershell -NoProfile -Command ^
    "$w = New-Object -ComObject WScript.Shell; ^
     $s = $w.CreateShortcut('%SHORTCUT%'); ^
     $s.TargetPath = '%cd%\start.bat'; ^
     $s.WorkingDirectory = '%cd%'; ^
     $s.IconLocation = '%cd%\app\static\logo.ico,0'; ^
     $s.Save()" 2>nul

echo.
echo ============================================================
echo    Done. Double-click "Matat (Sandbox)" on your Desktop
echo    or run start.bat from this folder.
echo.
echo    Login:  admin
echo    Password: admin123
echo ============================================================
echo.
pause
