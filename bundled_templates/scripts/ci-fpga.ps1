param(
    [ValidateSet('Auto', 'Vivado', 'Quartus')]
    [string]$Tool = 'Auto',
    [string]$Project = '',
    [string]$Tcl = '',
    [int]$Jobs = 4,
    [switch]$DryRun
)

# FPGA ビルド（Vivado / Quartus）。ci-build.ps1 からプリセット fpga-* のとき呼ばれる。
# Windows PowerShell 5.1 / pwsh 両対応。ツールが見つからない・プロジェクトが複数ある場合は明示エラー。
$ErrorActionPreference = "Stop"

function Join-PathMulti {
    param([string]$Base, [string[]]$ChildPaths)
    $result = $Base
    foreach ($child in $ChildPaths) { $result = Join-Path $result $child }
    return $result
}

function Get-RepoRoot {
    $scriptsDir = $PSScriptRoot
    $parent = Split-Path -Parent $scriptsDir
    if ((Split-Path -Leaf $parent) -ieq 'cisetup' -or (Split-Path -Leaf $parent) -ieq 'CISetup') {
        $root = Split-Path -Parent $parent
        if ([string]::IsNullOrWhiteSpace($root)) { return $parent }
        return $root
    }
    return $parent
}

function Find-Files {
    param([string]$Root, [string]$Filter)
    return @(Get-ChildItem -Path $Root -Filter $Filter -File -ErrorAction SilentlyContinue)
}

function Resolve-QuartusProject {
    param([string]$Root, [string]$Specified)
    if (-not [string]::IsNullOrWhiteSpace($Specified)) {
        $name = $Specified
        if ($name -notlike '*.qpf') { $name = "$name.qpf" }
        $path = if ([System.IO.Path]::IsPathRooted($Specified)) { $Specified } else { Join-Path $Root $name }
        if (-not (Test-Path $path)) {
            throw "Quartus プロジェクトが見つかりません: $path"
        }
        return (Get-Item $path)
    }
    $files = Find-Files -Root $Root -Filter '*.qpf'
    if ($files.Count -eq 0) {
        throw "リポジトリ直下に .qpf がありません。Quartus プロジェクト名を GUI のビルドコマンドに「-Project 名前」で指定するか、.qpf を直下に置いてください。"
    }
    if ($files.Count -gt 1) {
        $list = ($files | ForEach-Object { $_.Name }) -join ', '
        throw "リポジトリ直下に .qpf が複数あります（$list）。-Project で 1 つ指定してください。"
    }
    return $files[0]
}

function Resolve-VivadoInputs {
    param([string]$Root, [string]$SpecifiedTcl, [string]$SpecifiedProject)
    $tcl = $SpecifiedTcl
    if (-not [string]::IsNullOrWhiteSpace($tcl) -and -not [System.IO.Path]::IsPathRooted($tcl)) {
        $tcl = Join-Path $Root $tcl
    }
    if (-not [string]::IsNullOrWhiteSpace($tcl)) {
        if (-not (Test-Path $tcl)) { throw "Vivado Tcl が見つかりません: $tcl" }
        return [PSCustomObject]@{ Kind = 'tcl'; Path = $tcl }
    }
    $defaultTcl = Join-Path $Root 'build.tcl'
    if (Test-Path $defaultTcl) {
        return [PSCustomObject]@{ Kind = 'tcl'; Path = $defaultTcl }
    }
    $xprName = $SpecifiedProject
    if (-not [string]::IsNullOrWhiteSpace($xprName)) {
        if ($xprName -notlike '*.xpr') { $xprName = "$xprName.xpr" }
        $xprPath = if ([System.IO.Path]::IsPathRooted($SpecifiedProject)) { $SpecifiedProject } else { Join-Path $Root $xprName }
        if (-not (Test-Path $xprPath)) { throw "Vivado プロジェクトが見つかりません: $xprPath" }
        return [PSCustomObject]@{ Kind = 'xpr'; Path = $xprPath }
    }
    $xprs = Find-Files -Root $Root -Filter '*.xpr'
    if ($xprs.Count -eq 1) {
        return [PSCustomObject]@{ Kind = 'xpr'; Path = $xprs[0].FullName }
    }
    if ($xprs.Count -gt 1) {
        $list = ($xprs | ForEach-Object { $_.Name }) -join ', '
        throw "build.tcl が無く、.xpr が複数あります（$list）。-Tcl または -Project で指定してください。"
    }
    throw "Vivado 用の build.tcl も .xpr もリポジトリ直下にありません。合成スクリプト（build.tcl）を置くか、Vivado プロジェクト（.xpr）を直下に置いてください。"
}

