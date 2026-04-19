@echo off
REM ============================================================
REM Launch Claude Code in YOLO mode on the OPERATOR'S PC.
REM Same as start_claude_yolo.bat but tuned for her install at C:\Matat.
REM
REM Double-click this file after install.bat to spawn a Claude Code
REM session that:
REM   * starts in C:\Matat (the project)
REM   * never asks for permission approval
REM   * picks up a starting prompt from ./_operator_bootstrap.md
REM     (if present) so it has context on what to do next
REM ============================================================
cd /d "%~dp0"

echo.
echo ============================================================
echo   Claude Code - OPERATOR PC (YOLO)
echo   Project: %cd%
echo ============================================================
echo.

where claude >nul 2>nul
if errorlevel 1 (
    echo [X] claude CLI not found in PATH.
    echo     Install with: npm install -g @anthropic-ai/claude-code
    pause
    exit /b 1
)

if exist _operator_bootstrap.md (
    echo Bootstrap prompt found — loading into initial context.
    echo.
    claude --dangerously-skip-permissions "Read _operator_bootstrap.md and continue the work it describes. If the user interrupts, follow their instructions instead."
) else (
    claude --dangerously-skip-permissions %*
)
