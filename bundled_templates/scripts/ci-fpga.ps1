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

function Test-IgnoredSearchPath {
    param([string]$Root, [string]$FullName)
    $skip = @(
        '.git', '.vs', '.idea', 'bin', 'obj', 'artifacts', 'dist',
        'node_modules', '__pycache__', 'testresults', 'packages',
        'db', 'incremental_db', 'output_files'
    )
    $rootFull = $Root.TrimEnd('\', '/')
    $rest = $FullName
    if ($FullName.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        $rest = $FullName.Substring($rootFull.Length)
    }
    $rest = $rest.TrimStart('\', '/')
    foreach ($part in ($rest -split '[\\/]')) {
        if ([string]::IsNullOrWhiteSpace($part)) { continue }
        if ($skip -contains $part.ToLowerInvariant()) { return $true }
    }
    return $false
}

function Get-RepoRelativePath {
    param([string]$Root, [string]$FullName)
    $rootFull = $Root.TrimEnd('\', '/')
    if ($FullName.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        $rel = $FullName.Substring($rootFull.Length).TrimStart('\', '/')
        if (-not [string]::IsNullOrWhiteSpace($rel)) { return ($rel -replace '\\', '/') }
    }
    return ($FullName -replace '\\', '/')
}

function Find-Files {
    param([string]$Root, [string]$Filter)
    $items = @(Get-ChildItem -Path $Root -Filter $Filter -File -Recurse -ErrorAction SilentlyContinue)
    return @($items | Where-Object { -not (Test-IgnoredSearchPath -Root $Root -FullName $_.FullName) })
}

function Resolve-SpecifiedPath {
    param([string]$Root, [string]$Specified, [string]$Extension)
    if ([string]::IsNullOrWhiteSpace($Specified)) { return $null }
    $name = $Specified
    if ($name -notlike "*$Extension") { $name = "$name$Extension" }
    if ([System.IO.Path]::IsPathRooted($Specified)) {
        if (Test-Path $name) { return (Get-Item $name) }
        if (Test-Path $Specified) { return (Get-Item $Specified) }
        return $null
    }
    $direct = Join-Path $Root $name
    if (Test-Path $direct) { return (Get-Item $direct) }
    $asGiven = Join-Path $Root $Specified
    if (Test-Path $asGiven) { return (Get-Item $asGiven) }
    return $null
}

function Resolve-QuartusProject {
    param([string]$Root, [string]$Specified)
    if (-not [string]::IsNullOrWhiteSpace($Specified)) {
        $hit = Resolve-SpecifiedPath -Root $Root -Specified $Specified -Extension '.qpf'
        if ($hit) { return $hit }
        $leaf = [System.IO.Path]::GetFileName($Specified)
        if ($leaf -notlike '*.qpf') { $leaf = "$leaf.qpf" }
        $matches = @(Find-Files -Root $Root -Filter '*.qpf' | Where-Object { $_.Name -ieq $leaf })
        if ($matches.Count -eq 1) { return $matches[0] }
        if ($matches.Count -gt 1) {
            $list = ($matches | ForEach-Object { Get-RepoRelativePath -Root $Root -FullName $_.FullName }) -join ', '
            throw "指定に合う .qpf が複数あります（$list）。-Project に相対パスを書いてください。"
        }
        throw "Quartus プロジェクトが見つかりません: $Specified"
    }
    $files = Find-Files -Root $Root -Filter '*.qpf'
    if ($files.Count -eq 0) {
        throw "リポジトリ内に .qpf がありません。Quartus プロジェクト名を GUI のビルドコマンドに「-Project 名前または相対パス」で指定してください。"
    }
    if ($files.Count -gt 1) {
        $list = ($files | ForEach-Object { Get-RepoRelativePath -Root $Root -FullName $_.FullName }) -join ', '
        throw "リポジトリ内に .qpf が複数あります（$list）。-Project で 1 つ指定してください。"
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
    $tcls = Find-Files -Root $Root -Filter 'build.tcl'
    if ($tcls.Count -eq 1) {
        return [PSCustomObject]@{ Kind = 'tcl'; Path = $tcls[0].FullName }
    }
    if ($tcls.Count -gt 1) {
        $list = ($tcls | ForEach-Object { Get-RepoRelativePath -Root $Root -FullName $_.FullName }) -join ', '
        throw "build.tcl が複数あります（$list）。-Tcl で 1 つ指定してください。"
    }
    $xprName = $SpecifiedProject
    if (-not [string]::IsNullOrWhiteSpace($xprName)) {
        $hit = Resolve-SpecifiedPath -Root $Root -Specified $xprName -Extension '.xpr'
        if ($hit) { return [PSCustomObject]@{ Kind = 'xpr'; Path = $hit.FullName } }
        $leaf = [System.IO.Path]::GetFileName($xprName)
        if ($leaf -notlike '*.xpr') { $leaf = "$leaf.xpr" }
        $matches = @(Find-Files -Root $Root -Filter '*.xpr' | Where-Object { $_.Name -ieq $leaf })
        if ($matches.Count -eq 1) { return [PSCustomObject]@{ Kind = 'xpr'; Path = $matches[0].FullName } }
        throw "Vivado プロジェクトが見つかりません: $xprName"
    }
    $xprs = Find-Files -Root $Root -Filter '*.xpr'
    if ($xprs.Count -eq 1) {
        return [PSCustomObject]@{ Kind = 'xpr'; Path = $xprs[0].FullName }
    }
    if ($xprs.Count -gt 1) {
        $list = ($xprs | ForEach-Object { Get-RepoRelativePath -Root $Root -FullName $_.FullName }) -join ', '
        throw "build.tcl が無く、.xpr が複数あります（$list）。-Tcl または -Project で指定してください。"
    }
    throw "Vivado 用の build.tcl も .xpr もリポジトリ内にありません。合成スクリプト（build.tcl）を置くか、Vivado プロジェクト（.xpr）を置いてください。"
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
    # C: が無い Linux pwsh では Join-Path が例外になるので握りつぶす。
    $roots = @()
    foreach ($spec in @(
        @('C:', 'Xilinx', 'Vivado'),
        @('D:', 'Xilinx', 'Vivado')
    )) {
        try { $roots += , (Join-PathMulti $spec[0] $spec[1..($spec.Length - 1)]) } catch { }
    }
    if (-not [string]::IsNullOrWhiteSpace(${env:ProgramFiles})) {
        try { $roots += , (Join-PathMulti ${env:ProgramFiles} @('Xilinx', 'Vivado')) } catch { }
    }
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
    $roots = @()
    foreach ($spec in @(
        @('C:', 'intelFPGA_lite'),
        @('C:', 'intelFPGA'),
        @('C:', 'altera'),
        @('D:', 'intelFPGA_lite'),
        @('D:', 'intelFPGA')
    )) {
        try { $roots += , (Join-Path $spec[0] $spec[1]) } catch { }
    }
    foreach ($root in $roots) {
        if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path $root)) { continue }
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
    $hasTcl = (Find-Files -Root $Root -Filter 'build.tcl').Count -gt 0
    if ($hasQpf -and -not $hasXpr -and -not $hasTcl) { return 'Quartus' }
    if (($hasXpr -or $hasTcl) -and -not $hasQpf) { return 'Vivado' }
    if ($hasQpf -and ($hasXpr -or $hasTcl)) {
        throw "Vivado と Quartus の両方のプロジェクトが見つかりました。プリセットでツールを選ぶか、-Tool を指定してください。"
    }
    throw "FPGA プロジェクトを自動判定できませんでした。build.tcl / .xpr（Vivado）または .qpf（Quartus）をリポジトリ内（サブフォルダ可）に置いてください。"
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
    $qpfRel = Get-RepoRelativePath -Root $root -FullName $qpf.FullName
    $exe = Find-QuartusSh
    Write-Host "==> Quartus プロジェクト: $qpfRel"
    if ($DryRun) {
        Write-Host "DRYRUN tool=Quartus project=$projName qpf=$qpfRel exe=$(if ($exe) { $exe } else { 'NOT_FOUND' })"
        exit 0
    }
    if (-not $exe) {
        throw "quartus_sh が見つかりません。エージェントに Quartus を入れ、PATH / QUARTUS_ROOTDIR を設定してください。"
    }
    Write-Host "==> $exe --flow compile $projName  (cwd=$($qpf.DirectoryName))"
    Push-Location $qpf.DirectoryName
    try {
        & $exe --flow compile $projName
        if ($LASTEXITCODE -ne 0) { throw "Quartus コンパイルが失敗しました (exit code $LASTEXITCODE)." }
    }
    finally {
        Pop-Location
    }
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

$workDir = Split-Path -Parent $vivadoIn.Path
try {
    $binDir = Split-Path -Parent $exe
    $env:PATH = $binDir + [IO.Path]::PathSeparator + $env:PATH
    Write-Host "==> $exe -mode batch -notrace -source $tclToRun  (cwd=$workDir)"
    Push-Location $workDir
    try {
        & $exe -mode batch -notrace -source $tclToRun
        if ($LASTEXITCODE -ne 0) { throw "Vivado が失敗しました (exit code $LASTEXITCODE)." }
    }
    finally {
        Pop-Location
    }
    Write-Host "Vivado ビルド成功。"
}
finally {
    if ($tempTcl -and (Test-Path $tempTcl)) {
        Remove-Item $tempTcl -Force -ErrorAction SilentlyContinue
    }
}
