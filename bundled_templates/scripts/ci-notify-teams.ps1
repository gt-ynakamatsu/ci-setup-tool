param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('complete', 'error')]
    [string]$Status,

    [Parameter(Mandatory = $true)]
    [string]$BuildNumber,

    [string]$JobName = $env:JOB_NAME,
    [string]$BuildUrl = '',
    [string]$Branch = '',
    [string]$Commit = '',
    [string]$WebhookUrl = $env:TEAMS_WEBHOOK_URL,

    # 確認用: 生成した Teams ペイロード JSON をこのパスに保存する（送信はしない確認も可）。
    [string]$OutFile = ''
)

# Jenkins post ステージ — Teams 通知（1 枚のアダプティブ カード）。
# TEAMS_WEBHOOK_URL は Jenkins Credentials から注入。
# ユニットテスト失敗時のみ、失敗したテスト名とユニットテストログへのリンクボタンをカードに載せる。
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ci-config.ps1')
$ci = Get-CiSettings

# ---- ファイルサーバー配置先（ci-deploy-fileserver.ps1 が出力したマニフェスト）----
$deploy = $null
$manifestPath = Join-PathMulti $ci.Root @('artifacts', 'deploy-manifest.json')
if (Test-Path $manifestPath) {
    try {
        $m = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($m -and "$($m.buildNumber)" -eq "$BuildNumber") { $deploy = $m }
    }
    catch {
        Write-Warning "Failed to read deploy manifest: $_"
    }
}

function ConvertTo-FileUri {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    if ($Path -like '\\*') {
        # UNC パス（\\server\share\...）
        return 'file:' + ($Path -replace '\\', '/')
    }
    if ($Path -like '/*') {
        # Linux 等の絶対パス（先頭が "/"）はそのまま file:// を付与する。
        return 'file://' + $Path
    }
    return 'file:///' + ($Path -replace '\\', '/')
}

function Add-LinkActions {
    # 複数の閲覧 URL をそれぞれボタン化する。2 件以上なら連番を付ける。
    # URL が無ければ Fallback（配置先の file: URI など）を 1 つだけボタン化する。
    param($Actions, [string]$Title, $Urls, [string]$Fallback)
    $list = ConvertTo-StringArray $Urls
    if ($list.Count -eq 0) {
        if (-not [string]::IsNullOrWhiteSpace($Fallback)) {
            $Actions.Add(@{ type = 'Action.OpenUrl'; title = $Title; url = $Fallback }) | Out-Null
        }
        return
    }
    if ($list.Count -eq 1) {
        $Actions.Add(@{ type = 'Action.OpenUrl'; title = $Title; url = $list[0] }) | Out-Null
        return
    }
    for ($i = 0; $i -lt $list.Count; $i++) {
        $Actions.Add(@{ type = 'Action.OpenUrl'; title = "$Title ($($i + 1))"; url = $list[$i] }) | Out-Null
    }
}

if ([string]::IsNullOrWhiteSpace($WebhookUrl) -and [string]::IsNullOrWhiteSpace($OutFile)) {
    Write-Warning 'TEAMS_WEBHOOK_URL is not set. Skipping Teams notification.'
    exit 0
}

$displayName = if ($JobName) { $JobName } else { $ci.ProjectName }
$isSuccess = $Status -eq 'complete'
$headerStyle = if ($isSuccess) { 'good' } else { 'attention' }
$headline = if ($isSuccess) { "✅ ビルド成功" } else { "❌ ビルド失敗" }

