param(
    [string]$Configuration = "Release"
)

# Jenkins build ステージ — dotnet build または custom プロファイルの buildCommand を実行する。
$ErrorActionPreference = "Stop"
# Jenkins の自動トリガー等で CONFIGURATION が空のまま渡されると
# `dotnet build -c` の引数が欠落し MSB4126 になるため既定値で補う。
if ([string]::IsNullOrWhiteSpace($Configuration)) { $Configuration = "Release" }
. (Join-Path $PSScriptRoot 'ci-config.ps1')
$ci = Get-CiSettings
Set-Location $ci.Root

$env:CI = "true"

Write-Host "==> Project: $($ci.ProjectName)"

if ($ci.Preset -like 'fpga-*') {
    $fpga = Join-Path $PSScriptRoot 'ci-fpga.ps1'
    if (-not (Test-Path $fpga)) {
        throw "ci-fpga.ps1 が見つかりません: $fpga"
    }
    $tool = 'Vivado'
    if ($ci.Preset -eq 'fpga-quartus') { $tool = 'Quartus' }
    $fpgaArgs = @('-Tool', $tool)
    # ビルドコマンド欄の扱いは書き出しで決める。
    #   '-' 始まり  … ヘルパーへのオプション（例: -Project blink、-Tcl scripts/build.tcl）
    #   それ以外    … 利用者が用意した独自コマンド。ヘルパーを使わずそのまま実行する
    $extra = "$($ci.BuildCommand)".Trim()
    if ($extra -and -not $extra.StartsWith('-')) {
        Write-Host "==> FPGA プリセットですがビルドコマンドを優先: $extra"
        Invoke-Expression $extra
        if ($LASTEXITCODE -ne 0) { throw "Build command failed (exit code $LASTEXITCODE)." }
        Write-Host "Build succeeded."
        return
    }
    if ($extra -match '(?i)-Project(?:\s+|=)(\S+)') {
        $fpgaArgs += @('-Project', $Matches[1].Trim('"'))
    }
    if ($extra -match '(?i)-Tcl(?:\s+|=)(\S+)') {
        $fpgaArgs += @('-Tcl', $Matches[1].Trim('"'))
    }
    Write-Host "==> FPGA helper: $fpga $($fpgaArgs -join ' ')"
    & $fpga @fpgaArgs
    if ($LASTEXITCODE -ne 0) { throw "FPGA build failed (exit code $LASTEXITCODE)." }
    Write-Host "Build succeeded."
    return
}

if ($ci.Profile -eq 'custom') {
    if ([string]::IsNullOrWhiteSpace($ci.BuildCommand)) {
        throw "build.buildCommand is empty. Set a build command in the GUI (custom profile)."
    }
    Write-Host "==> Custom build: $($ci.BuildCommand)"
    Invoke-Expression $ci.BuildCommand
    if ($LASTEXITCODE -ne 0) { throw "Build command failed (exit code $LASTEXITCODE)." }
    Write-Host "Build succeeded."
    return
}

$env:DOTNET_NOLOGO = "true"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "true"

Write-Host "==> Restore"
dotnet restore $ci.SolutionFile
if ($LASTEXITCODE -ne 0) {
    throw "dotnet restore failed (exit code $LASTEXITCODE)."
}

Write-Host "==> Build"
dotnet build $ci.SolutionFile -c $Configuration --no-restore
if ($LASTEXITCODE -ne 0) {
    throw "dotnet build failed (exit code $LASTEXITCODE)."
}

Write-Host "Build succeeded."
