@echo off
REM ===========================================================================
REM sync_mirror.bat — full faithful mirror of all Access MDBs to a SQLite file.
REM Per the project's "faithful port" rule: VERBATIM Access table/column names,
REM all columns preserved, drop+create+insert (no upsert), comparison report.
REM Output: C:\matat\instance\mirror.db
REM ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [X] venv missing.
    pause & exit /b 1
)

set EXTRACT_ROOT=%TEMP%\matat_mirror_extract
if exist "%EXTRACT_ROOT%" rmdir /s /q "%EXTRACT_ROOT%"
mkdir "%EXTRACT_ROOT%"

set MIRROR_DIR=C:\matat\instance\mirror
if not exist "%MIRROR_DIR%" mkdir "%MIRROR_DIR%"
set PS32=C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe

echo.
echo ============================================================
echo   1. Extracting Gmach MDBs (verbatim, all tables, all cols)
echo ============================================================
call :gmach_extract "MttData" "C:\Gmach\MttData.mdb"
REM Mikud.mdb has its own table-level workgroup security and is NOT linked
REM by the front-end; the active postal-codes are in MttData.Kidomot already.
REM Skipping for now. To include Mikud.mdb later, route it through
REM extract_via_access_com.ps1 with a front-end that links it.
call :gmach_extract "trans"   "C:\Gmach\trans.mdb"

echo.
echo ============================================================
echo   2. Extracting ZTorm MDBs (via access_parser)
echo ============================================================
REM ztormdata uses DAO (more reliable than access_parser; handles memo fields)
call :ztorm_dao_extract "ztormdata"  "C:\ztorm\ztormdata.mdb"
call :ztorm_extract "zuser"          "C:\ztorm\zuser.mdb"
call :ztorm_extract "ztorm_bankim"   "C:\ztorm\bankim.mdb"
call :ztorm_extract "ztorm_mikud"    "C:\ztorm\mikud.mdb"
call :ztorm_extract "ztorm_shearim"  "C:\ztorm\shearim.mdb"
call :ztorm_extract "tash_ztormdata" "C:\ztorm\Tash\ztormdata.mdb"
call :ztorm_extract "tash_zuser"     "C:\ztorm\Tash\zuser.mdb"

echo.
echo ============================================================
echo   3. Building mirror.db
echo ============================================================
venv\Scripts\python.exe sync\build_mirror_sqlite.py "%EXTRACT_ROOT%" "%MIRROR_DIR%"
if errorlevel 1 (
    echo [X] build failed
    pause & exit /b 1
)

echo.
echo ============================================================
echo   4. Verifying mirror.db against source MDBs
echo ============================================================
venv\Scripts\python.exe sync\compare_mirror.py "%MIRROR_DIR%"
set CMPRC=%ERRORLEVEL%

echo.
echo ============================================================
if "%CMPRC%"=="0" (
    echo   MIRROR SYNC COMPLETE -- All comparisons PASS.
) else (
    echo   MIRROR SYNC COMPLETE -- See MISMATCHES above.
)
echo ============================================================
echo Mirror DB: %MIRROR_DB%
endlocal
exit /b 0

:gmach_extract
set NAME=%~1
set MDB=%~2
if not exist "%MDB%" (
    echo --- !NAME!: !MDB! not found, skipping
    goto :eof
)
mkdir "%EXTRACT_ROOT%\!NAME!" 2>nul
echo.
echo --- !NAME! ^(!MDB!^) ---
"%PS32%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync\extract_gmach_all.ps1" -MdbPath "!MDB!" -OutDir "%EXTRACT_ROOT%\!NAME!"
goto :eof

:ztorm_extract
set NAME=%~1
set MDB=%~2
if not exist "%MDB%" (
    echo --- !NAME!: !MDB! not found, skipping
    goto :eof
)
mkdir "%EXTRACT_ROOT%\!NAME!" 2>nul
echo.
echo --- !NAME! ^(!MDB!^) ---
venv\Scripts\python.exe sync\extract_ztorm_all.py "!MDB!" "%EXTRACT_ROOT%\!NAME!"
goto :eof

:ztorm_dao_extract
set NAME=%~1
set MDB=%~2
if not exist "%MDB%" (
    echo --- !NAME!: !MDB! not found, skipping
    goto :eof
)
mkdir "%EXTRACT_ROOT%\!NAME!" 2>nul
echo.
echo --- !NAME! ^(!MDB!^) [DAO+wrkgrp] ---
"%PS32%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync\extract_ztorm_dao.ps1" -MdbPath "!MDB!" -OutDir "%EXTRACT_ROOT%\!NAME!"
goto :eof
