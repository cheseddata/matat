@echo off
REM ============================================================
REM Build a self-contained operator install folder at F:\matat_operator_install
REM Excludes .git, venv, __pycache__, *.log, node_modules
REM Includes the current instance\matat.db so the operator has real data
REM ============================================================
setlocal
set SRC=%~dp0
set DST=F:\matat_operator_install

echo.
echo Building install kit at %DST%...
echo.

if exist "%DST%" (
    echo Removing existing %DST% ...
    rmdir /s /q "%DST%"
)

robocopy "%SRC%" "%DST%" ^
    /E ^
    /XD .git venv __pycache__ node_modules instance\__pycache__ logs .pytest_cache ^
    /XF *.log *.pid *.pyc .env package_operator_kit.bat ^
    /NFL /NDL /NJH /NJS /NP
if errorlevel 8 (
    echo Robocopy failed with code %errorlevel%
    pause
    exit /b 1
)

REM Make sure the .db file is present (robocopy /XD above excludes the __pycache__
REM under instance but keeps matat.db).
if not exist "%DST%\instance\matat.db" (
    echo [!] instance\matat.db missing from destination — did you forget to load data?
)

REM Write a VERSION stamp so we know what was shipped.
echo Build date: %date% %time% > "%DST%\VERSION.txt"
git -C "%SRC%" log -n 1 --pretty=format:"Commit: %%H%%n%%s%%n" >> "%DST%\VERSION.txt" 2>nul

echo.
echo ============================================================
echo    Install kit ready: %DST%
echo    Size:
for /f %%I in ('powershell -Command "(Get-ChildItem -Recurse '%DST%' | Measure-Object Length -Sum).Sum / 1MB"') do echo    %%I MB
echo.
echo    Copy the whole %DST% folder to the operator's PC.
echo    She then runs install.bat once, then start.bat daily.
echo ============================================================
pause
