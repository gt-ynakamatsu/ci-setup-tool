param(
    [string]$Configuration = "Release"
)

# Jenkins lint ステージ — dotnet format / custom lintCommand。custom で未設定ならスキップ。
$ErrorActionPreference = "Stop"
# Jenkins の自動トリガー等で CONFIGURATION が空のまま渡されると
# `dotnet build -c` の引数が欠落し MSB4126 になるため既定値で補う。
if ([string]::IsNullOrWhiteSpace($Configuration)) { $Configuration = "Release" }
. (Join-Path $PSScriptRoot 'ci-config.ps1')
$ci = Get-CiSettings
Set-Location $ci.Root

$env:CI = "true"

# コンソールに出る内容を全文残す（format / analyzer の指摘はここに出る）。
$lintLog = Get-CiLogPath -Root $ci.Root -Name 'lint-output.log'

Write-Host "==> Project: $($ci.ProjectName)"
Write-Host "==> Lint ログ: $lintLog"

if ($ci.Profile -eq 'custom') {
    if ([string]::IsNullOrWhiteSpace($ci.LintCommand)) {
        Write-Host "No custom lint command set. Skipping lint."
        return
    }
    Write-Host "==> Custom lint: $($ci.LintCommand)"
    $code = Invoke-CiLoggedCommandLine -LogPath $lintLog -CommandLine $ci.LintCommand -Label "Custom lint: $($ci.LintCommand)"
    if ($code -ne 0) { throw "Lint command failed (exit code $code). 詳細ログ: $lintLog" }
    Write-Host "Lint passed."
    return
}

$env:DOTNET_NOLOGO = "true"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "true"

Add-CiPreviewLangVersionOverride -Root $ci.Root
try {
    Write-Host "==> Restore"
    $code = Invoke-CiLogged -LogPath $lintLog -FilePath 'dotnet' -Arguments @('restore', $ci.SolutionFile) -Label 'dotnet restore'
    if ($code -ne 0) {
        throw "dotnet restore failed (exit code $code). 詳細ログ: $lintLog"
    }

    Write-Host "==> Format check"
    $code = Invoke-CiLogged -LogPath $lintLog -FilePath 'dotnet' -Arguments @('format', $ci.SolutionFile, '--verify-no-changes', '--verbosity', 'minimal') -Label 'dotnet format'
    if ($code -ne 0) {
        Write-Warning "dotnet format found issues. Run 'dotnet format $($ci.SolutionFile)' locally when you intentionally want formatting-only changes."
        Write-Warning "Continuing because CISetup treats formatting drift as a warning by default."
    }

    Write-Host "==> Build with analyzers (warnings as errors)"
    $code = Invoke-CiLogged -LogPath $lintLog -FilePath 'dotnet' -Arguments @('build', $ci.SolutionFile, '-c', $Configuration, '--no-restore') -Label 'dotnet build (analyzers)'
    if ($code -ne 0) {
        throw "dotnet build/analyzer check failed (exit code $code). 詳細ログ: $lintLog"
    }
}
finally {
    Remove-CiPreviewLangVersionOverride -Root $ci.Root
}

Write-Host "Lint passed."
