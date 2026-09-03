@echo off
REM Установка pre-commit hook для проверки секретов
REM Запусти этот скрипт после git clone
echo Installing pre-commit hook...
copy /Y "%~dp0pre-commit.hook" "%~dp0..\.git\hooks\pre-commit"
echo Done! Hook установлен.
