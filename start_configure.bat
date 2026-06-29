@echo off
REM 開発用: python ソースを優先（UI 変更が即反映）。Python が無いときだけ exe。
cd /d "%~dp0"
where python >nul 2>&1
if %errorlevel%==0 if exist "%~dp0configure.py" (
  python "%~dp0configure.py" %*
  if errorlevel 1 pause
  exit /b %errorlevel%
)
if exist "%~dp0CISetup.exe" (
  start "" "%~dp0CISetup.exe" %*
  exit /b 0
)
if exist "%~dp0dist\CISetup.exe" (
  start "" "%~dp0dist\CISetup.exe" %*
  exit /b 0
)
echo [エラー] Python も CISetup.exe も見つかりません。
pause
exit /b 1
