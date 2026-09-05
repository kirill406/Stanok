@echo off
REM Install pre-commit hook for Windows
REM Run this script after git clone
echo Installing pre-commit hook...

for /f "delims=" %%R in ('git rev-parse --git-dir') do set GIT_DIR=%%R
if not exist "%GIT_DIR%\hooks" mkdir "%GIT_DIR%\hooks"

copy /Y "%~dp0pre-commit.hook" "%GIT_DIR%\hooks\pre-commit" >nul

echo Done! Hook installed.
echo Hook uses #!/bin/sh (MSYS2 bash from Git for Windows)