# CI パイプライン共通設定ローダー
# CISetup/cisetup.config.json を読む（旧 cisetup/ フォルダ、およびリポジトリ直下の
# cisetup.config.json も後方互換で読む）。
# Jenkins 各ステージ（ci-build.ps1 等）から dot-source される。
#
# Windows PowerShell 5.1 / PowerShell 7+ (pwsh, Linux 含む) の両方で動く前提。
# パス連結は必ず Join-Path / Join-PathMulti を使い、"\" 決め打ちの文字列連結はしないこと
# （Linux では "\" はディレクトリ区切りではなく通常の1文字として扱われるため）。

function Join-PathMulti {
    # PowerShell 5.1 では Join-Path の -AdditionalChildPath（PS 6+ 限定）が使えないため、
    # 複数セグメントを順に Join-Path して連結する自前のヘルパー。
    param([string]$Base, [string[]]$ChildPaths)
    $result = $Base
    foreach ($child in $ChildPaths) { $result = Join-Path $result $child }
    return $result
}

function ConvertTo-PlatformPath {
    # 設定ファイル（JSON）は "/" 区切りで保存される想定だが、旧設定や Windows 由来の値は
    # "\" 区切りのこともある。実行 OS に応じたセパレーターへ正規化する。
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $Value }
    return ($Value -replace '[\\/]', [System.IO.Path]::DirectorySeparatorChar)
}

function Test-StorageUrl {
    # 格納先が http(s) URL（OneDrive/SharePoint 等）かどうか。
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    return ($Value.Trim() -match '^(?i)https?://')
}

function ConvertTo-StringArray {
    # JSON 値（単一文字列 or 配列）を空要素を除いた文字列配列へ正規化する。
    # NOTE: PowerShell はパイプライン/return で要素数 1 の配列を自動的にスカラーへ
    # 展開してしまう（要素数 0 や 2 以上では起きない）ため、呼び出し側で意図せず
    # 文字列として扱われ `[0]` が「先頭文字」を指してしまう事故を防ぐため、
    # return は必ず単項カンマ演算子（,）で配列であることを明示する。
    param($Value)
    $out = @()
    if ($null -eq $Value) { return , $out }
    if ($Value -is [string]) {
        $s = $Value.Trim()
        if ($s) { $out += $s }
        return , $out
    }
    if ($Value -is [System.Collections.IEnumerable]) {
        foreach ($item in $Value) {
            $s = "$item".Trim()
            if ($s) { $out += $s }
        }
        return , $out
    }
    $s = "$Value".Trim()
    if ($s) { $out += $s }
    return , $out
}

function Get-ConfigList {
    # 複数形→旧単数形の順にキーを探し、最初に値がある列を配列で返す（後方互換）。
    # NOTE: ConvertTo-StringArray と同様、return は単項カンマ演算子で配列を維持する。
    param($Container, [string[]]$Names)
    if ($null -eq $Container) { return , @() }
    $props = @($Container.PSObject.Properties.Name)
    foreach ($name in $Names) {
        if ($props -contains $name) {
            $list = ConvertTo-StringArray $Container.$name
            if ($list.Count -gt 0) { return , $list }
        }
    }
    return , @()
}

