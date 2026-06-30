# CISetup 設定 GUI（Python 正式版）

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python が見つかりません。Python 3.10 以上をインストールしてください。"
}

$configure = Join-Path $root "configure.py"
if (-not (Test-Path $configure)) {
    throw "configure.py が見つかりません: $configure"
}

& python $configure @args