function Find-VivadoExe {
    $cmd = Get-Command vivado -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($envName in @('XILINX_VIVADO', 'VIVADO_PATH')) {
        $base = [Environment]::GetEnvironmentVariable($envName)
        if ([string]::IsNullOrWhiteSpace($base)) { continue }
        foreach ($rel in @(
            $base,
            (Join-PathMulti $base @('bin', 'vivado')),
            (Join-PathMulti $base @('bin', 'vivado.bat'))
        )) {
            if ((Test-Path $rel) -and -not (Test-Path $rel -PathType Container)) {
                return (Get-Item $rel).FullName
            }
        }
    }
    # 区切り文字は Join-Path に任せる（'\' 決め打ちは pwsh on Linux で壊れるため）。
    $roots = @(
        (Join-PathMulti 'C:' @('Xilinx', 'Vivado')),
        (Join-PathMulti 'D:' @('Xilinx', 'Vivado')),
        (Join-PathMulti ${env:ProgramFiles} @('Xilinx', 'Vivado'))
    )
    foreach ($root in $roots) {
        if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path $root)) { continue }
        $versions = @(Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending)
        foreach ($ver in $versions) {
            foreach ($leaf in @('vivado.bat', 'vivado')) {
                $candidate = Join-PathMulti $ver.FullName @('bin', $leaf)
                if (Test-Path $candidate) { return (Get-Item $candidate).FullName }
            }
        }
    }
    return $null
}

function Find-QuartusSh {
    $cmd = Get-Command quartus_sh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($envName in @('QUARTUS_ROOTDIR', 'QSYS_ROOTDIR')) {
        $base = [Environment]::GetEnvironmentVariable($envName)
        if ([string]::IsNullOrWhiteSpace($base)) { continue }
        foreach ($rel in @(
            (Join-Path $base 'quartus_sh'),
            (Join-Path $base 'quartus_sh.exe'),
            (Join-PathMulti $base @('bin64', 'quartus_sh.exe')),
            (Join-PathMulti $base @('bin', 'quartus_sh.exe')),
            (Join-PathMulti $base @('quartus', 'bin64', 'quartus_sh.exe'))
        )) {
            if (Test-Path $rel) { return (Get-Item $rel).FullName }
        }
    }
    $roots = @(
        (Join-Path 'C:' 'intelFPGA_lite'),
        (Join-Path 'C:' 'intelFPGA'),
        (Join-Path 'C:' 'altera'),
        (Join-Path 'D:' 'intelFPGA_lite'),
        (Join-Path 'D:' 'intelFPGA')
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        $versions = @(Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending)
        foreach ($ver in $versions) {
            foreach ($rel in @(
                (Join-PathMulti $ver.FullName @('quartus', 'bin64', 'quartus_sh.exe')),
                (Join-PathMulti $ver.FullName @('quartus', 'bin', 'quartus_sh.exe'))
            )) {
                if (Test-Path $rel) { return (Get-Item $rel).FullName }
            }
        }
    }
    return $null
}

function Detect-Tool {
    param([string]$Root, [string]$Requested)
    if ($Requested -ne 'Auto') { return $Requested }
    $hasQpf = (Find-Files -Root $Root -Filter '*.qpf').Count -gt 0
    $hasXpr = (Find-Files -Root $Root -Filter '*.xpr').Count -gt 0
    $hasTcl = Test-Path (Join-Path $Root 'build.tcl')
    if ($hasQpf -and -not $hasXpr -and -not $hasTcl) { return 'Quartus' }
    if (($hasXpr -or $hasTcl) -and -not $hasQpf) { return 'Vivado' }
    if ($hasQpf -and ($hasXpr -or $hasTcl)) {
        throw "Vivado と Quartus の両方のプロジェクトが見つかりました。プリセットでツールを選ぶか、-Tool を指定してください。"
    }
    throw "FPGA プロジェクトを自動判定できませんでした。build.tcl / .xpr（Vivado）または .qpf（Quartus）をリポジトリ直下に置いてください。"
}

