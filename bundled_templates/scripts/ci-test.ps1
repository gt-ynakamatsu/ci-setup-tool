param(
    [string]$Configuration = "Release"
)

# Jenkins test ステージ — dotnet test（TRX 出力）または custom testCommand を実行する。
$ErrorActionPreference = "Stop"
# Jenkins の自動トリガー等で CONFIGURATION が空のまま渡されると
# `dotnet test -c` の引数が欠落し MSB4126 になるため既定値で補う。
if ([string]::IsNullOrWhiteSpace($Configuration)) { $Configuration = "Release" }
. "$PSScriptRoot\ci-config.ps1"
$ci = Get-CiSettings
Set-Location $ci.Root

$env:CI = "true"

Write-Host "==> Project: $($ci.ProjectName)"

if ($ci.Profile -eq 'custom') {
    if ([string]::IsNullOrWhiteSpace($ci.TestCommand)) {
        Write-Host "No custom test command set. Skipping tests."
        exit 0
    }
    Write-Host "==> Custom test: $($ci.TestCommand)"
    Invoke-Expression $ci.TestCommand
    if ($LASTEXITCODE -ne 0) { throw "Test command failed (exit code $LASTEXITCODE)." }
    Write-Host "Tests passed."
    return
}

if ([string]::IsNullOrWhiteSpace($ci.TestProject)) {
    Write-Host "No test project selected (project.testProject is empty). Skipping unit tests."
    exit 0
}

$testDir = Join-Path $ci.Root 'artifacts\test'
New-Item -ItemType Directory -Force -Path $testDir | Out-Null
$trxPath = Join-Path $testDir 'test-results.trx'
$summaryPath = Join-Path $testDir 'test-summary.json'
$failureLogPath = Join-Path $testDir 'test-failures.log'

function Import-TrxDetails {
    param([string]$Path)

    $counters = @{ Total = 0; Passed = 0; Failed = 0; Skipped = 0 }
    $tests = [System.Collections.Generic.List[object]]::new()

    if (-not (Test-Path $Path)) {
        return @{ Counters = $counters; Tests = $tests }
    }

    try {
        [xml]$trx = Get-Content $Path -Encoding UTF8
        $c = $trx.TestRun.ResultSummary.Counters
        if ($c) {
            $skipped = 0
            if ($null -ne $c.notExecuted) { $skipped = [int]$c.notExecuted }
            $counters = @{
                Total   = [int]$c.total
                Passed  = [int]$c.passed
                Failed  = [int]$c.failed
                Skipped = $skipped
            }
        }

        $unitResults = $trx.TestRun.Results.UnitTestResult
        if (-not $unitResults) {
            return @{ Counters = $counters; Tests = $tests }
        }

        if ($unitResults -isnot [System.Array]) {
            $unitResults = @($unitResults)
        }

        foreach ($utr in $unitResults) {
            $name = [string]$utr.testName
            $outcome = [string]$utr.outcome
            if ([string]::IsNullOrWhiteSpace($name)) { continue }

            $item = [ordered]@{
                name    = $name
                outcome = $outcome
            }

            if ($outcome -eq 'Failed') {
                $err = $utr.Output.ErrorInfo
                if ($err) {
                    $msg = [string]$err.Message
                    $stack = [string]$err.StackTrace
                    if (-not [string]::IsNullOrWhiteSpace($msg)) { $item.message = $msg.Trim() }
                    if (-not [string]::IsNullOrWhiteSpace($stack)) { $item.stackTrace = $stack.Trim() }
                }
            }

            $tests.Add($item)
        }
    }
    catch {
        Write-Warning "Failed to parse TRX: $_"
    }

    return @{ Counters = $counters; Tests = $tests }
}

function Write-TestSummary {
    param(
        [hashtable]$Counters,
        [System.Collections.Generic.List[object]]$Tests,
        [string]$TrxFile
    )

    @{
        total   = $Counters.Total
        passed  = $Counters.Passed
        failed  = $Counters.Failed
        skipped = $Counters.Skipped
        trxFile = $TrxFile
        tests   = @($Tests)
    } | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryPath -Encoding UTF8
}

function Write-FailureLog {
    param(
        [System.Collections.Generic.List[object]]$Tests,
        [string]$Path
    )

    $failed = @($Tests | Where-Object { $_.outcome -eq 'Failed' })
    if ($failed.Count -eq 0) {
        if (Test-Path $Path) { Remove-Item $Path -Force }
        return
    }

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("Unit test failures - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    [void]$sb.AppendLine("Project: $($ci.ProjectName)")
    [void]$sb.AppendLine("Test project: $($ci.TestProject)")
    [void]$sb.AppendLine('')

    foreach ($t in $failed) {
        [void]$sb.AppendLine("================================================================================")
        [void]$sb.AppendLine("FAILED: $($t.name)")
        if ($t.message) {
            [void]$sb.AppendLine('')
            [void]$sb.AppendLine([string]$t.message)
        }
        if ($t.stackTrace) {
            [void]$sb.AppendLine('')
            [void]$sb.AppendLine([string]$t.stackTrace)
        }
        [void]$sb.AppendLine('')
    }

    $sb.ToString() | Set-Content -Path $Path -Encoding UTF8
}

Write-Host "==> dotnet test ($($ci.TestProject))"
dotnet test $ci.TestProject -c $Configuration --no-build `
    --results-directory $testDir `
    --logger "trx;LogFileName=test-results.trx" `
    --logger "console;verbosity=normal"
$exitCode = $LASTEXITCODE

$parsed = Import-TrxDetails $trxPath
Write-TestSummary -Counters $parsed.Counters -Tests $parsed.Tests -TrxFile $trxPath
Write-FailureLog -Tests $parsed.Tests -Path $failureLogPath

Write-Host ''
Write-Host '====================== テスト結果 ======================'
Write-Host ("  合計   : {0}" -f $parsed.Counters.Total)
Write-Host ("  成功   : {0}" -f $parsed.Counters.Passed)
Write-Host ("  失敗   : {0}" -f $parsed.Counters.Failed)
Write-Host ("  スキップ: {0}" -f $parsed.Counters.Skipped)
Write-Host ("  TRX    : $trxPath")
if (Test-Path $failureLogPath) {
    Write-Host ("  失敗ログ: $failureLogPath")
}
Write-Host '----------------------------------------------------------'
foreach ($t in $parsed.Tests) {
    if ($t.outcome -eq 'Passed') { $mark = '[OK]' }
    elseif ($t.outcome -eq 'Failed') { $mark = '[NG]' }
    else { $mark = "[ $($t.outcome) ]" }
    Write-Host "  $mark $($t.name)"
}
Write-Host '=========================================================='

if ($exitCode -ne 0) {
    throw "dotnet test failed (exit code $exitCode)."
}

Write-Host "All tests passed."
