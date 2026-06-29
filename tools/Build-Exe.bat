@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo CISetup.exe をビルドしています...
echo.

python "%~dp0rebuild_exe.py"
set "RC=%errorlevel%"
if %RC% neq 0 (
  if /i not "%~1"=="/nopause" pause
  exit /b %RC%
)

echo.
echo 配布 zip も作る場合: powershell -File tools\Package-Distribution.ps1
echo.
if /i not "%~1"=="/nopause" pause
exit /b 0
