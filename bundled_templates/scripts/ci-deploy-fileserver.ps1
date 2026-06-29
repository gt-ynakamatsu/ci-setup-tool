param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Logs', 'Artifact', 'Analysis', 'Test')]
    [string]$Type,

    [string]$FileServerRoot = $env:CI_FILE_SERVER,
    [string]$BuildNumber = $env:BUILD_NUMBER,
    [string]$JobName = $env:JOB_NAME
)

# ログ / 解析レポート / リリース成果物を書き込み先（UNC・ローカル/ OneDrive 同期フォルダ）へ配置する。
# 配置先パスは deploy-manifest.json に記録し、ci-notify-teams.ps1 が Teams 通知に載せる。
# 書き込み先が共有 URL の場合は直接アップロード未対応のためスキップする（共有 URL は storage.*Url で Teams リンクに使用）。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\ci-config.ps1"
$ci = Get-CiSettings
Set-Location $ci.Root

# 正規セットアップの CI_FILE_SERVER（Jenkins パラメータ/環境変数、無ければ config の ciFileServer）を優先する。
# 詳細設定の storage.basePath は CI_FILE_SERVER が空のときだけ使うバックアップ。
$fileServer = if (-not [string]::IsNullOrWhiteSpace($FileServerRoot)) { $FileServerRoot } else { $ci.CiFileServer }
if (-not [string]::IsNullOrWhiteSpace($fileServer)) {
    $projectRoot = Join-StorageChild $fileServer $ci.ProjectName
}
elseif (-not [string]::IsNullOrWhiteSpace($ci.StorageBasePath)) {
    $projectRoot = $ci.StorageBasePath
}
else {
    Write-Warning 'CI_FILE_SERVER is not set and storage.basePath is empty. Skipping file server deploy.'
    exit 0
}

# 書き込み先が共有 URL（OneDrive/SharePoint 等）の場合、無人 CI から直接アップロードするには
# Microsoft Graph 連携が必要。ここでは未対応のためコピーをスキップする。
# ファイルは OneDrive の「ローカル同期フォルダのパス」へ書き、共有 URL は storage.*Url（Teams リンク）に設定する運用を推奨。
if (Test-StorageUrl $projectRoot) {
    Write-Warning ("書き込み先が URL です ($projectRoot)。" +
        "OneDrive/SharePoint への直接アップロードは未対応のため配置をスキップします。" +
        "同期済みローカルフォルダのパスを storage.basePath / CI_FILE_SERVER に指定し、" +
        "共有 URL は storage.*Url（Teams リンク）に設定してください。")
    exit 0
}

$displayName = if ($JobName) { $JobName } else { $ci.ProjectName }
$dateFolder = Get-Date -Format 'yyyyMMdd'
$timeStamp = Get-Date -Format 'HHmmss'

# 配置先パスを Teams 通知へ引き継ぐためのマニフェスト。
# 同一ビルド内（Analysis → Artifact → notify）で追記し、別ビルドの残骸は buildNumber で無効化する。
$manifestPath = Join-Path $ci.Root 'artifacts\deploy-manifest.json'

function Update-DeployManifest {
    param([hashtable]$Entries)

    $manifest = [ordered]@{}
    if (Test-Path $manifestPath) {
        try {
            $existing = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($existing -and "$($existing.buildNumber)" -eq "$BuildNumber") {
                foreach ($p in $existing.PSObject.Properties) {
                    $manifest[$p.Name] = $p.Value
                }
            }
        }
        catch {
            Write-Warning "Failed to read deploy manifest: $_"
        }
    }

    $manifest['buildNumber'] = "$BuildNumber"
    foreach ($key in $Entries.Keys) {
        $manifest[$key] = $Entries[$key]
    }

    ($manifest | ConvertTo-Json -Depth 10) | Set-Content -Path $manifestPath -Encoding UTF8
}

