@echo off
REM ============================================================
REM Launch Claude Code in YOLO mode on the OPERATOR'S PC.
REM Tries the GUI first, falls back to CLI if the GUI isn't installed.
REM Writes .claude\settings.local.json so bypass-permissions is on
REM for this project regardless of surface (GUI or CLI).
REM ============================================================
cd /d "%~dp0"

echo.
echo ============================================================
echo   Claude Code - OPERATOR PC (YOLO mode)
echo   Project: %cd%
echo ============================================================
echo.

REM --- Ensure bypass-permissions is set for this project ---
if not exist .claude mkdir .claude
if not exist .claude\settings.local.json (
    echo { "permissions": { "defaultMode": "bypassPermissions" } } > .claude\settings.local.json
    echo   [i] Wrote .claude\settings.local.json ^(bypass permissions on^)
)

REM --- Try the Claude desktop GUI first (single-line PowerShell) ---
powershell -NoProfile -Command "$app = Get-StartApps | Where-Object { $_.Name -eq 'Claude' } | Select-Object -First 1; if ($null -ne $app) { Start-Process ('shell:AppsFolder\' + $app.AppID); exit 0 } else { exit 1 }"
if not errorlevel 1 (
    echo GUI launched. Pick this project from the sidebar.
    exit /b 0
)

REM --- Fall back to the CLI ---
echo Claude GUI not found; falling back to CLI.
where claude >nul 2>nul
if errorlevel 1 (
    echo [X] Neither Claude GUI nor CLI found.
    echo     GUI:  https://claude.com/download
    echo     CLI:  npm install -g @anthropic-ai/claude-code
    pause
    exit /b 1
)

if exist _operator_bootstrap.md (
    echo Bootstrap prompt found — loading into initial context.
    claude --dangerously-skip-permissions "Read _operator_bootstrap.md and continue the work it describes. If the user interrupts, follow their instructions instead."
) else (
    claude --dangerously-skip-permissions %*
)
