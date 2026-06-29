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
. "$PSScriptRoot\ci-config.ps1"
$ci = Get-CiSettings

# ---- ファイルサーバー配置先（ci-deploy-fileserver.ps1 が出力したマニフェスト）----
$deploy = $null
$manifestPath = Join-Path $ci.Root 'artifacts\deploy-manifest.json'
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
        return 'file:' + ($Path -replace '\\', '/')
    }
    return 'file:///' + ($Path -replace '\\', '/')
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
    $shortCommit = if ($Commit.Length -gt 8) { $Commit.Substring(0, 8) } else { $Commit }
    $facts += @{ title = 'コミット'; value = $shortCommit }
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

$reportUrl = ''
$testReportUrl = ''

# ---- 静的解析サマリー ----
$summaryPath = Join-Path $ci.Root 'artifacts\analysis\analysis-summary.json'
if (Test-Path $summaryPath) {
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
        if ($ci.AnalysisUrl) { $reportUrl = $ci.AnalysisUrl }
        elseif ($deploy -and $deploy.analysisReport) { $reportUrl = ConvertTo-FileUri $deploy.analysisReport }
    }
    catch {
        Write-Warning "Failed to read analysis summary: $_"
    }
}

# ---- ユニットテスト（失敗時のみテスト名とログリンク） ----
$testSummaryPath = Join-Path $ci.Root 'artifacts\test\test-summary.json'
if (Test-Path $testSummaryPath) {
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
            if ($ci.TestsUrl) { $testReportUrl = $ci.TestsUrl }
            elseif ($deploy -and $deploy.testFailureLog) { $testReportUrl = ConvertTo-FileUri $deploy.testFailureLog }
            elseif ($deploy -and $deploy.testDir) { $testReportUrl = ConvertTo-FileUri $deploy.testDir }

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

if (-not $isSuccess) {
    $body += @{
        type  = 'TextBlock'
        color = 'Attention'
        wrap  = $true
        text  = "ビルドログ: 社内ファイルサーバー \\…\\$($ci.ProjectName)\logs\ を確認してください。"
    }
}

$actions = @()
if ($reportUrl) {
    $actions += @{ type = 'Action.OpenUrl'; title = '解析レポート (HTML)'; url = $reportUrl }
}
if ($testReportUrl) {
    $actions += @{ type = 'Action.OpenUrl'; title = 'ユニットテストログを開く'; url = $testReportUrl }
}
if ($deploy -and $deploy.artifactDir) {
    $artifactUrl = if ($ci.ReleaseUrl) { $ci.ReleaseUrl } else { ConvertTo-FileUri $deploy.artifactDir }
    $actions += @{ type = 'Action.OpenUrl'; title = '成果物フォルダを開く'; url = $artifactUrl }
}
if (-not $isSuccess -and $ci.LogsUrl) {
    $actions += @{ type = 'Action.OpenUrl'; title = 'ログフォルダを開く'; url = $ci.LogsUrl }
}

$card = @{
    type      = 'AdaptiveCard'
    '$schema' = 'http://adaptivecards.io/schemas/adaptive-card.json'
    version   = '1.4'
    body      = $body
    msteams   = @{ width = 'Full' }
}
if ($actions.Count -gt 0) { $card.actions = $actions }

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
