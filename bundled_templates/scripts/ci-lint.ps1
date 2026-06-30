param(
    [string]$Configuration = "Release"
)

# Jenkins lint ステージ — dotnet format / custom lintCommand。custom で未設定ならスキップ。
$ErrorActionPreference = "Stop"
# Jenkins の自動トリガー等で CONFIGURATION が空のまま渡されると
# `dotnet build -c` の引数が欠落し MSB4126 になるため既定値で補う。
if ([string]::IsNullOrWhiteSpace($Configuration)) { $Configuration = "Release" }
. "$PSScriptRoot\ci-config.ps1"
$ci = Get-CiSettings
Set-Location $ci.Root

$env:CI = "true"

Write-Host "==> Project: $($ci.ProjectName)"

if ($ci.Profile -eq 'custom') {
    if ([string]::IsNullOrWhiteSpace($ci.LintCommand)) {
        Write-Host "No custom lint command set. Skipping lint."
        return
    }
    Write-Host "==> Custom lint: $($ci.LintCommand)"
    Invoke-Expression $ci.LintCommand
    if ($LASTEXITCODE -ne 0) { throw "Lint command failed (exit code $LASTEXITCODE)." }
    Write-Host "Lint passed."
    return
}

$env:DOTNET_NOLOGO = "true"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "true"

Write-Host "==> Restore"
dotnet restore $ci.SolutionFile
if ($LASTEXITCODE -ne 0) {
    throw "dotnet restore failed (exit code $LASTEXITCODE)."
}

Write-Host "==> Format check"
dotnet format $ci.SolutionFile --verify-no-changes --verbosity minimal
if ($LASTEXITCODE -ne 0) {
    Write-Warning "dotnet format found issues. Run 'dotnet format $($ci.SolutionFile)' locally when you intentionally want formatting-only changes."
    Write-Warning "Continuing because CISetup treats formatting drift as a warning by default."
}

Write-Host "==> Build with analyzers (warnings as errors)"
dotnet build $ci.SolutionFile -c $Configuration --no-restore
if ($LASTEXITCODE -ne 0) {
    throw "dotnet build/analyzer check failed (exit code $LASTEXITCODE)."
}

Write-Host "Lint passed."
