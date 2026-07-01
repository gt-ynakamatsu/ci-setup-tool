param(
    [string]$Configuration = "Release",
    # 危険度がこの水準以上のとき終了コード1（ステージを失敗）にする。
    #   None   : 常に成功（検出のみ・既定）
    #   High   : 高リスクが1件でもあれば失敗
    #   Medium : 中リスク以上があれば失敗
    # ※ Jenkins の自動トリガーでは $env:ANALYSIS_FAIL_ON が空文字で渡ることがあり、
    #   ValidateSet を付けるとバインド時に弾かれてしまう。空は本体側で None に正規化する。
    [string]$FailOn = "None"
)

# Jenkins analyze ステージ — 静的解析レポート生成。FailOn で重大度に応じた失敗判定。
$ErrorActionPreference = "Stop"
# Jenkins の自動トリガー等で CONFIGURATION が空のまま渡されると
# `dotnet build -c` の引数が欠落し MSB4126 になるため既定値で補う。
if ([string]::IsNullOrWhiteSpace($Configuration)) { $Configuration = "Release" }
# FailOn も空文字で渡ることがあるため既定値に補正してから検証する。
if ([string]::IsNullOrWhiteSpace($FailOn)) { $FailOn = "None" }
if ($FailOn -notin @('None', 'High', 'Medium')) {
    throw "FailOn は None / High / Medium のいずれかを指定してください (指定値: '$FailOn')。"
}
. (Join-Path $PSScriptRoot 'ci-config.ps1')
$ci = Get-CiSettings
Set-Location $ci.Root

$env:CI = "true"

