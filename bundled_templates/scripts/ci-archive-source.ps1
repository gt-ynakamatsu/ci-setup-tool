param(
    [string]$BuildNumber = $env:BUILD_NUMBER
)

# pull してチェックアウトした最新の開発環境一式（ソースツリー）を zip 化する。
# storage.archiveSource が false のときは何もしない（自己ゲート。Jenkinsfile に when 条件は不要）。
# 出力: artifacts\source\<ArtifactPrefix>-<BUILD_NUMBER|日時>-src.zip
# PowerShell 5.1 互換（三項演算子不可、System.IO.Compression を使用）。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\ci-config.ps1"
$ci = Get-CiSettings
Set-Location $ci.Root

if (-not $ci.ArchiveSource) {
    Write-Host 'Source archive disabled (storage.archiveSource = false). Skipping.'
    exit 0
}

$sourceOut = Join-Path $ci.Root 'artifacts\source'
New-Item -ItemType Directory -Force -Path $sourceOut | Out-Null
# 再利用ワークスペースで過去ビルドの zip が残ると Source デプロイで全件コピーされるため、
# 出力先の既存 zip を一掃してから当該ビルドの zip だけを作る。
Get-ChildItem -Path $sourceOut -Filter '*.zip' -File -ErrorAction SilentlyContinue | Remove-Item -Force

$stamp = if ([string]::IsNullOrWhiteSpace($BuildNumber)) { Get-Date -Format 'yyyyMMdd-HHmmss' } else { $BuildNumber }
$prefix = if ([string]::IsNullOrWhiteSpace($ci.ArtifactPrefix)) { $ci.ProjectName } else { $ci.ArtifactPrefix }
$zipPath = Join-Path $sourceOut "$prefix-$stamp-src.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

# 除外: ディレクトリ名（ネスト含む）と末尾ファイルパターン。
$excludeDirs = @('.git', 'artifacts', 'bin', 'obj', '.vs', 'node_modules', 'packages', 'TestResults')
$excludeFilePatterns = @('*.user')

$rootFull = (Resolve-Path $ci.Root).Path.TrimEnd('\')
$rootPrefix = $rootFull + '\'

function Test-SourceExcluded {
    param([string]$FullPath)
    $rel = $FullPath.Substring($rootPrefix.Length)
    $parts = $rel -split '[\\/]'
    # 末尾要素はファイル名、それ以外の各階層がディレクトリ。
    for ($i = 0; $i -lt $parts.Length - 1; $i++) {
        if ($excludeDirs -contains $parts[$i]) { return $true }
    }
    $fileName = $parts[$parts.Length - 1]
    foreach ($pat in $excludeFilePatterns) {
        if ($fileName -like $pat) { return $true }
    }
    return $false
}

$files = @(Get-ChildItem -Path $rootFull -Recurse -File -Force | Where-Object {
        -not (Test-SourceExcluded $_.FullName)
    })

if ($files.Count -eq 0) {
    Write-Warning 'No source files to archive (after exclusions). Skipping.'
    exit 0
}

Add-Type -AssemblyName System.IO.Compression | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null

$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($f in $files) {
        $entryName = ($f.FullName.Substring($rootPrefix.Length)) -replace '\\', '/'
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, $entryName) | Out-Null
    }
}
finally {
    $zip.Dispose()
}

Write-Host "Source archive created: $zipPath ($($files.Count) files)"
