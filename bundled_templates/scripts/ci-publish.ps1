param(
    [string]$Configuration = "Release",
    [string]$Version = ""
)

# Jenkins publish ステージ — dotnet publish / custom publishCommand。PUBLISH_RELEASE=false ならスキップ。
$ErrorActionPreference = "Stop"
# Jenkins の自動トリガー等で CONFIGURATION が空のまま渡されると
# `dotnet build -c` の引数が欠落し MSB4126 になるため既定値で補う。
if ([string]::IsNullOrWhiteSpace($Configuration)) { $Configuration = "Release" }
. (Join-Path $PSScriptRoot 'ci-config.ps1')
$ci = Get-CiSettings
Set-Location $ci.Root

$env:CI = "true"

Write-Host "==> Project: $($ci.ProjectName)"

if ($ci.Profile -eq 'custom') {
    $releaseDir = Join-PathMulti $ci.Root @('artifacts', 'release')
    if (Test-Path $releaseDir) { Remove-Item -Recurse -Force $releaseDir }
    New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

    if (-not [string]::IsNullOrWhiteSpace($ci.PublishCommand)) {
        Write-Host "==> Custom publish: $($ci.PublishCommand)"
        Invoke-Expression $ci.PublishCommand
        if ($LASTEXITCODE -ne 0) { throw "Publish command failed (exit code $LASTEXITCODE)." }
    }

    if ([string]::IsNullOrWhiteSpace($ci.ArtifactGlob)) {
        Write-Warning "build.artifactGlob is empty. Nothing collected for release."
        return
    }

    # Convert glob (* ? **) to regex. '**' spans directory levels.
    function Convert-GlobToRegex {
        param([string]$Glob)
        $g = ($Glob -replace '\\', '/').TrimStart('/')
        $p = [regex]::Escape($g)
        $p = $p -replace '\\\*\\\*/', '(?:.*/)?'   # '**/' => zero or more dirs
        $p = $p -replace '\\\*\\\*', '.*'          # '**'  => anything
        $p = $p -replace '\\\*', '[^/]*'           # '*'   => non-slash
        $p = $p -replace '\\\?', '.'               # '?'   => one char
        return "^$p$"
    }

    $patterns = $ci.ArtifactGlob -split '[;,]' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $regexes = $patterns | ForEach-Object { Convert-GlobToRegex $_ }

    $allFiles = Get-ChildItem -Path $ci.Root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '[\\/]artifacts[\\/]release[\\/]' }

    $matched = @()
    foreach ($file in $allFiles) {
        $rel = $file.FullName.Substring($ci.Root.Length).TrimStart('\', '/') -replace '\\', '/'
        foreach ($rx in $regexes) {
            if ($rel -imatch $rx) {
                $matched += $file
                break
            }
        }
    }
    $matched = @($matched | Sort-Object FullName -Unique)

    if ($matched.Count -eq 0) {
        Write-Warning "artifactGlob '$($ci.ArtifactGlob)' matched no files."
        return
    }

    $prefix = $ci.ArtifactPrefix
    $zipName = if ($Version) { "$prefix-$Version.zip" } else { "$prefix.zip" }
    $zipPath = Join-Path $releaseDir $zipName
    Compress-Archive -Path $matched.FullName -DestinationPath $zipPath -Force
    Write-Host "Archived $($matched.Count) file(s) to $zipPath"
    return
}

$env:DOTNET_NOLOGO = "true"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "true"

$publishDir = Join-PathMulti $ci.Root @('artifacts', 'publish')
$releaseDir = Join-PathMulti $ci.Root @('artifacts', 'release')

if (Test-Path $publishDir) {
    Remove-Item -Recurse -Force $publishDir
}

if (Test-Path $releaseDir) {
    Remove-Item -Recurse -Force $releaseDir
}

New-Item -ItemType Directory -Force -Path $publishDir, $releaseDir | Out-Null