$analysisDir = Join-PathMulti $ci.Root @('artifacts', 'analysis')
if (Test-Path $analysisDir) {
    Remove-Item $analysisDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $analysisDir | Out-Null

if ($ci.Profile -eq 'custom') {
    if ([string]::IsNullOrWhiteSpace($ci.AnalyzeCommand)) {
        Write-Host "No custom analyze command set. Skipping static analysis."
        return
    }
    Write-Host "==> Custom analyze: $($ci.AnalyzeCommand)"
    Invoke-Expression $ci.AnalyzeCommand
    $analyzeExit = $LASTEXITCODE
    # 解析ツールが artifacts\analysis に出力したものはそのまま配置・通知に使われる。
    if ($FailOn -ne 'None' -and $analyzeExit -ne 0) {
        throw "Analyze command failed (exit code $analyzeExit)."
    }
    Write-Host "Static analysis (custom) completed."
    return
}

$env:DOTNET_NOLOGO = "true"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "true"

$reportPath = Join-Path $analysisDir 'analysis-report.md'
$csvPath = Join-Path $analysisDir 'analysis-findings.csv'
$rawPath = Join-Path $analysisDir 'analysis-build.log'

function Test-SecurityRule {
    param([string]$Rule)
    # CA3xxx / CA5xxx は Security カテゴリ。CA2100 等は SQL インジェクション系。
    return ($Rule -match '^CA(3\d{3}|5\d{3})$') -or
           ($Rule -in @('CA2100', 'CA2109', 'CA2119', 'CA2153', 'CA2300', 'CA2301', 'CA2302', 'CA2305', 'CA2310', 'CA2321', 'CA2322', 'CA2326', 'CA2327', 'CA2328', 'CA2329', 'CA2330', 'CA2350', 'CA2351', 'CA2352', 'CA2361', 'CA2362')) -or
           ($Rule -like 'SCS*') -or ($Rule -like 'SEC*')
}

function Get-RiskLevel {
    param([string]$Sev, [string]$Rule)
    if ($Sev -eq 'error') { return 'High' }
    if (Test-SecurityRule -Rule $Rule) { return 'High' }
    if ($Sev -eq 'warning') { return 'Medium' }
    return 'Low'
}

function Get-RelativePath {
    param([string]$Path, [string]$Root)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    $full = $Path.Trim()
    if ($full.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $full.Substring($Root.Length).TrimStart('\', '/')
    }
    return $full
}

Write-Host "==> Project: $($ci.ProjectName)"
Write-Host "==> Restore"
dotnet restore $ci.SolutionFile | Out-Host

Write-Host "==> Static analysis (Roslyn analyzers: all rules enabled)"
# プロジェクトファイルを書き換えずに全アナライザーを有効化。ここではビルドを失敗させない。
$buildOutput = & dotnet build $ci.SolutionFile `
    -c $Configuration `
    --no-restore `
    --nologo `
    -p:EnableNETAnalyzers=true `
    -p:AnalysisMode=AllEnabledByDefault `
    -p:AnalysisLevel=latest `
    -p:EnforceCodeStyleInBuild=true `
    -p:RunAnalyzersDuringBuild=true `
    -p:TreatWarningsAsErrors=false 2>&1
$buildExit = $LASTEXITCODE
$buildOutput | Out-String | Set-Content -Path $rawPath -Encoding UTF8

$patternLoc = '^(?<file>(?:[A-Za-z]:)?[^()]+?)\((?<line>\d+)(?:,\d+)?\):\s+(?<sev>error|warning|info)\s+(?<rule>[A-Za-z]+\d+):\s+(?<msg>.+?)(?:\s+\[[^\]]*\])?\s*$'
$patternNoLoc = '^(?<file>.+?)\s*:\s+(?<sev>error|warning|info)\s+(?<rule>[A-Za-z]+\d+):\s+(?<msg>.+?)(?:\s+\[[^\]]*\])?\s*$'

$findings = [ordered]@{}
foreach ($entry in $buildOutput) {
    $text = ([string]$entry).TrimEnd()
    if ([string]::IsNullOrWhiteSpace($text)) { continue }

    $m = [regex]::Match($text, $patternLoc)
    $line = 0
    if ($m.Success) {
        $line = [int]$m.Groups['line'].Value
    }
    else {
        $m = [regex]::Match($text, $patternNoLoc)
        if (-not $m.Success) { continue }
    }

    $rule = $m.Groups['rule'].Value
    $sev = $m.Groups['sev'].Value.ToLower()
    $file = Get-RelativePath -Path $m.Groups['file'].Value -Root $ci.Root
    $msg = $m.Groups['msg'].Value.Trim()
    $key = "$file|$line|$rule"
    if ($findings.Contains($key)) { continue }

    $findings[$key] = [PSCustomObject]@{
        Risk    = (Get-RiskLevel -Sev $sev -Rule $rule)
        Rule    = $rule
        Level   = $sev
        File    = $file
        Line    = $line
        Message = $msg
    }
}

$all = @($findings.Values)
$high = @($all | Where-Object { $_.Risk -eq 'High' } | Sort-Object Rule, File, Line)
$med = @($all | Where-Object { $_.Risk -eq 'Medium' } | Sort-Object Rule, File, Line)
$low = @($all | Where-Object { $_.Risk -eq 'Low' } | Sort-Object Rule, File, Line)

# ---- サマリー JSON（Teams 通知などが参照） ----
$summaryPath = Join-Path $analysisDir 'analysis-summary.json'
[PSCustomObject]@{
    high      = $high.Count
    medium    = $med.Count
    low       = $low.Count
    total     = $all.Count
    generated = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
} | ConvertTo-Json | Set-Content -Path $summaryPath -Encoding UTF8

# ---- CSV（全件） ----
if ($all.Count -gt 0) {
    $all | Sort-Object @{Expression = { @('High', 'Medium', 'Low').IndexOf($_.Risk) } }, Rule, File, Line |
        Select-Object Risk, Rule, Level, File, Line, Message |
        Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8
}

# ---- Markdown レポート ----
function Format-FindingTable {
    param([object[]]$Items)
    if ($Items.Count -eq 0) { return @('（該当なし）', '') }
    $lines = @('| ルール | 場所 | 内容 |', '| --- | --- | --- |')
    foreach ($f in $Items) {
        $loc = if ($f.Line -gt 0) { "$($f.File):$($f.Line)" } else { $f.File }
        $safeMsg = ($f.Message -replace '\|', '\|')
        $lines += "| $($f.Rule) | $loc | $safeMsg |"
    }
    $lines += ''
    return $lines
}

$ruleSummary = $all |
    Group-Object Rule |
    ForEach-Object {
        [PSCustomObject]@{ Rule = $_.Name; Risk = $_.Group[0].Risk; Count = $_.Count }
    } |
    Sort-Object @{Expression = { @('High', 'Medium', 'Low').IndexOf($_.Risk) } }, @{Expression = 'Count'; Descending = $true }

$report = New-Object System.Collections.Generic.List[string]
$report.Add("# 静的解析レポート — $($ci.ProjectName)")
$report.Add('')
$report.Add("- 生成日時: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$report.Add("- 構成: $Configuration")
$report.Add("- ソリューション: $($ci.SolutionFile)")
$report.Add('')
$report.Add('## 危険度サマリー')
$report.Add('')
$report.Add('| 危険度 | 件数 | 説明 |')
$report.Add('| --- | --- | --- |')
$report.Add("| 高 (High) | $($high.Count) | コンパイルエラー・セキュリティ系。要対応 |")
$report.Add("| 中 (Medium) | $($med.Count) | アナライザー警告。バグの可能性あり |")
$report.Add("| 低 (Low) | $($low.Count) | スタイル・情報レベルの指摘 |")
$report.Add('')

$report.Add('## 高リスク (High)')
$report.Add('')
Format-FindingTable -Items $high | ForEach-Object { $report.Add($_) }

$report.Add('## 中リスク (Medium)')
$report.Add('')
Format-FindingTable -Items $med | ForEach-Object { $report.Add($_) }

$report.Add('## 低リスク (Low) — ルール別件数')
$report.Add('')
$lowByRule = $low | Group-Object Rule | Sort-Object Count -Descending
if ($lowByRule.Count -eq 0) {
    $report.Add('（該当なし）')
}
else {
    $report.Add('| ルール | 件数 |')
    $report.Add('| --- | --- |')
    foreach ($g in $lowByRule) { $report.Add("| $($g.Name) | $($g.Count) |") }
}
$report.Add('')

$report.Add('## ルール別件数（全体）')
$report.Add('')
$report.Add('| ルール | 危険度 | 件数 |')
$report.Add('| --- | --- | --- |')
foreach ($r in $ruleSummary) { $report.Add("| $($r.Rule) | $($r.Risk) | $($r.Count) |") }
$report.Add('')

$report | Set-Content -Path $reportPath -Encoding UTF8

# ---- HTML レポート（ブラウザでそのまま閲覧可能・自己完結） ----
function ConvertTo-HtmlText {
    param([string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { return '' }
    return ($Value -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' -replace '"', '&quot;')
}

$riskClass = @{ High = 'high'; Medium = 'medium'; Low = 'low' }
$riskLabel = @{ High = '高 High'; Medium = '中 Medium'; Low = '低 Low' }

$ordered = $all | Sort-Object @{Expression = { @('High', 'Medium', 'Low').IndexOf($_.Risk) } }, Rule, File, Line

$rowsHtml = New-Object System.Collections.Generic.List[string]
foreach ($f in $ordered) {
    $loc = if ($f.Line -gt 0) { "$($f.File):$($f.Line)" } else { $f.File }
    $cls = $riskClass[$f.Risk]
    $rowsHtml.Add(
        "<tr data-risk=`"$($f.Risk)`"><td><span class=`"badge $cls`">$($riskLabel[$f.Risk])</span></td>" +
        "<td class=`"rule`">$(ConvertTo-HtmlText $f.Rule)</td>" +
        "<td class=`"loc`">$(ConvertTo-HtmlText $loc)</td>" +
        "<td>$(ConvertTo-HtmlText $f.Message)</td></tr>")
}

