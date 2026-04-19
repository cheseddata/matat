@echo off
REM ============================================================
REM Launch the Claude Code DESKTOP GUI on this project in YOLO mode.
REM
REM - Opens the packaged Claude app (same interface you already use
REM   — sessions on the left, chat area on the right).
REM - The project at F:\matat_git is pre-configured via
REM   .claude/settings.local.json to run in "bypass permissions"
REM   mode so tool calls are auto-approved without Shift+Tab.
REM
REM If you prefer the CLI terminal version instead, run:
REM   claude --dangerously-skip-permissions
REM ============================================================
cd /d "%~dp0"

echo.
echo ============================================================
echo   Claude Code (GUI, YOLO mode)
echo   Project: %cd%
echo ============================================================
echo.
echo   The Claude desktop app is opening now. Pick the "matat" or
echo   "matat_git" session from the sidebar (or start a new one).
echo.
echo   Bypass-permissions is already enabled for this project
echo   via .claude\settings.local.json — no Shift+Tab needed.
echo.

REM --- Ensure bypass-permissions is set for this project ---
if not exist .claude mkdir .claude
if not exist .claude\settings.local.json (
    echo { "permissions": { "defaultMode": "bypassPermissions" } } > .claude\settings.local.json
    echo   [i] Wrote .claude\settings.local.json (bypass permissions on)
)

REM --- Find the Claude GUI via Start Menu AUMID ---
powershell -NoProfile -Command ^
    "$app = Get-StartApps | Where-Object { $_.Name -eq 'Claude' } | Select-Object -First 1; ^
     if ($null -eq $app) { ^
        Write-Host '[X] Claude Code desktop app not found. Install from https://claude.com/download'; ^
        exit 1; ^
     }; ^
     Start-Process ('shell:AppsFolder\' + $app.AppID)"

if errorlevel 1 pause
