param(
    [string]$OutDir = "",
    [string]$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe",
    [string]$ThemeCss = "C:\Users\$env:USERNAME\.cursor\skills\genetec-presentation-template\genetec.css"
)

# 配布 zip に入れる手順書の PDF を作る。
#   CI-GUIDE.md / GUI.md        → md2pdf.js（Mermaid 図を描画して A4 の PDF）
#   CISetup-CI-Guide.marp.md    → Marp CLI（genetec テーマのスライド PDF）
# 前提: Node.js（npm / node が PATH にあること）と Google Chrome。
# 初回のみ tools\docs-pdf で npm install が走る。

$ErrorActionPreference = "Stop"
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $toolsDir
$pdfTool = Join-Path $toolsDir "docs-pdf"
$guides = Join-Path $root "docs\guides"

if (-not $OutDir) { $OutDir = Join-Path $root "dist\docs-pdf" }

foreach ($cmd in @("node", "npm")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd が見つかりません。Node.js を入れてから再実行してください。"
    }
}
if (-not (Test-Path $ChromePath)) { throw "Chrome が見つかりません: $ChromePath" }
if (-not (Test-Path $ThemeCss)) { throw "Marp テーマが見つかりません: $ThemeCss" }

if (-not (Test-Path (Join-Path $pdfTool "node_modules"))) {
    Write-Host "==> npm install (tools\docs-pdf)"
    Push-Location $pdfTool
    try {
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install に失敗しました。" }
    }
    finally { Pop-Location }
}

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$marp = Join-Path $pdfTool "node_modules\.bin\marp.cmd"

Push-Location $pdfTool
try {
    foreach ($name in @("CI-GUIDE", "GUI")) {
        Write-Host "==> $name.pdf"
        $out = Join-Path $OutDir "$name.pdf"
        node md2pdf.js (Join-Path $guides "$name.md") $out $ChromePath
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $out)) { throw "$name.pdf の作成に失敗しました。" }
    }
}
finally { Pop-Location }

Write-Host "==> CISetup-CI-Guide.pdf (Marp)"
$slidesMd = Join-Path $guides "CISetup-CI-Guide.marp.md"
$slidesPdf = Join-Path $OutDir "CISetup-CI-Guide.pdf"
& $marp --no-config-file --pdf --pdf-outlines --allow-local-files --browser chrome --browser-path $ChromePath --theme-set $ThemeCss -o $slidesPdf -- $slidesMd
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $slidesPdf)) { throw "CISetup-CI-Guide.pdf の作成に失敗しました。" }

Write-Host "==> PDF: $OutDir"
Get-ChildItem $OutDir -Filter *.pdf | ForEach-Object { "    {0}  ({1:N0} bytes)" -f $_.Name, $_.Length }
