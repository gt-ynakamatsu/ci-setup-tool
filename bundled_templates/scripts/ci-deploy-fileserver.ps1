param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Logs', 'Artifact', 'Analysis', 'Test', 'Source')]
    [string]$Type,

    [string]$FileServerRoot = $env:CI_FILE_SERVER,
    [string]$BuildNumber = $env:BUILD_NUMBER,
    [string]$JobName = $env:JOB_NAME
)

# ログ / 解析レポート / リリース成果物 / ユニットテスト結果を、設定された「全書き込み先」
# （UNC・ローカル / OneDrive 同期フォルダ）へ順にコピーする。
# 配置先パスは deploy-manifest.json に記録し、ci-notify-teams.ps1 が Teams 通知に載せる。
# 書き込み先が共有 URL の場合は直接アップロード未対応のため各先ごとにスキップする
# （共有 URL は storage.*Urls で Teams リンクに使用）。
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ci-config.ps1')
$ci = Get-CiSettings
Set-Location $ci.Root

$displayName = if ($JobName) { $JobName } else { $ci.ProjectName }
$dateFolder = Get-Date -Format 'yyyyMMdd'
$timeStamp = Get-Date -Format 'HHmmss'
$testsDir = if ($ci.TestsDir) { $ci.TestsDir } else { 'tests' }

# 配置先パスを Teams 通知へ引き継ぐためのマニフェスト。
# 同一ビルド内（Analysis → Artifact → notify）で追記し、別ビルドの残骸は buildNumber で無効化する。
$manifestPath = Join-PathMulti $ci.Root @('artifacts', 'deploy-manifest.json')

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

# ---- 書き込み先（複数）の解決 ----
# Jenkins パラメータ/環境変数 CI_FILE_SERVER が指定された場合はそれを単一の書き込み先として
# 上書き採用する（従来互換）。無ければ config / cisetup.local.json の全先を使う。
#   CI_FILE_SERVER 系 : <base>/<project>（プロジェクト名を付与）
#   basePath 系       : <base>（そのまま）
# ユニットテスト結果は releases / logs / analysis と混ざらない専用トップレベルに分離する:
#   CI_FILE_SERVER 系 : <base>/<testsDir>/<project>
#   basePath 系       : <base>/<testsDir>
# ※ プロジェクト名はフォルダ整理のための区切りで、検出/判定ロジックには依存しない。
$targets = New-Object System.Collections.Generic.List[object]
$seen = New-Object System.Collections.Generic.HashSet[string]

function Add-WriteTarget {
    param([string]$Base, [bool]$AppendProject)
    if ([string]::IsNullOrWhiteSpace($Base)) { return }
    $b = $Base.Trim()
    if ($AppendProject) {
        $root = Join-StorageChild $b $ci.ProjectName
        $testsRoot = Join-StorageChild (Join-StorageChild $b $testsDir) $ci.ProjectName
    }
    else {
        $root = $b
        $testsRoot = Join-StorageChild $b $testsDir
    }
    # 重複排除は「入力ベース文字列」ではなく「実効ルート」で行う（GUI の build_target_roots と一致させ、
    # ④=<base>/<project> と書き込み先ベース=<base> が同一ルートに解決される場合の二重コピーを防ぐ）。
    if (-not $seen.Add($root.ToLowerInvariant())) { return }
    $targets.Add([PSCustomObject]@{ Base = $b; Root = $root; TestsRoot = $testsRoot }) | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace($FileServerRoot)) {
    Add-WriteTarget -Base $FileServerRoot -AppendProject $true
}
else {
    foreach ($fs in $ci.CiFileServers) { Add-WriteTarget -Base $fs -AppendProject $true }
    foreach ($bp in $ci.StorageBasePaths) { Add-WriteTarget -Base $bp -AppendProject $false }
}

if ($targets.Count -eq 0) {
    Write-Warning 'CI_FILE_SERVER is not set and storage.basePaths is empty. Skipping file server deploy.'
    exit 0
}

function Test-TargetUrl {
    # 書き込み先が共有 URL（OneDrive/SharePoint 等）なら警告してスキップ対象とする。
    param([object]$Target)
    if (Test-StorageUrl $Target.Root) {
        Write-Warning ("書き込み先が URL です ($($Target.Base))。" +
            "OneDrive/SharePoint への直接アップロードは未対応のため、この先への配置をスキップします。" +
            "同期済みローカルフォルダのパスを CI_FILE_SERVER / storage.basePaths に指定し、" +
            "共有 URL は storage.*Urls（Teams リンク）に設定してください。")
        return $true
    }
    return $false
}

function Get-CategoryDest {
    param([object]$Target, [string]$CategoryDir)
    $dest = Join-StorageChild $Target.Root $CategoryDir
    if ($ci.UseDateSubfolder) { $dest = Join-StorageChild $dest $dateFolder }
    return $dest
}

function Get-TestsDest {
    param([object]$Target)
    $dest = $Target.TestsRoot
    if ($ci.UseDateSubfolder) { $dest = Join-StorageChild $dest $dateFolder }
    return $dest
}

if ($Type -eq 'Logs') {
    $logFile = Join-PathMulti $ci.Root @('artifacts', 'logs', 'build.log')
    if (-not (Test-Path $logFile)) {
        Write-Warning "Log file not found: $logFile"
        exit 0
    }

    foreach ($t in $targets) {
        if (Test-TargetUrl $t) { continue }
        $destDir = Get-CategoryDest -Target $t -CategoryDir $ci.LogsDir
        $destFile = Join-Path $destDir "$displayName-$BuildNumber-$timeStamp.log"
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        Copy-Item -Path $logFile -Destination $destFile -Force
        Write-Host "Log saved to $destFile"
    }
    return
}

