# CI パイプライン共通設定ローダー
# cisetup/cisetup.config.json を読む（旧: リポジトリ直下の cisetup.config.json も後方互換）。
# Jenkins 各ステージ（ci-build.ps1 等）から dot-source される。

function Test-StorageUrl {
    # 格納先が http(s) URL（OneDrive/SharePoint 等）かどうか。
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    return ($Value.Trim() -match '^(?i)https?://')
}

function ConvertTo-StringArray {
    # JSON 値（単一文字列 or 配列）を空要素を除いた文字列配列へ正規化する。
    param($Value)
    $out = @()
    if ($null -eq $Value) { return $out }
    if ($Value -is [string]) {
        $s = $Value.Trim()
        if ($s) { $out += $s }
        return $out
    }
    if ($Value -is [System.Collections.IEnumerable]) {
        foreach ($item in $Value) {
            $s = "$item".Trim()
            if ($s) { $out += $s }
        }
        return $out
    }
    $s = "$Value".Trim()
    if ($s) { $out += $s }
    return $out
}

function Get-ConfigList {
    # 複数形→旧単数形の順にキーを探し、最初に値がある列を配列で返す（後方互換）。
    param($Container, [string[]]$Names)
    if ($null -eq $Container) { return @() }
    $props = @($Container.PSObject.Properties.Name)
    foreach ($name in $Names) {
        if ($props -contains $name) {
            $list = ConvertTo-StringArray $Container.$name
            if ($list.Count -gt 0) { return $list }
        }
    }
    return @()
}