function Write-VivadoXprTcl {
    param([string]$XprPath, [string]$OutTcl, [int]$JobCount)
    $escaped = $XprPath -replace '\\', '/'
    @"
set_param general.maxThreads $JobCount
open_project {$escaped}
if {[llength [get_runs impl_1]] == 0} {
    error "Run impl_1 が見つかりません。GUI で実装ランを作るか、build.tcl を用意してください。"
}
reset_run impl_1
launch_runs impl_1 -to_step write_bitstream -jobs $JobCount
wait_on_run impl_1
set st [get_property STATUS [get_runs impl_1]]
puts "impl_1 STATUS=`$st"
if {[string match -nocase "*ERROR*" `$st]} {
    error "Vivado impl_1 が失敗しました: `$st"
}
"@ | Set-Content -Path $OutTcl -Encoding UTF8
}

$root = Get-RepoRoot
Set-Location $root
Write-Host "==> FPGA CI  root=$root  tool=$Tool"

$resolvedTool = Detect-Tool -Root $root -Requested $Tool
Write-Host "==> 使用ツール: $resolvedTool"

if ($resolvedTool -eq 'Quartus') {
    $qpf = Resolve-QuartusProject -Root $root -Specified $Project
    $projName = [System.IO.Path]::GetFileNameWithoutExtension($qpf.Name)
    $exe = Find-QuartusSh
    Write-Host "==> Quartus プロジェクト: $($qpf.Name)"
    if ($DryRun) {
        Write-Host "DRYRUN tool=Quartus project=$projName exe=$(if ($exe) { $exe } else { 'NOT_FOUND' })"
        exit 0
    }
    if (-not $exe) {
        throw "quartus_sh が見つかりません。エージェントに Quartus を入れ、PATH / QUARTUS_ROOTDIR を設定してください。"
    }
    Write-Host "==> $exe --flow compile $projName"
    & $exe --flow compile $projName
    if ($LASTEXITCODE -ne 0) { throw "Quartus コンパイルが失敗しました (exit code $LASTEXITCODE)." }
    Write-Host "Quartus ビルド成功。"
    exit 0
}

$vivadoIn = Resolve-VivadoInputs -Root $root -SpecifiedTcl $Tcl -SpecifiedProject $Project
$exe = Find-VivadoExe
Write-Host "==> Vivado 入力: $($vivadoIn.Kind) $($vivadoIn.Path)"
if ($DryRun) {
    Write-Host "DRYRUN tool=Vivado kind=$($vivadoIn.Kind) path=$($vivadoIn.Path) exe=$(if ($exe) { $exe } else { 'NOT_FOUND' })"
    exit 0
}
if (-not $exe) {
    throw "vivado が見つかりません。エージェントに Vivado を入れ、PATH / XILINX_VIVADO を設定してください。"
}

$tclToRun = $vivadoIn.Path
$tempTcl = $null
if ($vivadoIn.Kind -eq 'xpr') {
    $tempTcl = Join-Path $root ('.ci-fpga-impl.tcl')
    Write-VivadoXprTcl -XprPath $vivadoIn.Path -OutTcl $tempTcl -JobCount $Jobs
    $tclToRun = $tempTcl
}

try {
    $binDir = Split-Path -Parent $exe
    $env:PATH = $binDir + [IO.Path]::PathSeparator + $env:PATH
    Write-Host "==> $exe -mode batch -notrace -source $tclToRun"
    & $exe -mode batch -notrace -source $tclToRun
    if ($LASTEXITCODE -ne 0) { throw "Vivado が失敗しました (exit code $LASTEXITCODE)." }
    Write-Host "Vivado ビルド成功。"
}
finally {
    if ($tempTcl -and (Test-Path $tempTcl)) {
        Remove-Item $tempTcl -Force -ErrorAction SilentlyContinue
    }
}