function Join-StorageChild {
    # 格納先（UNC/ローカルパス または URL）にサブパスを連結する。
    # URL なら "/"、パスなら実行 OS のセパレーター（Windows: "\" / Linux: "/"）で連結する。
    param([string]$Base, [string]$Child)
    if ([string]::IsNullOrWhiteSpace($Base)) { return $Child }
    if ([string]::IsNullOrWhiteSpace($Child)) { return $Base }
    if (Test-StorageUrl $Base) {
        return ($Base.TrimEnd('/')) + '/' + ($Child.Trim('/', '\'))
    }
    $sep = [System.IO.Path]::DirectorySeparatorChar
    return ($Base.TrimEnd('\', '/')) + $sep + ($Child.Trim('\', '/'))
}

# ---- 実行ログ（コンソールに出た内容をそのままファイルへ残す）----
# Jenkins の Console Output には出ているのに artifacts/logs に残らない、という取りこぼしを防ぐための仕組み。
# Start-Transcript は native コマンド（dotnet / vivado / quartus_sh 等）の出力をコンソールバッファ経由で
# 記録するため、出力が多いと欠落する（PowerShell の既知の制約）。CI 失敗の原因はまさにその出力に
# 書かれているので、native コマンドは Invoke-CiLogged / Invoke-CiLoggedCommandLine 経由で呼び、
# 1 行ずつコンソールとログファイルの両方へ書き出す。
# ログは <Root>/artifacts/logs に集約し、ci-deploy-fileserver.ps1 -Type Logs が格納先の logs へ配置する。

function Get-CiLogDir {
    param([Parameter(Mandatory = $true)][string]$Root)
    $dir = Join-PathMulti $Root @('artifacts', 'logs')
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    return $dir
}

function Get-CiLogPath {
    # $Root は絶対パス（Get-CiSettings の Root）を渡すこと。StreamWriter は PowerShell の
    # カレント位置ではなくプロセスの作業フォルダを基準にするため、相対パスでは書き先がずれる。
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Name
    )
    return Join-Path (Get-CiLogDir -Root $Root) $Name
}

function New-CiLogWriter {
    param([Parameter(Mandatory = $true)][string]$LogPath)
    $dir = Split-Path -Parent $LogPath
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    # 追記・UTF-8（BOM なし）。同じステージ内の複数コマンドを 1 本のログに積み上げる。
    return (New-Object System.IO.StreamWriter($LogPath, $true, (New-Object System.Text.UTF8Encoding($false))))
}

function Write-CiLogLine {
    param($Value, [System.IO.StreamWriter]$Writer)
    # native コマンドの stderr は 2>&1 で ErrorRecord になるため文字列化して同じ扱いにする。
    $line = if ($Value -is [System.Management.Automation.ErrorRecord]) { $Value.ToString() } else { "$Value" }
    Write-Host $line
    if ($Writer) { $Writer.WriteLine($line) }
}

function Write-CiLogHeader {
    param([string]$Text, [System.IO.StreamWriter]$Writer)
    Write-CiLogLine -Value ("==> $Text  [" + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "]") -Writer $Writer
}

function Invoke-CiLogged {
    <#
      native コマンドを実行し、stdout / stderr の全行をコンソールとログへ流して終了コードを返す。

      Windows PowerShell 5.1 は ErrorActionPreference=Stop のまま native の stderr を 2>&1 すると
      stderr の 1 行目で NativeCommandError を投げ、終了コードを拾えなくなる。この関数の中だけ
      Continue にすることで回避する（native コマンドの呼び出しがこの関数のスコープで起きるため、
      呼び出し元スクリプトの Stop 設定は影響しない）。
    #>
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$Label = ''
    )
    $ErrorActionPreference = 'Continue'
    if (-not (Get-Command $FilePath -ErrorAction SilentlyContinue)) {
        # EAP=Continue では CommandNotFound が握りつぶされ、古い $LASTEXITCODE で成功扱いに
        # なりうるため、ここで明示的に失敗させる。
        throw "コマンドが見つかりません: $FilePath"
    }
    $writer = New-CiLogWriter -LogPath $LogPath
    try {
        $header = if ($Label) { $Label } else { (@($FilePath) + $Arguments) -join ' ' }
        Write-CiLogHeader -Text $header -Writer $writer
        & $FilePath @Arguments 2>&1 | ForEach-Object { Write-CiLogLine -Value $_ -Writer $writer }
        $code = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
        Write-CiLogLine -Value "<== exit code $code" -Writer $writer
        return $code
    }
    finally {
        $writer.Flush()
        $writer.Dispose()
    }
}

function Copy-CiFpgaReports {
    <#
      Vivado / Quartus が作業フォルダへ書き出すレポートを artifacts/logs/fpga-reports へ集める。
      コンソール出力だけではタイミング違反やフィット失敗の本文が足りないことがあるため、
      ツール自身の .rpt / vivado.log 等をログ配置と同じフォルダへ残す。
      呼び出しは成功・失敗どちらでも（throw の finally から）行う想定。
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$SearchRoot,
        [int]$MaxFiles = 80,
        [long]$MaxBytes = 20971520
    )
    if ([string]::IsNullOrWhiteSpace($SearchRoot) -or -not (Test-Path -LiteralPath $SearchRoot)) {
        return
    }
    $destDir = Join-Path (Get-CiLogDir -Root $Root) 'fpga-reports'
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null

    $skip = @(
        '.git', '.vs', '.idea', 'bin', 'obj', 'artifacts', 'dist',
        'node_modules', '__pycache__', 'incremental_db', 'db', '.xil'
    )
    $keepNames = @('vivado.log', 'vivado.jou', 'runme.log')
    $keepExt = @('.rpt', '.summary', '.smsg', '.pin', '.jou')

    $searchFull = (Get-Item -LiteralPath $SearchRoot).FullName
    $candidates = @(Get-ChildItem -LiteralPath $searchFull -Recurse -File -ErrorAction SilentlyContinue)
    $picked = New-Object System.Collections.Generic.List[object]
    foreach ($file in $candidates) {
        if ($file.Length -gt $MaxBytes) { continue }
        $rel = $file.FullName.Substring($searchFull.Length).TrimStart('\', '/')
        $skipHit = $false
        foreach ($part in ($rel -split '[\\/]')) {
            if ($skip -contains $part.ToLowerInvariant()) { $skipHit = $true; break }
        }
        if ($skipHit) { continue }
        $nameLower = $file.Name.ToLowerInvariant()
        $extLower = $file.Extension.ToLowerInvariant()
        if (($keepNames -contains $nameLower) -or ($keepExt -contains $extLower)) {
            $picked.Add($file) | Out-Null
        }
    }

    $truncated = $false
    if ($picked.Count -gt $MaxFiles) {
        $picked = @($picked | Sort-Object FullName | Select-Object -First $MaxFiles)
        $truncated = $true
    }
    else {
        $picked = @($picked | Sort-Object FullName)
    }

    $copied = 0
    foreach ($file in $picked) {
        $rel = $file.FullName.Substring($searchFull.Length).TrimStart('\', '/')
        $safe = ($rel -replace '[\\/]', '__')
        if ([string]::IsNullOrWhiteSpace($safe)) { $safe = $file.Name }
        Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $destDir $safe) -Force
        $copied++
    }
    if ($truncated) {
        Write-Warning "FPGA レポートが $MaxFiles 件を超えたため先頭 $MaxFiles 件だけ logs へコピーしました。"
    }
    Write-Host "==> FPGA レポートを logs/fpga-reports へ $copied 件コピーしました（検索: $searchFull）"
}

function Invoke-CiLoggedCommandLine {
    <#
      GUI で設定した独自コマンド（buildCommand / lintCommand / publishCommand 等）を
      Invoke-CiLogged と同じようにコンソールとログへ流して実行し、終了コードを返す。

      NOTE: native の stderr で誤って止まらないよう ErrorActionPreference は Continue にする。
      独自コマンド内の「非終了エラー」はログに残るがビルドは止めない（終了コードと throw で判定する）。
    #>
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$CommandLine,
        [string]$Label = ''
    )
    $ErrorActionPreference = 'Continue'
    $writer = New-CiLogWriter -LogPath $LogPath
    try {
        $header = if ($Label) { $Label } else { $CommandLine }
        Write-CiLogHeader -Text $header -Writer $writer
        Invoke-Expression $CommandLine 2>&1 | ForEach-Object { Write-CiLogLine -Value $_ -Writer $writer }
        $code = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
        Write-CiLogLine -Value "<== exit code $code" -Writer $writer
        return $code
    }
    finally {
        $writer.Flush()
        $writer.Dispose()
    }
}

function Get-CISetupLayout {
    $scriptsDir = $PSScriptRoot
    $parent = Split-Path -Parent $scriptsDir

    # フォルダ名は新 CISetup / 旧 cisetup の両方を大文字小文字非区別で許容する。
    if ((Split-Path -Leaf $parent) -ieq 'cisetup' -or (Split-Path -Leaf $parent) -ieq 'CISetup') {
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
            logRetentionCount = 10000
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
        throw "cisetup.config.json not found under CISetup/. Run Configure.ps1 (GUI) to create settings."
    }

    # ---- ビルドプロファイル（dotnet / custom）----
    $build = $config.build
    $buildProfile = if ($build -and $build.profile) { ([string]$build.profile).Trim().ToLower() } else { 'dotnet' }
    if ($buildProfile -ne 'custom') { $buildProfile = 'dotnet' }
    $presetId = if ($build -and $build.preset) { ([string]$build.preset).Trim().ToLower() } else { '' }
    $isFpga = $presetId.StartsWith('fpga-')

    $buildCommand = if ($build) { [string]$build.buildCommand } else { '' }
    $lintCommand = if ($build) { [string]$build.lintCommand } else { '' }
    $analyzeCommand = if ($build) { [string]$build.analyzeCommand } else { '' }
    $publishCommand = if ($build) { [string]$build.publishCommand } else { '' }
    $testCommand = if ($build) { [string]$build.testCommand } else { '' }
    $artifactGlob = if ($build) { [string]$build.artifactGlob } else { '' }
    # 未設定なら publish 側でエージェント OS から補う。
    $runtimeIdentifier = if ($build) { ([string]$build.runtimeIdentifier).Trim() } else { '' }
    $analysisExcludePaths = if ($build) { ([string]$build.analysisExcludePaths).Trim() } else { '' }
    $testProject = if ($config.project.testProject) { (ConvertTo-PlatformPath $config.project.testProject).Trim() } else { '' }

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
    elseif (-not $isFpga -and [string]::IsNullOrWhiteSpace($buildCommand)) {
        throw "cisetup.config.json: build.buildCommand is required for the custom profile."
    }

    $storage = $config.storage
    $logsDir = if ($storage -and $storage.logsDir) { $storage.logsDir.Trim() } else { 'logs' }
    $releasesDir = if ($storage -and $storage.releasesDir) { $storage.releasesDir.Trim() } else { 'releases' }
    $analysisDirName = if ($storage -and $storage.analysisDir) { $storage.analysisDir.Trim() } else { 'analysis' }
    $useDateSubfolder = if ($storage -and $null -ne $storage.useDateSubfolder) { [bool]$storage.useDateSubfolder } else { $true }
    $testsDir = if ($storage -and $storage.testsDir) { $storage.testsDir.Trim() } else { 'tests' }
    $sourceDir = if ($storage -and $storage.sourceDir) { $storage.sourceDir.Trim() } else { 'source' }
    $archiveSource = if ($storage -and $null -ne $storage.archiveSource) { [bool]$storage.archiveSource } else { $false }
    # カテゴリ有効フラグ（未設定＝後方互換で有効）。false のカテゴリは配置(deploy)をスキップする。
    $enableLogs = if ($storage -and $null -ne $storage.enableLogs) { [bool]$storage.enableLogs } else { $true }
    $enableReleases = if ($storage -and $null -ne $storage.enableReleases) { [bool]$storage.enableReleases } else { $true }
    $enableAnalysis = if ($storage -and $null -ne $storage.enableAnalysis) { [bool]$storage.enableAnalysis } else { $true }
    $enableTests = if ($storage -and $null -ne $storage.enableTests) { [bool]$storage.enableTests } else { $true }

    # 書き込み先・閲覧 URL は複数対応（配列。旧単一キーも読む）。
    $basePaths = Get-ConfigList $storage @('basePaths', 'basePath')
    $releaseUrls = Get-ConfigList $storage @('releaseUrls', 'releaseUrl')
    $analysisUrls = Get-ConfigList $storage @('analysisUrls', 'analysisUrl')
    $logsUrls = Get-ConfigList $storage @('logsUrls', 'logsUrl')
    $testsUrls = Get-ConfigList $storage @('testsUrls', 'testsUrl')
    $sourceUrls = Get-ConfigList $storage @('sourceUrls', 'sourceUrl')

    $jenkins = $config.jenkins
    $ciFileServers = Get-ConfigList $jenkins @('ciFileServers', 'ciFileServer')

    # 個人 ID を含む書き込み先は git 非追跡の cisetup.local.json に保持される（あれば優先）。
    # NOTE: このファイルは通常ワークスペース内（チェックアウト対象ディレクトリ配下）に置く運用のため、
    # git checkout が「フレッシュクローン」にフォールバックした場合（例: 一時的な git サーバーエラー
    # で .git が不完全な状態になり、retry() での再チェックアウト時に git plugin がワークスペースを
    # 丸ごと削除して再クローンするケース）に、このファイルも一緒に失われうる。
    # そのため、ワークスペースの「外側」（ワークスペースの兄弟パス）にも同名の内容を置けるようにし、
    # ワークスペースが再クローンされても書き込み先設定が失われないようにする（両方あれば
    # ワークスペース内を優先。ワークスペース内が無い/空のときのみ兄弟パスを使う）。
    $localPath = if ($layout.Layout -eq 'cisetup') { Join-Path $layout.CiDir 'cisetup.local.json' } else { Join-Path $root 'cisetup.local.json' }
    $externalLocalPath = Join-Path (Split-Path -Parent $root) ("$(Split-Path -Leaf $root).cisetup.local.json")

    function Import-LocalOverrides {
        param([string]$Path)
        if (-not (Test-Path $Path)) { return $null }
        try {
            $data = Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
            return [PSCustomObject]@{
                BasePaths     = Get-ConfigList $data @('basePaths', 'basePath')
                CiFileServers = Get-ConfigList $data @('ciFileServers', 'ciFileServer')
                ReleaseUrls   = Get-ConfigList $data @('releaseUrls', 'releaseUrl')
                AnalysisUrls  = Get-ConfigList $data @('analysisUrls', 'analysisUrl')
                LogsUrls      = Get-ConfigList $data @('logsUrls', 'logsUrl')
                TestsUrls     = Get-ConfigList $data @('testsUrls', 'testsUrl')
                SourceUrls    = Get-ConfigList $data @('sourceUrls', 'sourceUrl')
            }
        }
        catch {
            Write-Warning "Failed to read $Path : $_"
            return $null
        }
    }

    function Test-LocalOverridesEmpty {
        param($Overrides)
        if (-not $Overrides) { return $true }
        return (
            $Overrides.BasePaths.Count -eq 0 -and
            $Overrides.CiFileServers.Count -eq 0 -and
            $Overrides.ReleaseUrls.Count -eq 0 -and
            $Overrides.AnalysisUrls.Count -eq 0 -and
            $Overrides.LogsUrls.Count -eq 0 -and
            $Overrides.TestsUrls.Count -eq 0 -and
            $Overrides.SourceUrls.Count -eq 0
        )
    }

    $localOverrides = Import-LocalOverrides -Path $localPath
    if (Test-LocalOverridesEmpty $localOverrides) {
        $externalOverrides = Import-LocalOverrides -Path $externalLocalPath
        if ($externalOverrides) { $localOverrides = $externalOverrides }
    }
    if ($localOverrides) {
        if ($localOverrides.BasePaths.Count -gt 0) { $basePaths = $localOverrides.BasePaths }
        if ($localOverrides.CiFileServers.Count -gt 0) { $ciFileServers = $localOverrides.CiFileServers }
        if ($localOverrides.ReleaseUrls.Count -gt 0) { $releaseUrls = $localOverrides.ReleaseUrls }
        if ($localOverrides.AnalysisUrls.Count -gt 0) { $analysisUrls = $localOverrides.AnalysisUrls }
        if ($localOverrides.LogsUrls.Count -gt 0) { $logsUrls = $localOverrides.LogsUrls }
        if ($localOverrides.TestsUrls.Count -gt 0) { $testsUrls = $localOverrides.TestsUrls }
        if ($localOverrides.SourceUrls.Count -gt 0) { $sourceUrls = $localOverrides.SourceUrls }
    }

    return [PSCustomObject]@{
        ProjectName = $config.project.name
        SolutionFile = $config.project.solutionFile
        PublishProject = (ConvertTo-PlatformPath $config.project.publishProject)
        TestProject = $testProject
        ArtifactPrefix = if ([string]::IsNullOrWhiteSpace($config.project.artifactPrefix)) { $config.project.name } else { $config.project.artifactPrefix }
        Profile = $buildProfile
        Preset = $presetId
        BuildCommand = $buildCommand
        LintCommand = $lintCommand
        AnalyzeCommand = $analyzeCommand
        PublishCommand = $publishCommand
        TestCommand = $testCommand
        ArtifactGlob = $artifactGlob
        RuntimeIdentifier = $runtimeIdentifier
        AnalysisExcludePaths = $analysisExcludePaths
        StorageBasePaths = $basePaths
        StorageBasePath = if ($basePaths.Count -gt 0) { $basePaths[0] } else { '' }
        LogsDir = (ConvertTo-PlatformPath $logsDir)
        ReleasesDir = (ConvertTo-PlatformPath $releasesDir)
        AnalysisDir = (ConvertTo-PlatformPath $analysisDirName)
        TestsDir = (ConvertTo-PlatformPath $testsDir)
        SourceDir = (ConvertTo-PlatformPath $sourceDir)
        ArchiveSource = $archiveSource
        EnableLogs = $enableLogs
        EnableReleases = $enableReleases
        EnableAnalysis = $enableAnalysis
        EnableTests = $enableTests
        UseDateSubfolder = $useDateSubfolder
        ReleaseUrls = $releaseUrls
        AnalysisUrls = $analysisUrls
        LogsUrls = $logsUrls
        TestsUrls = $testsUrls
        SourceUrls = $sourceUrls
        ReleaseUrl = if ($releaseUrls.Count -gt 0) { $releaseUrls[0] } else { '' }
        AnalysisUrl = if ($analysisUrls.Count -gt 0) { $analysisUrls[0] } else { '' }
        LogsUrl = if ($logsUrls.Count -gt 0) { $logsUrls[0] } else { '' }
        TestsUrl = if ($testsUrls.Count -gt 0) { $testsUrls[0] } else { '' }
        SourceUrl = if ($sourceUrls.Count -gt 0) { $sourceUrls[0] } else { '' }
        CiFileServers = $ciFileServers
        CiFileServer = if ($ciFileServers.Count -gt 0) { $ciFileServers[0] } else { '' }
        Root = $root
        CiDir = $layout.CiDir
    }
}

# device-platform は C# preview 構文を含む。顧客側の修正はすぐ入らないため、
# サブモジュールのソースは変更せず、コンパイル中だけこのディレクトリ配下の
# LangVersion を preview にする。ファイルは CISetup の印があるときだけ消し、
# ソース zip や git の作業ツリーには残さない。
function Get-CiPreviewLangVersionMarker {
    return 'CISetup temporary: allow C# preview'
}

function Get-CiPreviewLangVersionRelPaths {
    return , @('vendor/DevicePlatform')
}

function Get-CiPreviewLangVersionDir {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )
    $parts = @($RelativePath -split '[\\/]' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    return (Join-PathMulti $Root $parts)
}

function Test-CiOwnedPreviewFile {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) { return $false }
    $text = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    return ($text -and $text.Contains((Get-CiPreviewLangVersionMarker)))
}

