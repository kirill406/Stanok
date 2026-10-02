@echo off
rem Install git hooks from scripts/ into .git/hooks/
copy /Y scripts\pre-commit .git\hooks\pre-commit >nul
echo pre-commit hook installed.