function Get-StorageDestDir {
    param(
        [string]$CategoryDir
    )

    $dest = Join-StorageChild $projectRoot $CategoryDir
    if ($ci.UseDateSubfolder) {
        $dest = Join-StorageChild $dest $dateFolder
    }
    return $dest
}

if ($Type -eq 'Logs') {
    $logFile = Join-Path $ci.Root 'artifacts\logs\build.log'
    if (-not (Test-Path $logFile)) {
        Write-Warning "Log file not found: $logFile"
        exit 0
    }

    $destDir = Get-StorageDestDir -CategoryDir $ci.LogsDir
    $destFile = Join-Path $destDir "$displayName-$BuildNumber-$timeStamp.log"

    New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    Copy-Item -Path $logFile -Destination $destFile -Force

    Write-Host "Log saved to $destFile"
    return
}

if ($Type -eq 'Analysis') {
    $analysisDir = Join-Path $ci.Root 'artifacts\analysis'
    if (-not (Test-Path $analysisDir)) {
        Write-Warning "Analysis directory not found: $analysisDir"
        exit 0
    }

    $files = Get-ChildItem -Path $analysisDir -File
    if ($files.Count -eq 0) {
        Write-Warning 'No analysis report found to deploy.'
        exit 0
    }

    $destDir = Join-Path (Get-StorageDestDir -CategoryDir 'analysis') "$displayName-$BuildNumber-$timeStamp"
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null

    foreach ($file in $files) {
        Copy-Item -Path $file.FullName -Destination (Join-Path $destDir $file.Name) -Force
    }

    $entries = @{ analysisDir = $destDir }
    $reportFile = Join-Path $destDir 'analysis-report.html'
    if (Test-Path $reportFile) {
        $entries['analysisReport'] = $reportFile
    }
    Update-DeployManifest -Entries $entries

    Write-Host "Analysis report saved to $destDir"
    return
}

if ($Type -eq 'Test') {
    $testDir = Join-Path $ci.Root 'artifacts\test'
    if (-not (Test-Path $testDir)) {
        Write-Warning "Test directory not found: $testDir"
        exit 0
    }

    $files = Get-ChildItem -Path $testDir -File
    if ($files.Count -eq 0) {
        Write-Warning 'No test artifacts found to deploy.'
        exit 0
    }

    $categoryDir = if ($ci.TestsDir) { $ci.TestsDir } else { 'tests' }
    $destDir = Join-Path (Get-StorageDestDir -CategoryDir $categoryDir) "$displayName-$BuildNumber-$timeStamp"
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null

    foreach ($file in $files) {
        Copy-Item -Path $file.FullName -Destination (Join-Path $destDir $file.Name) -Force
    }

    $entries = @{ testDir = $destDir }
    $failureLog = Join-Path $destDir 'test-failures.log'
    if (Test-Path $failureLog) {
        $entries['testFailureLog'] = $failureLog
    }
    Update-DeployManifest -Entries $entries

    Write-Host "Test artifacts saved to $destDir"
    return
}

$releaseDir = Join-Path $ci.Root 'artifacts\release'
if (-not (Test-Path $releaseDir)) {
    Write-Warning "Release directory not found: $releaseDir"
    exit 0
}

$zipFiles = Get-ChildItem -Path $releaseDir -Filter '*.zip' -File
if ($zipFiles.Count -eq 0) {
    Write-Warning 'No zip artifact found to deploy.'
    exit 0
}

$destDir = Get-StorageDestDir -CategoryDir $ci.ReleasesDir
New-Item -ItemType Directory -Force -Path $destDir | Out-Null

foreach ($zip in $zipFiles) {
    $destFile = Join-Path $destDir $zip.Name
    Copy-Item -Path $zip.FullName -Destination $destFile -Force
    Write-Host "Artifact saved to $destFile"
}

Update-DeployManifest -Entries @{ artifactDir = $destDir }