function Remove-CiPreviewLangVersionOverride {
    param([Parameter(Mandatory = $true)][string]$Root)
    foreach ($rel in (Get-CiPreviewLangVersionRelPaths)) {
        $dir = Get-CiPreviewLangVersionDir -Root $Root -RelativePath $rel
        foreach ($name in @('Directory.Build.props', 'Directory.Build.targets')) {
            $path = Join-Path $dir $name
            if (Test-CiOwnedPreviewFile -Path $path) {
                Remove-Item -LiteralPath $path -Force
            }
        }
    }
}

function Add-CiPreviewLangVersionOverride {
    param([Parameter(Mandatory = $true)][string]$Root)
    $marker = Get-CiPreviewLangVersionMarker
    $xml = @"
<Project>
  <!-- $marker in this directory until upstream builds on stable C#. -->
  <PropertyGroup>
    <LangVersion>preview</LangVersion>
  </PropertyGroup>
</Project>
"@
    foreach ($rel in (Get-CiPreviewLangVersionRelPaths)) {
        $dir = Get-CiPreviewLangVersionDir -Root $Root -RelativePath $rel
        if (-not (Test-Path -LiteralPath $dir)) { continue }
        $props = Join-Path $dir 'Directory.Build.props'
        $targets = Join-Path $dir 'Directory.Build.targets'
        $chosen = $null
        if (-not (Test-Path -LiteralPath $props) -or (Test-CiOwnedPreviewFile -Path $props)) {
            $chosen = $props
        }
        elseif (-not (Test-Path -LiteralPath $targets) -or (Test-CiOwnedPreviewFile -Path $targets)) {
            $chosen = $targets
        }
        else {
            Write-Warning "LangVersion=preview を入れられません。既存の Directory.Build.props と Directory.Build.targets は変更していません: $dir"
            continue
        }
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($chosen, ($xml.Trim() + "`r`n"), $utf8)
        Write-Host "==> LangVersion=preview (temporary): $rel"
    }
}
