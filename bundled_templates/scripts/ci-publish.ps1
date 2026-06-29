param(
    [string]$Configuration = "Release",
    [string]$Version = ""
)

# Jenkins publish ステージ — dotnet publish / custom publishCommand。PUBLISH_RELEASE=false ならスキップ。
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
    $releaseDir = Join-Path $ci.Root 'artifacts\release'
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
        Where-Object { $_.FullName -notmatch '\\artifacts\\release\\' }

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

$publishDir = Join-Path $ci.Root "artifacts\publish"
$releaseDir = Join-Path $ci.Root "artifacts\release"

if (Test-Path $publishDir) {
    Remove-Item -Recurse -Force $publishDir
}

if (Test-Path $releaseDir) {
    Remove-Item -Recurse -Force $releaseDir
}

New-Item -ItemType Directory -Force -Path $publishDir, $releaseDir | Out-Null

$publishArgs = @(
    "publish",
    $ci.PublishProject,
    "-c", $Configuration,
    "-o", $publishDir,
    "--self-contained", "false",
    "-p:PublishSingleFile=false"
)

if ($Version) {
    $publishArgs += @("-p:Version=$Version", "-p:AssemblyVersion=$Version.0", "-p:FileVersion=$Version.0")
}

Write-Host "==> Publish"
dotnet @publishArgs

$prefix = $ci.ArtifactPrefix
$zipName = if ($Version) { "$prefix-$Version-win-x64.zip" } else { "$prefix-win-x64.zip" }
$zipPath = Join-Path $releaseDir $zipName

Write-Host "==> Archive $zipName"
Compress-Archive -Path (Join-Path $publishDir "*") -DestinationPath $zipPath -Force

Write-Host "Published to $zipPath"