# publishProject はリポジトリルートからの相対パス想定。存在しない場合は MSB1009 になる前に
# 明確なエラーを出し、リポジトリ内の .csproj 候補を提示して設定修正を促す。
$publishProjectPath = if ([System.IO.Path]::IsPathRooted($ci.PublishProject)) {
    $ci.PublishProject
} else {
    Join-Path $ci.Root $ci.PublishProject
}
if (-not (Test-Path $publishProjectPath)) {
    $candidates = Get-ChildItem -Path $ci.Root -Recurse -File -Filter *.csproj -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName.Substring($ci.Root.Length).TrimStart('\', '/') }
    $list = if ($candidates) { ($candidates | ForEach-Object { "  - $_" }) -join [Environment]::NewLine } else { "  (.csproj が見つかりません)" }
    throw @"
Publish 対象のプロジェクトが見つかりません: $($ci.PublishProject)
（探索パス: $publishProjectPath）

リポジトリ内の .csproj 候補:
$list

GUI の『公開プロジェクト (publishProject)』を、リポジトリルートからの正しい相対パスに修正してください。
"@
}

# framework-dependent + PublishSingleFile（.NET ランタイムは同梱しない）。
# アプリ依存 DLL は単一 exe に取り込むが、ランタイムは同梱しない（self-contained だと肥大化するため）。
# 実行 PC 側に対応する .NET ランタイムが入っている前提の運用。
# PublishSingleFile には RuntimeIdentifier（-r）が必要。
$platformTag = if ($env:OS -eq 'Windows_NT') { 'win-x64' } else { 'linux-x64' }
$publishArgs = @(
    "publish",
    $ci.PublishProject,
    "-c", $Configuration,
    "-r", $platformTag,
    "-o", $publishDir,
    "--self-contained", "false",
    "-p:PublishSingleFile=true",
    "-p:IncludeNativeLibrariesForSelfExtract=true"
)

if ($Version) {
    $publishArgs += @("-p:Version=$Version", "-p:AssemblyVersion=$Version.0", "-p:FileVersion=$Version.0")
}

Write-Host "==> Publish (framework-dependent single-file, $platformTag)"
dotnet @publishArgs
if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish failed (exit code $LASTEXITCODE)."
}

$prefix = $ci.ArtifactPrefix
$projBase = [System.IO.Path]::GetFileNameWithoutExtension($ci.PublishProject)

# 単一ファイル化した実行ファイルを release 直下へコピー（成果物の主出力）。
$exeCandidates = @(Get-ChildItem -Path $publishDir -File -Filter '*.exe' -ErrorAction SilentlyContinue)
if ($exeCandidates.Count -eq 0) {
    # Linux 等: 拡張子なしの apphost が主成果物になることがある
    $maybe = Join-Path $publishDir $projBase
    if (Test-Path -LiteralPath $maybe -PathType Leaf) {
        $exeCandidates = @(Get-Item -LiteralPath $maybe)
    }
}
if ($exeCandidates.Count -eq 0) {
    throw @"
Publish 後に実行ファイルが見つかりません（$publishDir）。
publishProject（$($ci.PublishProject)）の OutputType が Exe / WinExe であることを確認してください。
"@
}

$mainExe = @($exeCandidates | Where-Object { $_.BaseName -ieq $projBase } | Select-Object -First 1)
if (-not $mainExe) {
    $mainExe = @($exeCandidates | Sort-Object Length -Descending | Select-Object -First 1)
}
$mainExe = $mainExe[0]

$exeExt = if ($env:OS -eq 'Windows_NT') { '.exe' } else { '' }
$exeName = if ($Version) { "$prefix-$Version-$platformTag$exeExt" } else { "$prefix-$platformTag$exeExt" }
$exePath = Join-Path $releaseDir $exeName
Copy-Item -LiteralPath $mainExe.FullName -Destination $exePath -Force
Write-Host "Executable: $exePath"

# 後方互換のため zip も残す（単一 exe + 付随ファイル）。
$zipName = if ($Version) { "$prefix-$Version-$platformTag.zip" } else { "$prefix-$platformTag.zip" }
$zipPath = Join-Path $releaseDir $zipName

Write-Host "==> Archive $zipName"
Compress-Archive -Path (Join-Path $publishDir "*") -DestinationPath $zipPath -Force

Write-Host "Published to $exePath and $zipPath"
