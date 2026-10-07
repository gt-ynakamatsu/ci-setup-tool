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

# コンソールに出る内容（dotnet / 独自コマンドの出力）はここに全文残す。失敗時の原因はほぼこの中にある。
$buildLog = Get-CiLogPath -Root $ci.Root -Name 'build-output.log'

Write-Host "==> Project: $($ci.ProjectName)"
Write-Host "==> ビルドログ: $buildLog"

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
        try {
            $code = Invoke-CiLoggedCommandLine -LogPath $buildLog -CommandLine $extra -Label "FPGA build command: $extra"
            if ($code -ne 0) { throw "Build command failed (exit code $code). 詳細ログ: $buildLog" }
            Write-Host "Build succeeded."
        }
        finally {
            # 独自コマンドでも Vivado / Quartus の .rpt 等は作業フォルダに残るので、失敗時も含めて回収する。
            Copy-CiFpgaReports -Root $ci.Root -SearchRoot $ci.Root
        }
        return
    }
    # 空白を含むパスは GUI が引用符付きで書き出すため、"..." も 1 つの値として受ける。
    if ($extra -match '(?i)-Project(?:\s+|=)("[^"]+"|\S+)') {
        $fpgaArgs += @('-Project', $Matches[1].Trim('"'))
    }
    if ($extra -match '(?i)-Tcl(?:\s+|=)("[^"]+"|\S+)') {
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
    $code = Invoke-CiLoggedCommandLine -LogPath $buildLog -CommandLine $ci.BuildCommand -Label "Custom build: $($ci.BuildCommand)"
    if ($code -ne 0) { throw "Build command failed (exit code $code). 詳細ログ: $buildLog" }
    Write-Host "Build succeeded."
    return
}

$env:DOTNET_NOLOGO = "true"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "true"

Add-CiPreviewLangVersionOverride -Root $ci.Root
try {
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
    Remove-CiPreviewLangVersionOverride -Root $ci.Root
}

Write-Host "Build succeeded."
