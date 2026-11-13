param(
    [string]$Configuration = "Release"
)

# Jenkins build ステージ — dotnet restore / build を実行する。
$ErrorActionPreference = "Stop"
# Jenkins の自動トリガー等で CONFIGURATION が空のまま渡されると
# `dotnet build -c` の引数が欠落し MSB4126 になるため既定値で補う。
if ([string]::IsNullOrWhiteSpace($Configuration)) { $Configuration = "Release" }
. (Join-Path $PSScriptRoot 'ci-config.ps1')
$ci = Get-CiSettings
Set-Location $ci.Root

$env:CI = "true"

# コンソールに出る内容（dotnet の出力）はここに全文残す。失敗時の原因はほぼこの中にある。
$buildLog = Get-CiLogPath -Root $ci.Root -Name 'build-output.log'

Write-Host "==> Project: $($ci.ProjectName)"
Write-Host "==> ビルドログ: $buildLog"

$env:DOTNET_NOLOGO = "true"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "true"

$dotnetSdkPin = $null
Add-CiPreviewLangVersionOverride -Root $ci.Root
try {
    $dotnetSdkPin = Enable-CiDotNetSdk -Root $ci.Root -Spec $ci.DotNetSdk
    Write-Host "==> Restore"
    $code = Invoke-CiLogged -LogPath $buildLog -FilePath 'dotnet' -Arguments @('restore', $ci.SolutionFile) -Label 'dotnet restore'
    if ($code -ne 0) {
        throw "dotnet restore failed (exit code $code). 詳細ログ: $buildLog"
    }

    Write-Host "==> Build"
    $code = Invoke-CiLogged -LogPath $buildLog -FilePath 'dotnet' -Arguments @('build', $ci.SolutionFile, '-c', $Configuration, '--no-restore') -Label 'dotnet build'
    if ($code -ne 0) {
        throw "dotnet build failed (exit code $code). 詳細ログ: $buildLog"
    }
}
finally {
    Disable-CiDotNetSdk -Path $dotnetSdkPin
    Remove-CiPreviewLangVersionOverride -Root $ci.Root
}

Write-Host "Build succeeded."