function Join-StorageChild {
    # 格納先（UNC/ローカルパス または URL）にサブパスを連結する。
    # URL なら "/"、パスなら "\" で連結する。
    param([string]$Base, [string]$Child)
    if ([string]::IsNullOrWhiteSpace($Base)) { return $Child }
    if ([string]::IsNullOrWhiteSpace($Child)) { return $Base }
    if (Test-StorageUrl $Base) {
        return ($Base.TrimEnd('/')) + '/' + ($Child.Trim('/', '\'))
    }
    return ($Base.TrimEnd('\', '/')) + '\' + ($Child.Trim('\', '/'))
}

function Get-CISetupLayout {
    $scriptsDir = $PSScriptRoot
    $parent = Split-Path -Parent $scriptsDir

    if ((Split-Path -Leaf $parent) -eq 'cisetup') {
        $ciDir = $parent
        $root = Split-Path -Parent $ciDir
        if ([string]::IsNullOrWhiteSpace($root)) {
            $root = $ciDir
        }
        return [PSCustomObject]@{
            CiDir  = $ciDir
            Root   = $root
            Layout = 'cisetup'
        }
    }

    return [PSCustomObject]@{
        CiDir  = $parent
        Root   = $parent
        Layout = 'legacy'
    }
}

function Get-CISetupConfigPath {
    param(
        [string]$CiDir,
        [string]$Root,
        [string]$Layout
    )

    if ($Layout -eq 'cisetup') {
        return Join-Path $CiDir 'cisetup.config.json'
    }

    return Join-Path $Root 'cisetup.config.json'
}

function ConvertFrom-LegacyCiSettings {
    param($Legacy, [string]$Root)

    return [PSCustomObject]@{
        project = [PSCustomObject]@{
            name = $Legacy.projectName
            solutionFile = $Legacy.solutionFile
            publishProject = $Legacy.publishProject
            artifactPrefix = $Legacy.artifactPrefix
        }
        storage = if ($Legacy.storage) { $Legacy.storage } else { [PSCustomObject]@{
            basePath = ''
            logsDir = 'logs'
            releasesDir = 'releases'
            useDateSubfolder = $true
        }}
        jenkins = [PSCustomObject]@{
            jobName = 'CISetup-CI'
            agentLabel = 'windows'
            cronSchedule = '0 0 * * *'
            pollSchedule = 'H/5 * * * *'
            ciFileServer = '\\fileserver\ci'
            teamsCredentialId = 'teams-webhook-url'
            defaultConfiguration = 'Release'
            buildTimeoutMinutes = 30
            logRetentionCount = 30
            timezone = 'Asia/Tokyo'
        }
        git = [PSCustomObject]@{
            repositoryUrl = ''
            branch = 'main'
            credentialId = 'internal-git'
        }
    }
}

function Get-CiSettings {
    $layout = Get-CISetupLayout
    $root = $layout.Root
    $configPath = Get-CISetupConfigPath -CiDir $layout.CiDir -Root $root -Layout $layout.Layout
    $legacyPath = Join-Path $root 'ci.settings.json'

    if (Test-Path $configPath) {
        $config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    elseif (Test-Path $legacyPath) {
        # 旧 CISetup プロジェクト向け。GUI 保存時に cisetup.config.json へ移行される。
        $legacy = Get-Content $legacyPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $config = ConvertFrom-LegacyCiSettings -Legacy $legacy -Root $root
    }
    else {
        throw "cisetup.config.json not found under cisetup/. Run Configure.ps1 (GUI) to create settings."
    }

    # ---- ビルドプロファイル（dotnet / custom）----
    $build = $config.build
    $buildProfile = if ($build -and $build.profile) { ([string]$build.profile).Trim().ToLower() } else { 'dotnet' }
    if ($buildProfile -ne 'custom') { $buildProfile = 'dotnet' }

    $buildCommand = if ($build) { [string]$build.buildCommand } else { '' }
    $lintCommand = if ($build) { [string]$build.lintCommand } else { '' }
    $analyzeCommand = if ($build) { [string]$build.analyzeCommand } else { '' }
    $publishCommand = if ($build) { [string]$build.publishCommand } else { '' }
    $testCommand = if ($build) { [string]$build.testCommand } else { '' }
    $artifactGlob = if ($build) { [string]$build.artifactGlob } else { '' }
    $testProject = if ($config.project.testProject) { ($config.project.testProject -replace '/', '\').Trim() } else { '' }

    if ([string]::IsNullOrWhiteSpace($config.project.name)) {
        throw "cisetup.config.json: project.name is required."
    }

    if ($buildProfile -eq 'dotnet') {
        foreach ($key in @('solutionFile', 'publishProject', 'artifactPrefix')) {
            if ([string]::IsNullOrWhiteSpace($config.project.$key)) {
                throw "cisetup.config.json: project.$key is required for the dotnet profile."
            }
        }
    }
    elseif ([string]::IsNullOrWhiteSpace($buildCommand)) {
        throw "cisetup.config.json: build.buildCommand is required for the custom profile."
    }

    $storage = $config.storage
    $logsDir = if ($storage -and $storage.logsDir) { $storage.logsDir.Trim() } else { 'logs' }
    $releasesDir = if ($storage -and $storage.releasesDir) { $storage.releasesDir.Trim() } else { 'releases' }
    $useDateSubfolder = if ($storage -and $null -ne $storage.useDateSubfolder) { [bool]$storage.useDateSubfolder } else { $true }
    $testsDir = if ($storage -and $storage.testsDir) { $storage.testsDir.Trim() } else { 'tests' }
    $sourceDir = if ($storage -and $storage.sourceDir) { $storage.sourceDir.Trim() } else { 'source' }
    $archiveSource = if ($storage -and $null -ne $storage.archiveSource) { [bool]$storage.archiveSource } else { $false }

    # 書き込み先・閲覧 URL は複数対応（配列。旧単一キーも読む）。
    $basePaths = Get-ConfigList $storage @('basePaths', 'basePath')
    $releaseUrls = Get-ConfigList $storage @('releaseUrls', 'releaseUrl')
    $analysisUrls = Get-ConfigList $storage @('analysisUrls', 'analysisUrl')
    $logsUrls = Get-ConfigList $storage @('logsUrls', 'logsUrl')
    $testsUrls = Get-ConfigList $storage @('testsUrls', 'testsUrl')

    $jenkins = $config.jenkins
    $ciFileServers = Get-ConfigList $jenkins @('ciFileServers', 'ciFileServer')

    # 個人 ID を含む書き込み先は git 非追跡の cisetup.local.json に保持される（あれば優先）。
    $localPath = if ($layout.Layout -eq 'cisetup') { Join-Path $layout.CiDir 'cisetup.local.json' } else { Join-Path $root 'cisetup.local.json' }
    if (Test-Path $localPath) {
        try {
            $local = Get-Content $localPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $localBasePaths = Get-ConfigList $local @('basePaths', 'basePath')
            $localCiFileServers = Get-ConfigList $local @('ciFileServers', 'ciFileServer')
            if ($localBasePaths.Count -gt 0) { $basePaths = $localBasePaths }
            if ($localCiFileServers.Count -gt 0) { $ciFileServers = $localCiFileServers }
        }
        catch {
            Write-Warning "Failed to read cisetup.local.json: $_"
        }
    }

    return [PSCustomObject]@{
        ProjectName = $config.project.name
        SolutionFile = $config.project.solutionFile
        PublishProject = ($config.project.publishProject -replace '/', '\')
        TestProject = $testProject
        ArtifactPrefix = if ([string]::IsNullOrWhiteSpace($config.project.artifactPrefix)) { $config.project.name } else { $config.project.artifactPrefix }
        Profile = $buildProfile
        BuildCommand = $buildCommand
        LintCommand = $lintCommand
        AnalyzeCommand = $analyzeCommand
        PublishCommand = $publishCommand
        TestCommand = $testCommand
        ArtifactGlob = $artifactGlob
        StorageBasePaths = $basePaths
        StorageBasePath = if ($basePaths.Count -gt 0) { $basePaths[0] } else { '' }
        LogsDir = ($logsDir -replace '/', '\')
        ReleasesDir = ($releasesDir -replace '/', '\')
        TestsDir = ($testsDir -replace '/', '\')
        SourceDir = ($sourceDir -replace '/', '\')
        ArchiveSource = $archiveSource
        UseDateSubfolder = $useDateSubfolder
        ReleaseUrls = $releaseUrls
        AnalysisUrls = $analysisUrls
        LogsUrls = $logsUrls
        TestsUrls = $testsUrls
        ReleaseUrl = if ($releaseUrls.Count -gt 0) { $releaseUrls[0] } else { '' }
        AnalysisUrl = if ($analysisUrls.Count -gt 0) { $analysisUrls[0] } else { '' }
        LogsUrl = if ($logsUrls.Count -gt 0) { $logsUrls[0] } else { '' }
        TestsUrl = if ($testsUrls.Count -gt 0) { $testsUrls[0] } else { '' }
        CiFileServers = $ciFileServers
        CiFileServer = if ($ciFileServers.Count -gt 0) { $ciFileServers[0] } else { '' }
        Root = $root
        CiDir = $layout.CiDir
    }
}
