# CI パイプライン共通設定ローダー
# cisetup/cisetup.config.json を読む（旧: リポジトリ直下の cisetup.config.json も後方互換）。
# Jenkins 各ステージ（ci-build.ps1 等）から dot-source される。

function Test-StorageUrl {
    # 格納先が http(s) URL（OneDrive/SharePoint 等）かどうか。
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    return ($Value.Trim() -match '^(?i)https?://')
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
    $storageBasePath = if ($storage -and $storage.basePath) { $storage.basePath.Trim() } else { '' }
    $logsDir = if ($storage -and $storage.logsDir) { $storage.logsDir.Trim() } else { 'logs' }
    $releasesDir = if ($storage -and $storage.releasesDir) { $storage.releasesDir.Trim() } else { 'releases' }
    $useDateSubfolder = if ($storage -and $null -ne $storage.useDateSubfolder) { [bool]$storage.useDateSubfolder } else { $true }
    $releaseUrl = if ($storage -and $storage.releaseUrl) { $storage.releaseUrl.Trim() } else { '' }
    $analysisUrl = if ($storage -and $storage.analysisUrl) { $storage.analysisUrl.Trim() } else { '' }
    $logsUrl = if ($storage -and $storage.logsUrl) { $storage.logsUrl.Trim() } else { '' }
    $testsUrl = if ($storage -and $storage.testsUrl) { $storage.testsUrl.Trim() } else { '' }
    $testsDir = if ($storage -and $storage.testsDir) { $storage.testsDir.Trim() } else { 'tests' }

    $jenkins = $config.jenkins
    $ciFileServer = if ($jenkins -and $jenkins.ciFileServer) { $jenkins.ciFileServer.Trim() } else { '' }

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
        StorageBasePath = $storageBasePath
        LogsDir = ($logsDir -replace '/', '\')
        ReleasesDir = ($releasesDir -replace '/', '\')
        TestsDir = ($testsDir -replace '/', '\')
        UseDateSubfolder = $useDateSubfolder
        ReleaseUrl = $releaseUrl
        AnalysisUrl = $analysisUrl
        LogsUrl = $logsUrl
        TestsUrl = $testsUrl
        CiFileServer = $ciFileServer
        Root = $root
        CiDir = $layout.CiDir
    }
}