$facts = @(
    @{ title = 'プロジェクト'; value = $ci.ProjectName }
    @{ title = 'ジョブ / ビルド'; value = "$displayName #$BuildNumber" }
    @{ title = '日時'; value = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') }
)
if ($Branch) { $facts += @{ title = 'ブランチ'; value = $Branch } }
if ($Commit) {
    $facts += @{ title = 'コミット'; value = $Commit }
}
if ($BuildUrl) { $facts += @{ title = 'Jenkins'; value = $BuildUrl } }

$body = @(
    @{
        type  = 'Container'
        style = $headerStyle
        bleed = $true
        items = @(
            @{ type = 'TextBlock'; size = 'Large'; weight = 'Bolder'; text = $headline; wrap = $true }
            @{ type = 'TextBlock'; spacing = 'None'; isSubtle = $true; text = "$displayName #$BuildNumber"; wrap = $true }
        )
    }
    @{ type = 'FactSet'; facts = $facts }
)

$hasAnalysis = $false
$analysisFallback = ''
$hasTestFailure = $false
$testFallback = ''

# ---- 静的解析サマリー ----
$summaryPath = Join-PathMulti $ci.Root @('artifacts', 'analysis', 'analysis-summary.json')
if ($ci.EnableAnalysis -and (Test-Path $summaryPath)) {
    try {
        $summary = Get-Content $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $analysisColor = if ($summary.high -gt 0) { 'Attention' } elseif ($summary.medium -gt 0) { 'Warning' } else { 'Good' }
        $body += @{
            type   = 'TextBlock'
            weight = 'Bolder'
            color  = $analysisColor
            wrap   = $true
            text   = "静的解析  高 $($summary.high) ・ 中 $($summary.medium) ・ 低 $($summary.low)"
        }
        $hasAnalysis = $true
        if ($deploy -and $deploy.analysisReport) { $analysisFallback = ConvertTo-FileUri $deploy.analysisReport }
    }
    catch {
        Write-Warning "Failed to read analysis summary: $_"
    }
}

# ---- ユニットテスト（失敗時のみテスト名とログリンク） ----
$testSummaryPath = Join-PathMulti $ci.Root @('artifacts', 'test', 'test-summary.json')
if ($ci.EnableTests -and (Test-Path $testSummaryPath)) {
    try {
        $ts = Get-Content $testSummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $testColor = if ($ts.failed -gt 0) { 'Attention' } elseif ($ts.total -eq 0) { 'Default' } else { 'Good' }
        $body += @{
            type   = 'TextBlock'
            weight = 'Bolder'
            color  = $testColor
            wrap   = $true
            text   = "ユニットテスト  成功 $($ts.passed) / 失敗 $($ts.failed) / 合計 $($ts.total)"
        }

        $items = @($ts.tests)
        $failed = @($items | Where-Object { $_.outcome -eq 'Failed' })

        if ($failed.Count -gt 0) {
            $hasTestFailure = $true
            if ($deploy -and $deploy.testFailureLog) { $testFallback = ConvertTo-FileUri $deploy.testFailureLog }
            elseif ($deploy -and $deploy.testDir) { $testFallback = ConvertTo-FileUri $deploy.testDir }

            $testLines = [System.Collections.Generic.List[string]]::new()
            $maxShow = 40
            for ($i = 0; $i -lt $failed.Count; $i++) {
                if ($i -ge $maxShow) { break }
                $testLines.Add("❌ $($failed[$i].name)")
            }
            if ($failed.Count -gt $maxShow) {
                $testLines.Add("... 他 $($failed.Count - $maxShow) 件失敗")
            }

            $body += @{
                type     = 'TextBlock'
                weight   = 'Bolder'
                color    = 'Attention'
                wrap     = $true
                spacing  = 'Small'
                text     = '失敗したテスト:'
            }
            $body += @{
                type     = 'TextBlock'
                wrap     = $true
                fontType = 'Monospace'
                spacing  = 'Small'
                color    = 'Attention'
                text     = ($testLines -join "`n")
            }
        }
        elseif ($items.Count -gt 0) {
            $body += @{
                type     = 'TextBlock'
                isSubtle = $true
                wrap     = $true
                text     = 'すべてのテストが成功しました'
            }
        }
    }
    catch {
        Write-Warning "Failed to read test summary: $_"
    }
}

if (-not $isSuccess -and $ci.EnableLogs) {
    $body += @{
        type  = 'TextBlock'
        color = 'Attention'
        wrap  = $true
        text  = "ビルドログ: 設定済みの書き込み先（$($ci.ProjectName) の logs フォルダ）を確認してください。"
    }
}

$actions = New-Object System.Collections.Generic.List[object]
if ($hasAnalysis -and $ci.EnableAnalysis) {
    Add-LinkActions -Actions $actions -Title '解析レポート (HTML)' -Urls $ci.AnalysisUrls -Fallback $analysisFallback
}
if ($hasTestFailure -and $ci.EnableTests) {
    Add-LinkActions -Actions $actions -Title 'ユニットテストログを開く' -Urls $ci.TestsUrls -Fallback $testFallback
}
if ($deploy -and $deploy.artifactDir -and $ci.EnableReleases) {
    Add-LinkActions -Actions $actions -Title '成果物フォルダを開く' -Urls $ci.ReleaseUrls -Fallback (ConvertTo-FileUri $deploy.artifactDir)
}
if ($deploy -and $deploy.sourceDir -and $ci.ArchiveSource) {
    Add-LinkActions -Actions $actions -Title '開発環境 zip を開く' -Urls $ci.SourceUrls -Fallback (ConvertTo-FileUri $deploy.sourceDir)
}
if (-not $isSuccess -and $ci.EnableLogs -and $ci.LogsUrls.Count -gt 0) {
    Add-LinkActions -Actions $actions -Title 'ログフォルダを開く' -Urls $ci.LogsUrls -Fallback ''
}

$card = @{
    type      = 'AdaptiveCard'
    '$schema' = 'http://adaptivecards.io/schemas/adaptive-card.json'
    version   = '1.4'
    body      = $body
    msteams   = @{ width = 'Full' }
}
# NOTE: Windows PowerShell 5.1 では、関数内で要素を追加した List[object] を
# @(...) で配列化すると "Argument types do not match" になる既知の不具合がある。
# ToArray() を使って回避する。
if ($actions.Count -gt 0) { $card.actions = $actions.ToArray() }

$payloadObj = [ordered]@{
    type        = 'message'
    attachments = @(
        @{
            contentType = 'application/vnd.microsoft.card.adaptive'
            content     = $card
        }
    )
}

$payload = $payloadObj | ConvertTo-Json -Depth 25

if (-not [string]::IsNullOrWhiteSpace($OutFile)) {
    $payload | Set-Content -Path $OutFile -Encoding UTF8
    Write-Host "Payload written to $OutFile"
}

if ([string]::IsNullOrWhiteSpace($WebhookUrl)) {
    return
}

try {
    Invoke-RestMethod -Uri $WebhookUrl -Method Post -Body $payload -ContentType 'application/json; charset=utf-8'
    Write-Host "Teams notification sent: $Status"
}
catch {
    Write-Warning "Failed to send Teams notification: $_"
    exit 0
}