$ruleRowsHtml = New-Object System.Collections.Generic.List[string]
foreach ($r in $ruleSummary) {
    $cls = $riskClass[$r.Risk]
    $ruleRowsHtml.Add("<tr><td class=`"rule`">$(ConvertTo-HtmlText $r.Rule)</td><td><span class=`"badge $cls`">$($riskLabel[$r.Risk])</span></td><td>$($r.Count)</td></tr>")
}

$generated = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$htmlPath = Join-Path $analysisDir 'analysis-report.html'

$html = @"
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>静的解析レポート - $(ConvertTo-HtmlText $ci.ProjectName)</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: "Segoe UI", "Yu Gothic UI", system-ui, sans-serif; margin: 0; background: #f5f6f8; color: #1f2329; }
  header { background: #1f2329; color: #fff; padding: 20px 28px; }
  header h1 { margin: 0 0 6px; font-size: 20px; }
  header .meta { font-size: 13px; opacity: .8; }
  main { padding: 24px 28px; max-width: 1200px; margin: 0 auto; }
  .cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
  .card { flex: 1 1 160px; border-radius: 10px; padding: 16px 18px; color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.15); }
  .card .n { font-size: 32px; font-weight: 700; line-height: 1; }
  .card .l { font-size: 13px; opacity: .95; margin-top: 6px; }
  .card.high { background: #d13438; } .card.medium { background: #c19c00; } .card.low { background: #5a6473; }
  .controls { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; margin: 14px 0; }
  .controls input[type=search] { flex: 1 1 280px; padding: 9px 12px; border: 1px solid #c8ccd2; border-radius: 8px; font-size: 14px; }
  .controls label { font-size: 14px; cursor: pointer; user-select: none; display: inline-flex; align-items: center; gap: 6px; }
  table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); margin-bottom: 28px; }
  th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid #eef0f3; font-size: 13.5px; vertical-align: top; }
  th { background: #eef1f5; font-weight: 600; position: sticky; top: 0; }
  td.rule { font-family: Consolas, monospace; white-space: nowrap; }
  td.loc { font-family: Consolas, monospace; color: #3a4250; white-space: nowrap; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; color: #fff; font-size: 12px; font-weight: 600; white-space: nowrap; }
  .badge.high { background: #d13438; } .badge.medium { background: #c19c00; } .badge.low { background: #5a6473; }
  h2 { font-size: 16px; margin: 26px 0 10px; }
  .empty { color: #6b7280; font-style: italic; }
  @media (prefers-color-scheme: dark) {
    body { background: #1a1d21; color: #e6e8eb; }
    table { background: #24282d; box-shadow: none; } th { background: #2c3137; } td, th { border-bottom-color: #333a41; }
    .controls input[type=search] { background: #24282d; color: #e6e8eb; border-color: #3a4148; }
  }
</style>
</head>
<body>
<header>
  <h1>静的解析レポート — $(ConvertTo-HtmlText $ci.ProjectName)</h1>
  <div class="meta">生成日時: $generated ／ 構成: $(ConvertTo-HtmlText $Configuration) ／ ソリューション: $(ConvertTo-HtmlText $ci.SolutionFile)</div>
</header>
<main>
  <div class="cards">
    <div class="card high"><div class="n">$($high.Count)</div><div class="l">高 High（要対応）</div></div>
    <div class="card medium"><div class="n">$($med.Count)</div><div class="l">中 Medium（バグの可能性）</div></div>
    <div class="card low"><div class="n">$($low.Count)</div><div class="l">低 Low（スタイル等）</div></div>
  </div>

  <h2>指摘一覧</h2>
  <div class="controls">
    <input type="search" id="q" placeholder="ルール / ファイル / メッセージで絞り込み..." oninput="applyFilters()">
    <label><input type="checkbox" id="cHigh" checked onchange="applyFilters()"> 高</label>
    <label><input type="checkbox" id="cMedium" checked onchange="applyFilters()"> 中</label>
    <label><input type="checkbox" id="cLow" checked onchange="applyFilters()"> 低</label>
  </div>
  <table id="findings">
    <thead><tr><th>危険度</th><th>ルール</th><th>場所</th><th>内容</th></tr></thead>
    <tbody>
$([string]::Join("`n", $rowsHtml))
    </tbody>
  </table>
  $(if ($all.Count -eq 0) { '<p class="empty">問題は検出されませんでした。</p>' })

  <h2>ルール別件数</h2>
  <table>
    <thead><tr><th>ルール</th><th>危険度</th><th>件数</th></tr></thead>
    <tbody>
$([string]::Join("`n", $ruleRowsHtml))
    </tbody>
  </table>
</main>
<script>
  function applyFilters() {
    var q = document.getElementById('q').value.toLowerCase();
    var show = { High: document.getElementById('cHigh').checked, Medium: document.getElementById('cMedium').checked, Low: document.getElementById('cLow').checked };
    var rows = document.querySelectorAll('#findings tbody tr');
    for (var i = 0; i < rows.length; i++) {
      var tr = rows[i];
      var ok = show[tr.dataset.risk] && (q === '' || tr.textContent.toLowerCase().indexOf(q) !== -1);
      tr.style.display = ok ? '' : 'none';
    }
  }
</script>
</body>
</html>
"@

$html | Set-Content -Path $htmlPath -Encoding UTF8

# ---- コンソールサマリー ----
Write-Host ''
Write-Host '====================== 静的解析結果 ======================'
Write-Host ("  高 (High)  : {0}" -f $high.Count)
Write-Host ("  中 (Medium): {0}" -f $med.Count)
Write-Host ("  低 (Low)   : {0}" -f $low.Count)
Write-Host '----------------------------------------------------------'
if ($high.Count -gt 0) {
    Write-Host '  [高リスク] 上位:'
    foreach ($f in ($high | Select-Object -First 15)) {
        $loc = if ($f.Line -gt 0) { "$($f.File):$($f.Line)" } else { $f.File }
        Write-Host ("    - {0}  {1}  {2}" -f $f.Rule, $loc, $f.Message)
    }
}
Write-Host "  HTML    : $htmlPath  (ブラウザで開く)"
Write-Host "  Markdown: $reportPath"
Write-Host "  CSV     : $csvPath"
Write-Host '=========================================================='

if ($buildExit -ne 0 -and $high.Count -eq 0) {
    Write-Warning "解析ビルドが終了コード $buildExit で終了しました（詳細は $rawPath）。"
}

$shouldFail = $false
if ($FailOn -eq 'High' -and $high.Count -gt 0) { $shouldFail = $true }
if ($FailOn -eq 'Medium' -and ($high.Count + $med.Count) -gt 0) { $shouldFail = $true }

if ($shouldFail) {
    throw "静的解析で危険度 $FailOn 以上の指摘が見つかりました（高=$($high.Count) / 中=$($med.Count)）。"
}

Write-Host 'Static analysis completed.'
