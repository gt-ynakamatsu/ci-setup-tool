@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM プロジェクト初回セットアップ: CI 配置 + 設定 GUI
REM   Setup-Project.bat
REM   Setup-Project.bat D:\work\MyApp

cd /d "%~dp0"

set "BB_PY=%~dp0configure.py"
set "BB_EXE=%~dp0CISetup.exe"
if not exist "%BB_EXE%" set "BB_EXE=%~dp0dist\CISetup.exe"

set "BB_RUN="
where python >nul 2>&1
if %errorlevel%==0 if exist "%BB_PY%" set "BB_RUN=py"
if not defined BB_RUN if exist "%BB_EXE%" set "BB_RUN=exe"

if not defined BB_RUN (
  echo [エラー] configure.py（Python）も CISetup.exe も見つかりません。
  echo          Build-Exe.bat で exe をビルドするか、Python をインストールしてください。
  goto :EndError
)

echo.
echo ========================================
echo   CISetup CI - プロジェクトセットアップ
echo ========================================
echo.

set "PROJECT=%~1"
if "!PROJECT!"=="" (
  echo git clone したプロジェクトフォルダを入力してください。
  echo （.sln ファイルがあるフォルダ = リポジトリルート）
  echo.
  set /p "PROJECT=フォルダパス: "
)

if "!PROJECT!"=="" (
  echo [エラー] フォルダが指定されていません。
  goto :EndError
)

if not exist "!PROJECT!" (
  echo [エラー] フォルダが見つかりません: !PROJECT!
  goto :EndError
)

for %%F in ("!PROJECT!") do set "PROJECT=%%~fF"

echo 対象: !PROJECT!
echo.

echo [1/2] CI ファイルを自動配置しています...
if "%BB_RUN%"=="py" (
  python "%BB_PY%" --bootstrap "!PROJECT!"
) else (
  "%BB_EXE%" --bootstrap "!PROJECT!"
)
if errorlevel 1 (
  echo [エラー] CI ファイルの配置に失敗しました。
  goto :EndError
)
echo       完了（cisetup/ 以下）

echo.
echo [2/2] 設定 GUI を起動します...
if "%BB_RUN%"=="py" (
  start "" python "%BB_PY%" --open "!PROJECT!"
) else (
  start "" "%BB_EXE%" --open "!PROJECT!"
)

echo.
echo GUI で ①〜⑤ を入力し、「セットアップを実行」で保存・Jenkins 反映・Git push まで行えます。
echo.
goto :EndOk

:EndError
echo.
pause
exit /b 1

:EndOk
pause
exit /b 0
