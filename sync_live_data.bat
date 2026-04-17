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
venv\Scripts\python.exe sync\import_gmach_data.py
if errorlevel 1 (
    echo   [X] Gemach base import failed.
    goto :gemach_done
)

REM Step 1d: import big transaction tables
echo.
echo [Gemach 4/4] Importing Peulot + Tnuot transactions ^(may take ~1 min^)...
venv\Scripts\python.exe sync\import_gmach_transactions.py
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
venv\Scripts\python.exe sync\import_ztorm_live.py
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
venv\Scripts\python.exe sync\run_smart_match.py

echo.
echo ============================================================
echo   Data sync complete.
echo ============================================================
REM No `pause` here — install.bat pauses at the end of its own flow.
REM If you're running sync_live_data.bat standalone, add `pause` below:
if /i "%1"=="/standalone" pause
