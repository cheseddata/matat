@echo off
REM ============================================================
REM Launch Claude Code in YOLO (no-approval) mode on this project.
REM
REM Use when:
REM   - You are running multiple projects in parallel
REM   - You don't want to babysit permission prompts
REM   - You trust the session to use your credentials freely
REM
REM Details:
REM   --dangerously-skip-permissions  : approve all tool calls silently
REM   cwd is this directory (F:\matat_git) so Claude starts on the project
REM ============================================================
cd /d "%~dp0"

echo.
echo ============================================================
echo   Claude Code - YOLO MODE (no approval prompts)
echo   Project: %cd%
echo ============================================================
echo.
echo   To quit: type /exit or press Ctrl+C twice
echo.

where claude >nul 2>nul
if errorlevel 1 (
    echo [X] claude CLI not found in PATH.
    echo     Install with: npm install -g @anthropic-ai/claude-code
    echo     Or see: https://docs.claude.com/en/docs/claude-code
    pause
    exit /b 1
)

claude --dangerously-skip-permissions %*
