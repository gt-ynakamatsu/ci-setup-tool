param(
    [string]$Version = ""
)

# CISetup.exe をビルドし、社内配布 zip を dist\ に作成する。
# このスクリプトは tools\ に置かれている前提（リポジトリルート = 親フォルダ）。
# -Version 未指定時は cisetup.version.VERSION を使う。
$ErrorActionPreference = "Stop"
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $toolsDir
Set-Location $root

if (-not $Version) {
    $Version = python -c "from cisetup.version import VERSION; print(VERSION)"
    if ($LASTEXITCODE -ne 0 -or -not $Version) {
        throw "cisetup.version.VERSION を読めませんでした。"
    }
    $Version = $Version.Trim()
}

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
Copy-Item (Join-Path $root "docs\guides\README-dist.md") (Join-Path $stage "README.md") -Force

# 利用者向けガイドは PDF にして docs\ へ（開発者向け資料は同梱しない）
$pdfDir = Join-Path $distRoot "docs-pdf"
Write-Host "==> 手順書 PDF"
& (Join-Path $toolsDir "Build-DocsPdf.ps1") -OutDir $pdfDir
if ($LASTEXITCODE -ne 0) { throw "手順書 PDF の作成に失敗しました。" }
foreach ($pdf in @("CI-GUIDE.pdf", "GUI.pdf", "CISetup-CI-Guide.pdf")) {
    $src = Join-Path $pdfDir $pdf
    if (-not (Test-Path $src)) { throw "PDF がありません: $src" }
    Copy-Item $src (Join-Path $stage "docs") -Force
}

# Jenkins サーバーの手順書は、版番号付きの PDF をそのまま同梱する。
$guides = Join-Path $root "docs\guides"
foreach ($pdf in @(
    "JENKINS-SERVER-SETUP-version3.2.pdf",
    "JENKINS-SERVER-SETUP-MANUAL-version1.2.pdf"
)) {
    $src = Join-Path $guides $pdf
    if (-not (Test-Path $src)) { throw "PDF がありません: $src" }
    Copy-Item $src (Join-Path $stage "docs") -Force
}

$stageTools = Join-Path $stage "tools"
New-Item -ItemType Directory -Path $stageTools -Force | Out-Null
$setupScript = Join-Path $toolsDir "Setup-JenkinsServer.ps1"
if (-not (Test-Path $setupScript)) { throw "スクリプトがありません: $setupScript" }
Copy-Item $setupScript (Join-Path $stageTools "Setup-JenkinsServer.ps1") -Force

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "==> Created: $zipPath"
Write-Host "    展開後 CISetup.exe をダブルクリック（Python 不要）"
