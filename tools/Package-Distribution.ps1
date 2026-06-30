param(
    [string]$Version = "1.0.0"
)

# CISetup.exe をビルドし、社内配布 zip を dist\ に作成する。
# このスクリプトは tools\ に置かれている前提（リポジトリルート = 親フォルダ）。
$ErrorActionPreference = "Stop"
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $toolsDir
Set-Location $root

$distRoot = Join-Path $root "dist"
$exeName = "CISetup.exe"
$stage = Join-Path $distRoot "CISetup-$Version"
$zipPath = Join-Path $distRoot "CISetup-$Version.zip"

Write-Host "==> PyInstaller build"
python (Join-Path $toolsDir "rebuild_exe.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller ビルドに失敗しました。" }

$builtExe = Join-Path $distRoot $exeName
if (-not (Test-Path $builtExe)) {
    throw "ビルド失敗: $builtExe が生成されませんでした。tools\Build-Exe.bat を確認してください。"
}

$sizeMb = [math]::Round((Get-Item $builtExe).Length / 1MB, 1)
Write-Host "    $exeName ($sizeMb MB)"

if (Test-Path $stage) {
    Remove-Item $stage -Recurse -Force
}
New-Item -ItemType Directory -Path $stage -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stage "docs") -Force | Out-Null

# 配布物: exe + 利用者向け手順 + ユーザー向け README
Copy-Item $builtExe (Join-Path $stage $exeName) -Force
Copy-Item (Join-Path $root "Setup-Project.bat") $stage -Force

# 利用者向け README を README.md として同梱（開発者向けルート README ではない）
Copy-Item (Join-Path $root "docs\README-dist.md") (Join-Path $stage "README.md") -Force

# 利用者向けガイドのみ docs\ へ（開発者向け資料は同梱しない）
foreach ($doc in @("CI-GUIDE.md", "GUI.md", "CISetup-CI-Guide.marp.md")) {
    $src = Join-Path $root "docs\$doc"
    if (Test-Path $src) { Copy-Item $src (Join-Path $stage "docs") -Force }
}

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "==> Created: $zipPath"
Write-Host "    展開後 CISetup.exe をダブルクリック（Python 不要）"