if ($Type -eq 'Analysis') {
    $analysisDir = Join-PathMulti $ci.Root @('artifacts', 'analysis')
    if (-not (Test-Path $analysisDir)) {
        Write-Warning "Analysis directory not found: $analysisDir"
        exit 0
    }

    $files = Get-ChildItem -Path $analysisDir -File
    if ($files.Count -eq 0) {
        Write-Warning 'No analysis report found to deploy.'
        exit 0
    }

    $firstDest = $null
    foreach ($t in $targets) {
        if (Test-TargetUrl $t) { continue }
        $destDir = Join-Path (Get-CategoryDest -Target $t -CategoryDir 'analysis') "$displayName-$BuildNumber-$timeStamp"
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        foreach ($file in $files) {
            Copy-Item -Path $file.FullName -Destination (Join-Path $destDir $file.Name) -Force
        }
        Write-Host "Analysis report saved to $destDir"
        if (-not $firstDest) { $firstDest = $destDir }
    }

    if ($firstDest) {
        $entries = @{ analysisDir = $firstDest }
        $reportFile = Join-Path $firstDest 'analysis-report.html'
        if (Test-Path $reportFile) {
            $entries['analysisReport'] = $reportFile
        }
        Update-DeployManifest -Entries $entries
    }
    return
}

if ($Type -eq 'Test') {
    $testDir = Join-PathMulti $ci.Root @('artifacts', 'test')
    if (-not (Test-Path $testDir)) {
        Write-Warning "Test directory not found: $testDir"
        exit 0
    }

    $files = Get-ChildItem -Path $testDir -File
    if ($files.Count -eq 0) {
        Write-Warning 'No test artifacts found to deploy.'
        exit 0
    }

    $firstDest = $null
    foreach ($t in $targets) {
        if (Test-TargetUrl $t) { continue }
        # ユニットテスト結果は専用トップレベル（Get-TestsDest）へ配置する。
        $destDir = Join-Path (Get-TestsDest -Target $t) "$displayName-$BuildNumber-$timeStamp"
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        foreach ($file in $files) {
            Copy-Item -Path $file.FullName -Destination (Join-Path $destDir $file.Name) -Force
        }
        Write-Host "Test artifacts saved to $destDir"
        if (-not $firstDest) { $firstDest = $destDir }
    }

    if ($firstDest) {
        $entries = @{ testDir = $firstDest }
        $failureLog = Join-Path $firstDest 'test-failures.log'
        if (Test-Path $failureLog) {
            $entries['testFailureLog'] = $failureLog
        }
        Update-DeployManifest -Entries $entries
    }
    return
}

if ($Type -eq 'Source') {
    # 開発環境一式 zip を専用サブフォルダ（SourceDir）へ配置する。releases と同じ category 構造。
    # archiveSource が無効なら何も配置しない（旧 zip が残っていても誤配置しないよう明示ゲート）。
    if (-not $ci.ArchiveSource) {
        Write-Host 'Source archive disabled (storage.archiveSource = false). Skipping source deploy.'
        exit 0
    }
    $sourceDirLocal = Join-PathMulti $ci.Root @('artifacts', 'source')
    if (-not (Test-Path $sourceDirLocal)) {
        Write-Warning "Source directory not found: $sourceDirLocal"
        exit 0
    }

    $zipFiles = Get-ChildItem -Path $sourceDirLocal -Filter '*.zip' -File
    if ($zipFiles.Count -eq 0) {
        Write-Warning 'No source archive found to deploy.'
        exit 0
    }

    $sourceCat = if ($ci.SourceDir) { $ci.SourceDir } else { 'source' }
    $firstDest = $null
    foreach ($t in $targets) {
        if (Test-TargetUrl $t) { continue }
        $destDir = Get-CategoryDest -Target $t -CategoryDir $sourceCat
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        foreach ($zip in $zipFiles) {
            $destFile = Join-Path $destDir $zip.Name
            Copy-Item -Path $zip.FullName -Destination $destFile -Force
            Write-Host "Source archive saved to $destFile"
        }
        if (-not $firstDest) { $firstDest = $destDir }
    }

    if ($firstDest) {
        Update-DeployManifest -Entries @{ sourceDir = $firstDest }
    }
    return
}

# ---- Artifact（リリース zip）----
$releaseDir = Join-PathMulti $ci.Root @('artifacts', 'release')
if (-not (Test-Path $releaseDir)) {
    Write-Warning "Release directory not found: $releaseDir"
    exit 0
}

$zipFiles = Get-ChildItem -Path $releaseDir -Filter '*.zip' -File
if ($zipFiles.Count -eq 0) {
    Write-Warning 'No zip artifact found to deploy.'
    exit 0
}

$firstDest = $null
foreach ($t in $targets) {
    if (Test-TargetUrl $t) { continue }
    $destDir = Get-CategoryDest -Target $t -CategoryDir $ci.ReleasesDir
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    foreach ($zip in $zipFiles) {
        $destFile = Join-Path $destDir $zip.Name
        Copy-Item -Path $zip.FullName -Destination $destFile -Force
        Write-Host "Artifact saved to $destFile"
    }
    if (-not $firstDest) { $firstDest = $destDir }
}

if ($firstDest) {
    Update-DeployManifest -Entries @{ artifactDir = $firstDest }
}
