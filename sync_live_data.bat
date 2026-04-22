@echo off
REM ============================================================
REM Refresh the local sandbox DB with the OPERATOR's live data
REM Pulls from:
REM   C:\Gmach\MttData.mdb  (Gemach members / loans / peulot / tnuot)
REM   C:\ztorm\ztormdata.mdb  (ZTorm — uses Python access_parser,
REM                            requires that library; optional)
REM
REM Safe to run at install time or any time after (re-runnable).
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [X] venv missing. Run install.bat first.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM Force sync scripts to write to the LOCAL SQLite file (fast).
REM Even in "remote" DB mode, the sync always populates the local
REM SQLite first; push_to_matattest.py then copies gemach_* tables
REM up to matattest through the SSH tunnel (only runs if mode=remote).
REM ------------------------------------------------------------
set DATABASE_URL=sqlite:///C:/Matat/instance/matat.db

REM ------------------------------------------------------------
REM 1. GEMACH sync
REM ------------------------------------------------------------
echo.
echo ============================================================
echo   Syncing Gemach from C:\Gmach\MttData.mdb ...
echo ============================================================

if not exist "C:\Gmach\MttData.mdb" (
    echo   [!] C:\Gmach\MttData.mdb not found — skipping Gemach sync.
    echo       The shipped database will be used as-is.
    goto :gemach_done
)

set EXTRACT_DIR=%TEMP%\gmach_extract
if not exist "%EXTRACT_DIR%" mkdir "%EXTRACT_DIR%"

REM Step 1a: extract big tables (peulot + tnuot + munz) directly from MDB
REM via 32-bit PowerShell (Jet OLEDB 4.0 is 32-bit only).
echo.
echo [Gemach 1/4] Extracting Peulot / Tnuot / Munz from MttData.mdb...
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe ^
    -ExecutionPolicy Bypass ^
    -File "%~dp0sync\extract_gmach_big.ps1" ^
    -MdbPath "C:\Gmach\MttData.mdb" ^
    -OutDir "%EXTRACT_DIR%"
if errorlevel 1 (
    echo   [X] Gemach extract failed. See errors above.
    goto :gemach_done
)

REM Step 1b: extract smaller tables (haverim, hork, btlhork, lookups, translate)
echo.
echo [Gemach 2/4] Extracting Haverim / Hork / Btlhork / lookups...
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe ^
    -ExecutionPolicy Bypass ^
    -File "%~dp0sync\extract_gmach_small.ps1" ^
    -MdbPath "C:\Gmach\MttData.mdb" ^
    -OutDir "%EXTRACT_DIR%"
if errorlevel 1 (
    echo   [X] Gemach small-tables extract failed.
    goto :gemach_done
)

REM Step 1c: import members + loans
echo.
echo [Gemach 3/4] Importing Gemach members + loans...
set GMACH_EXTRACT_DIR=%EXTRACT_DIR%
venv\Scripts\python.exe -u sync\import_gmach_data.py
if errorlevel 1 (
    echo   [X] Gemach base import failed.
    goto :gemach_done
)

REM Step 1d: import big transaction tables
echo.
echo [Gemach 4/4] Importing Peulot + Tnuot transactions ^(may take ~1 min^)...
venv\Scripts\python.exe -u sync\import_gmach_transactions.py
if errorlevel 1 (
    echo   [X] Gemach transactions import failed.
)

:gemach_done

REM ------------------------------------------------------------
REM 2. ZTORM sync (optional — requires access_parser)
REM ------------------------------------------------------------
echo.
echo ============================================================
echo   Syncing ZTorm from C:\ztorm\ztormdata.mdb ...
echo ============================================================

if not exist "C:\ztorm\ztormdata.mdb" (
    echo   [!] C:\ztorm\ztormdata.mdb not found — skipping ZTorm sync.
    goto :ztorm_done
)

echo   ZTorm MDB is password-protected, so we use the Python
echo   access_parser library instead of direct OLE DB.
venv\Scripts\python.exe -c "import access_parser" 2>nul
if errorlevel 1 (
    echo   [i] access_parser not installed. Installing now...
    venv\Scripts\python.exe -m pip install access-parser --quiet
    if errorlevel 1 (
        echo   [X] Could not install access-parser. Skipping ZTorm sync.
        goto :ztorm_done
    )
)

echo.
echo   Running ZTorm import...
venv\Scripts\python.exe -u sync\import_ztorm_live.py
if errorlevel 1 (
    echo   [!] ZTorm import had errors. Sandbox will use shipped ZTorm data.
)

:ztorm_done

REM ------------------------------------------------------------
REM 3. Re-run smart-match linking
REM ------------------------------------------------------------
echo.
echo ============================================================
echo   Re-linking Gemach members to Matat donors...
echo ============================================================
venv\Scripts\python.exe -u sync\run_smart_match.py

REM ------------------------------------------------------------
REM 4. Push freshly-synced gemach data up to matattest (via tunnel)
REM     Only runs if instance\db_mode.txt says "remote".
REM ------------------------------------------------------------
set DB_MODE_FILE=%~dp0instance\db_mode.txt
set DB_MODE=local
if exist "%DB_MODE_FILE%" (
    for /f "tokens=*" %%i in (%DB_MODE_FILE%) do set DB_MODE=%%i
)
if /i "%DB_MODE%"=="remote" (
    echo.
    echo ============================================================
    echo   Pushing gemach_* tables to matattest MySQL ^(via SSH tunnel^)...
    echo ============================================================
    venv\Scripts\python.exe -u sync\push_to_matattest.py
    if errorlevel 1 (
        echo   [!] Push to matattest failed. Local SQLite is still up to date.
    )
)

REM ------------------------------------------------------------
REM 5. Push freshly-synced SQLite file to the test server
REM    (/var/www/matat/test on matat-server, reached via Tailscale)
REM    and restart matat-test so SQLAlchemy reopens the new file.
REM    Requires: Tailscale up, SSH key authorized for root@matat-server.
REM    Non-fatal on failure — local SQLite is still up to date.
REM ------------------------------------------------------------
where ssh >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo ============================================================
    echo   Pushing matat.db to test.matat server ^(via Tailscale^)...
    echo ============================================================
    scp -o ConnectTimeout=5 -o BatchMode=yes "%~dp0instance\matat.db" root@matat-server:/var/www/matat/test/instance/matat.db
    if errorlevel 1 (
        echo   [!] scp failed ^(Tailscale down? key not loaded?^). Skipping restart.
    ) else (
        ssh -o ConnectTimeout=5 -o BatchMode=yes root@matat-server "systemctl restart matat-test"
        if errorlevel 1 (
            echo   [!] Restart command failed. File copied but matat-test may need manual restart.
        ) else (
            echo   [OK] Test server refreshed.
        )
    )
)

echo.
echo ============================================================
echo   Data sync complete.
echo ============================================================
REM No `pause` here — install.bat pauses at the end of its own flow.
REM If you're running sync_live_data.bat standalone, add `pause` below:
if /i "%1"=="/standalone" pause
