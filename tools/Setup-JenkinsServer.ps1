# 何も入っていない Windows サーバーに、CISetup から接続できる状態までを一度に用意する。
# 管理者の PowerShell で、Jenkins を動かすサーバー上で実行する。
#   powershell -ExecutionPolicy Bypass -File .\tools\Setup-JenkinsServer.ps1 -JenkinsUrl http://ci-server:8080/ -AdminPassword <password>
# -AdminPassword を省略し、パスワードファイルがなければ、パスワードを生成して保存する。
# 対象は、Jenkins、Git、JDK、.NET が入っていないサーバー。別 PC のエージェントは -SkipAgent。
# 既に入っているものは二度入れない。Git は git.exe、.NET は -DotNetSdk、JDK は 21 または 25、
# Jenkins は MSI の登録を見る。MSI 版の Jenkins があるときは、WAR の配置から先は行わない。
param(
    [string]$AdminUser = "admin",
    [string]$AdminPassword = "",
    [string]$JenkinsHome = "C:\jenkins",
    [int]$Port = 8080,
    [string]$JenkinsUrl = "",
    [string]$AgentName = "windows-agent",
    [string]$AgentWorkDir = "C:\Jenkins\workspace",
    [string]$FileShare = "",
    [string]$ProjectPath = "",
    [string]$CISetupExe = "",
    [switch]$SkipAgent,
    # 8.0 のようなチャネルか、8.0.428 のような版。既定は 8.0 チャネル。
    [string]$DotNetSdk = "8.0"
)

$ErrorActionPreference = "Stop"
# Windows PowerShell 5.1 は進捗表示のせいで大きなファイルの取得が極端に遅くなる。
$ProgressPreference = "SilentlyContinue"
# Windows Server 2016 以前の PowerShell 5.1 は、既定だと TLS 1.2 を使わない。
$tls = [Net.SecurityProtocolType]::Tls12
if ([enum]::GetNames([Net.SecurityProtocolType]) -contains "Tls13") {
    $tls = $tls -bor [Net.SecurityProtocolType]::Tls13
}
[Net.ServicePointManager]::SecurityProtocol = $tls
$script:JenkinsSession = $null
$script:FirewallFailures = @()

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message"
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-IcaclsFailed([string]$Output, [int]$ExitCode) {
    if ($ExitCode -ne 0) {
        return $true
    }
    return $Output -match 'Failed processing [1-9]|処理に失敗した\s*[1-9]|Access is denied|アクセスが拒否'
}

function Restrict-Acl([string]$Path) {
    # サーバー起動時に SYSTEM が実行するファイルと、秘密情報を含むファイルを、一般ユーザーから
    # 書き換え・読み取りできないようにする。継承を切り、SYSTEM と Administrators だけに権限を与える。
    # (OI)(CI) を /T でファイルへ付けると、ファイル側の権限が空になり実行できなくなる。
    # フォルダには継承できる権限を付け、既存の中身は親から継承し直す。
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $item = Get-Item -LiteralPath $Path
    if (-not $item.PSIsContainer) {
        $result = Invoke-Icacls @($item.FullName, "/inheritance:r", "/grant:r", "*S-1-5-18:F", "*S-1-5-32-544:F", "/C", "/Q") "アクセス権を設定"
        if (Test-IcaclsFailed $result.Output $result.ExitCode) {
            throw "アクセス権を制限できませんでした: $($item.FullName)`n$($result.Output)"
        }
        return
    }
    $result = Invoke-Icacls @($item.FullName, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)(F)", "*S-1-5-32-544:(OI)(CI)(F)", "/C", "/Q") "アクセス権を設定"
    if (Test-IcaclsFailed $result.Output $result.ExitCode) {
        throw "アクセス権を制限できませんでした: $($item.FullName)`n$($result.Output)"
    }
    $children = @(Get-ChildItem -LiteralPath $item.FullName -Force -ErrorAction SilentlyContinue)
    if ($children.Count -eq 0) {
        return
    }
    $result = Invoke-Icacls @("$($item.FullName)\*", "/reset", "/T", "/C", "/Q") "アクセス権を設定"
    if (Test-IcaclsFailed $result.Output $result.ExitCode) {
        throw "アクセス権を制限できませんでした: $($item.FullName)`n$($result.Output)"
    }
}

function New-RandomPassword([int]$Length) {
    # 英数字だけを使う。引用符や記号は、Groovy とコマンドラインでの扱いが難しいため使わない。
    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

function Test-SamePath([string]$Left, [string]$Right) {
    if (-not $Left -or -not $Right) { return $false }
    return $Left.TrimEnd("\").Equals($Right.TrimEnd("\"), [StringComparison]::OrdinalIgnoreCase)
}

function Test-UnderPath([string]$Path, [string]$Root) {
    if (-not $Path -or -not $Root) { return $false }
    $full = [System.IO.Path]::GetFullPath($Path)
    $rootFull = [System.IO.Path]::GetFullPath($Root)
    if (-not $rootFull.EndsWith("\")) { $rootFull += "\" }
    return $full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase) -or (Test-SamePath $full $rootFull.TrimEnd("\"))
}

function Get-JavaMajorVersion([string]$JavaExe) {
    if (-not (Test-Path -LiteralPath $JavaExe)) { return 0 }
    $output = & cmd.exe /c "`"$JavaExe`" -version 2>&1" | Out-String
    if ($output -match 'version "1\.(?<old>[0-9]+)') { return [int]$Matches.old }
    if ($output -match 'version "(?<major>[0-9]+)') { return [int]$Matches.major }
    return 0
}

function Find-Java21Or25 {
    # C:\ 全体は探さない。スクリプトが置いた JDK と、通常のインストール先、PATH 上の java だけを見る。
    $candidates = @()
    if (Test-Path -LiteralPath "C:\jdk21") {
        $candidates += @(Get-ChildItem -LiteralPath "C:\jdk21" -Filter java.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\bin\\java\.exe$' })
    }
    Refresh-Path
    $command = Get-Command java -ErrorAction SilentlyContinue
    if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source)) {
        $candidates += Get-Item -LiteralPath $command.Source
    }
    foreach ($pattern in @(
        "C:\Program Files\Eclipse Adoptium\jdk-2*\bin\java.exe",
        "C:\Program Files\Java\jdk-2*\bin\java.exe",
        "C:\Program Files\Microsoft\jdk-2*\bin\java.exe",
        "C:\Program Files\Zulu\zulu-2*\bin\java.exe"
    )) {
        $candidates += @(Get-Item -Path $pattern -ErrorAction SilentlyContinue)
    }
    $seen = @{}
    foreach ($item in $candidates) {
        if (-not $item) { continue }
        $path = $item.FullName
        if ($seen.ContainsKey($path.ToLowerInvariant())) { continue }
        $seen[$path.ToLowerInvariant()] = $true
        $major = Get-JavaMajorVersion $path
        if ($major -eq 21 -or $major -eq 25) {
            return [pscustomobject]@{ Path = $path; Major = $major }
        }
    }
    return $null
}

function Get-DotNetSdkRequirement([string]$Spec) {
    $text = if ([string]::IsNullOrWhiteSpace($Spec)) { "8.0" } else { $Spec.Trim() }
    if ($text -match '^\d+\.0$') {
        return [pscustomobject]@{ Kind = "channel"; Spec = $text; Major = $text.Split(".")[0] }
    }
    if ($text -match '^\d+\.\d+\.\d+$') {
        return [pscustomobject]@{ Kind = "version"; Spec = $text; Major = $text.Split(".")[0] }
    }
    throw ".NET SDK の指定は 8.0 のようなチャネルか、8.0.428 のような版にしてください: $text"
}

function Test-SdkListMatches([string]$Listed, $Requirement) {
    foreach ($line in ($Listed -split "`r?`n")) {
        $version = ($line.Trim() -split '\s+', 2)[0]
        if (-not $version) { continue }
        if ($Requirement.Kind -eq "version") {
            if ($version -eq $Requirement.Spec) { return $true }
        }
        elseif ($version.StartsWith($Requirement.Major + ".")) {
            return $true
        }
    }
    return $false
}

function Test-DotNetSdk([string]$Exe, $Requirement) {
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }
    $sdks = & $Exe --list-sdks 2>&1 | Out-String
    return Test-SdkListMatches $sdks $Requirement
}

function Find-DotNetSdk($Requirement) {
    Refresh-Path
    $candidates = @()
    $command = Get-Command dotnet -ErrorAction SilentlyContinue
    if ($command -and $command.Source) { $candidates += $command.Source }
    $candidates += @("C:\Program Files\dotnet\dotnet.exe", "C:\dotnet\dotnet.exe")
    $seen = @{}
    foreach ($exe in $candidates) {
        if (-not $exe) { continue }
        $key = $exe.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        if (Test-DotNetSdk $exe $Requirement) { return $exe }
    }
    return $null
}

function Get-InstalledMsiJenkins {
    $roots = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($root in $roots) {
        foreach ($item in @(Get-ItemProperty -Path $root -ErrorAction SilentlyContinue)) {
            $name = [string]$item.DisplayName
            if ($name -match '^Jenkins( \d|$)' -and $item.WindowsInstaller -eq 1) {
                return $item
            }
        }
    }
    return $null
}

function Add-MachinePathFront([string]$Entry) {
    if (-not (Test-Path $Entry)) {
        throw "PATH に追加する場所がありません: $Entry"
    }
    $current = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $parts = @()
    if ($current) {
        $parts = $current -split ";" | Where-Object { $_ -and ($_.TrimEnd("\") -ne $Entry.TrimEnd("\")) }
    }
    $updated = (@($Entry) + $parts) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $updated, "Machine")
    Refresh-Path
}

function Test-FileSignature([string]$Path, [string]$Kind) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        if ($stream.Length -lt 2) {
            return $false
        }
        $bytes = New-Object byte[] 2
        [void]$stream.Read($bytes, 0, 2)
    } finally {
        $stream.Dispose()
    }
    if ($Kind -eq "zip") {
        return ($bytes[0] -eq 0x50 -and $bytes[1] -eq 0x4B)
    }
    if ($Kind -eq "exe") {
        return ($bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A)
    }
    return $true
}

function Get-ProgressColumns {
    # 行をウィンドウ幅いっぱいにすると折り返し、\r が前の行を消せずに積み重なる。
    # 日本語は表示幅が文字数より広いので、文字数ではなく表示幅で収める。
    $width = 78
    try {
        $window = [Console]::WindowWidth
        if ($window -gt 8) { $width = $window - 1 }
    } catch {
    }
    return $width
}

function Fit-ConsoleLine([string]$Text) {
    $max = Get-ProgressColumns
    $builder = New-Object System.Text.StringBuilder
    $width = 0
    foreach ($ch in $Text.ToCharArray()) {
        $charWidth = 1
        if ([int]$ch -gt 255) { $charWidth = 2 }
        if (($width + $charWidth) -gt $max) { break }
        [void]$builder.Append($ch)
        $width += $charWidth
    }
    while ($width -lt $max) {
        [void]$builder.Append(" ")
        $width++
    }
    return $builder.ToString()
}

function Write-ProgressLine([string]$Label, [int]$Percent, [string]$Detail) {
    if ($Percent -lt 0) { $Percent = 0 }
    if ($Percent -gt 100) { $Percent = 100 }
    $width = 28
    $filled = [int](($width * $Percent) / 100)
    $bar = ("#" * $filled).PadRight($width, "-")
    $text = "{0} [{1}] {2,3}%  {3}" -f $Label, $bar, $Percent, $Detail
    [Console]::Write("`r" + (Fit-ConsoleLine $text))
}

function Write-ActivityLine([string]$Label, [int]$ElapsedSeconds, [int]$Frame) {
    # 日本語のコンソールでは \ が円記号になる。
    $spin = "|/-*"
    $mark = $spin[$Frame % 4]
    $text = "{0} {1}  {2}秒経過" -f $Label, $mark, $ElapsedSeconds
    [Console]::Write("`r" + (Fit-ConsoleLine $text))
}

function Complete-ProgressLine {
    [Console]::WriteLine()
}

function Save-Url([string]$Url, [string]$Destination) {
    $request = [System.Net.HttpWebRequest]::Create($Url)
    $request.UserAgent = "CISetup"
    $request.AllowAutoRedirect = $true
    $response = $null
    $output = $null
    $inputStream = $null
    $lineOpen = $false
    try {
        $async = $request.BeginGetResponse($null, $null)
        $startedAt = Get-Date
        $frame = 0
        while (-not $async.IsCompleted) {
            $elapsed = [int]((Get-Date) - $startedAt).TotalSeconds
            Write-ActivityLine "サーバーへ接続" $elapsed $frame
            $frame++
            $lineOpen = $true
            [void]$async.AsyncWaitHandle.WaitOne(400)
        }
        if ($lineOpen) {
            Complete-ProgressLine
            $lineOpen = $false
        }
        $response = $request.EndGetResponse($async)
        $total = $response.ContentLength
        $inputStream = $response.GetResponseStream()
        $output = [System.IO.File]::Create($Destination)
        $buffer = New-Object byte[] (64KB)
        $readTotal = [int64]0
        $lastPercent = -1
        $lastDraw = [datetime]::MinValue
        if ($total -gt 0) {
            Write-ProgressLine "ダウンロード" 0 ("0.0 / {0:N1} MB" -f ($total / 1MB))
            $lineOpen = $true
            $lastPercent = 0
            $lastDraw = Get-Date
        }
        while (($count = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $output.Write($buffer, 0, $count)
            $readTotal += $count
            $percent = 0
            $detail = "{0:N1} MB" -f ($readTotal / 1MB)
            if ($total -gt 0) {
                $percent = [int](($readTotal * 100) / $total)
                $detail = "{0:N1} / {1:N1} MB" -f ($readTotal / 1MB), ($total / 1MB)
            }
            $now = Get-Date
            if ($percent -ne $lastPercent -or ($now - $lastDraw).TotalMilliseconds -ge 400) {
                Write-ProgressLine "ダウンロード" $percent $detail
                $lastPercent = $percent
                $lastDraw = $now
                $lineOpen = $true
            }
        }
        Write-ProgressLine "ダウンロード" 100 ("{0:N1} MB" -f ($readTotal / 1MB))
        $lineOpen = $true
    } finally {
        if ($output) { $output.Dispose() }
        if ($inputStream) { $inputStream.Dispose() }
        if ($response) { $response.Dispose() }
        elseif ($request) { $request.Abort() }
        if ($lineOpen) { Complete-ProgressLine }
    }
}

function Expand-ZipFile([string]$ZipPath, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = $null
    $started = $false
    try {
        $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        $entries = @($archive.Entries)
        $total = $entries.Count
        if ($total -eq 0) {
            throw "ZIP が空です: $ZipPath"
        }
        New-Item -ItemType Directory -Force -Path $Destination | Out-Null
        $root = [System.IO.Path]::GetFullPath($Destination)
        if (-not $root.EndsWith("\")) { $root += "\" }
        $index = 0
        $lastPercent = -1
        $started = $true
        foreach ($entry in $entries) {
            $index++
            $name = $entry.FullName.Replace("/", "\")
            if ($name.StartsWith("\") -or $name.Contains("..\")) {
                throw "ZIP のパスが不正です: $($entry.FullName)"
            }
            $target = [System.IO.Path]::GetFullPath((Join-Path $Destination $name))
            if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
                throw "ZIP のパスが展開先の外を指しています: $($entry.FullName)"
            }
            if ($entry.FullName.EndsWith("/") -or $entry.FullName.EndsWith("\")) {
                New-Item -ItemType Directory -Force -Path $target | Out-Null
            } else {
                $parent = Split-Path -Parent $target
                if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
            }
            $percent = [int](($index * 100) / $total)
            if ($percent -ne $lastPercent) {
                Write-ProgressLine "展開" $percent ("{0}/{1}" -f $index, $total)
                $lastPercent = $percent
            }
        }
    } finally {
        if ($archive) { $archive.Dispose() }
        if ($started) { Complete-ProgressLine }
    }
}

function Invoke-Icacls([string[]]$ArgumentList, [string]$Label) {
    $job = Start-Job -ScriptBlock {
        param([string[]]$ArgumentList)
        $lines = & icacls.exe @ArgumentList 2>&1
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
        [pscustomobject]@{ ExitCode = [int]$code; Output = ($lines | Out-String) }
    } -ArgumentList (,$ArgumentList)
    $startedAt = Get-Date
    $frame = 0
    try {
        while ($job.State -eq "Running") {
            $elapsed = [int]((Get-Date) - $startedAt).TotalSeconds
            Write-ActivityLine $Label $elapsed $frame
            $frame++
            Start-Sleep -Milliseconds 400
        }
        return Receive-Job -Job $job
    } finally {
        Complete-ProgressLine
        if ($job) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        }
    }
}

function Wait-External([System.Diagnostics.Process]$Process, [string]$Label) {
    $startedAt = Get-Date
    $frame = 0
    $shown = $false
    while (-not $Process.HasExited) {
        $elapsed = [int]((Get-Date) - $startedAt).TotalSeconds
        Write-ActivityLine $Label $elapsed $frame
        $frame++
        $shown = $true
        Start-Sleep -Milliseconds 400
    }
    $Process.WaitForExit()
    if ($shown) { Complete-ProgressLine }
    return $Process.ExitCode
}

function Get-FileSha256([string]$Path) {
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -lt 8MB) {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        $buffer = New-Object byte[] (1024 * 1024)
        $readTotal = [int64]0
        $total = $stream.Length
        $lastPercent = -1
        while (($count = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            [void]$sha.TransformBlock($buffer, 0, $count, $null, 0)
            $readTotal += $count
            $percent = [int](($readTotal * 100) / $total)
            if ($percent -ne $lastPercent) {
                Write-ProgressLine "SHA256 を確認" $percent ("{0:N0} MB" -f ($total / 1MB))
                $lastPercent = $percent
            }
        }
        [void]$sha.TransformFinalBlock($buffer, 0, 0)
        return ([BitConverter]::ToString($sha.Hash)).Replace("-", "").ToLowerInvariant()
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($sha) { $sha.Dispose() }
        Complete-ProgressLine
    }
}

function Test-DownloadReusable([string]$Path, [string]$Kind, [string]$ExpectedSha256) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    if ($ExpectedSha256) {
        return (Get-FileSha256 $Path) -eq $ExpectedSha256
    }
    if ($Kind -eq "text") {
        return (Get-Item -LiteralPath $Path).Length -gt 0
    }
    return Test-FileSignature $Path $Kind
}

function Download-File([string]$Url, [string]$Destination, [string]$Kind, [string]$Sha256 = "") {
    $expected = ""
    if ($Sha256) {
        $expected = $Sha256.ToLowerInvariant()
    }
    if (Test-DownloadReusable $Destination $Kind $expected) {
        Write-Host "既存のファイルを使います: $Destination"
        return
    }
    if (Test-Path -LiteralPath $Destination) {
        Write-Host "取得済みファイルが壊れているため削除します: $Destination"
        Remove-Item -LiteralPath $Destination -Force
    }
    Write-Host "ダウンロード: $Url"
    try {
        Save-Url $Url $Destination
    } catch {
        if (Test-Path -LiteralPath $Destination) {
            Remove-Item -LiteralPath $Destination -Force
        }
        throw
    }
    if (Test-DownloadReusable $Destination $Kind $expected) {
        return
    }
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Force
    }
    if ($expected) {
        throw "ダウンロードしたファイルの SHA256 が一致しません: $Destination"
    }
    throw "ダウンロードしたファイルを確認できませんでした: $Destination"
}

function Test-JenkinsUp([string]$LoginUrl) {
    try {
        $response = Invoke-WebRequest -Uri $LoginUrl -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    } catch {
        $code = $null
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
        }
        return $code -in 200, 401, 403
    }
}

function Register-StartupTask([string]$TaskName, [string]$BatPath) {
    # サーバー起動時に、ログオンしていなくても動かす。ウィンドウは開かない。
    # 異常終了したときは、タスク スケジューラが 1 分間隔で 10 回まで起動し直す。
    # SYSTEM で動くため、ジョブも SYSTEM になる。共有フォルダはコンピューターアカウントの権限が必要。
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c call `"$BatPath`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1)
    # StartWhenAvailable は付けない。起動後に登録すると、起動時刻を逃したとみなしてすぐ SYSTEM で動き、スクリプトが起動したプロセスと重なる。
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
}

function Invoke-WithStartupTasksSuspended([scriptblock]$Action, [string[]]$TaskNames) {
    # 起動タスクが動かしているプロセスを止める前にタスクを無効化する。
    # 無効化しないと、強制終了を失敗とみなして 1 分後にタスクが二重起動する。
    if (-not $TaskNames) {
        $TaskNames = @("CISetup Jenkins", "CISetup Jenkins Agent")
    }
    $restore = @()
    try {
        foreach ($name in $TaskNames) {
            $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
            if (-not $task -or $task.State -eq "Disabled") {
                continue
            }
            $restore += $name
            Disable-ScheduledTask -TaskName $name | Out-Null
            Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        }
        & $Action
    } finally {
        foreach ($name in $restore) {
            if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
                Enable-ScheduledTask -TaskName $name | Out-Null
            }
        }
    }
}

function Wait-Jenkins([string]$LoginUrl, [int]$Minutes = 8, [string]$Label = "Jenkins の起動を待つ") {
    $deadline = (Get-Date).AddMinutes($Minutes)
    $startedAt = Get-Date
    $frame = 0
    $shown = $false
    $lastCheck = [datetime]::MinValue
    while ((Get-Date) -lt $deadline) {
        $now = Get-Date
        if (($now - $lastCheck).TotalSeconds -ge 5) {
            $lastCheck = $now
            if (Test-JenkinsUp $LoginUrl) {
                if ($shown) { Complete-ProgressLine }
                return
            }
        }
        $elapsed = [int]($now - $startedAt).TotalSeconds
        Write-ActivityLine $Label $elapsed $frame
        $frame++
        $shown = $true
        Start-Sleep -Milliseconds 400
    }
    if ($shown) { Complete-ProgressLine }
    throw "Jenkins が $Minutes 分以内に $LoginUrl で応答しませんでした。$(Join-Path $JenkinsHome 'jenkins.log') を確認してください。画面で追うときは、管理者 PowerShell で start-jenkins.bat window を実行します。"
}

function Get-BasicHeaders([string]$BaseUrl, [string]$User, [string]$Password) {
    $script:JenkinsSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $pair = "{0}:{1}" -f $User, $Password.Trim()
    $token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
    $headers = @{ Authorization = "Basic $token" }
    try {
        $crumb = Invoke-RestMethod -WebSession $script:JenkinsSession -Headers $headers -Uri ($BaseUrl + "crumbIssuer/api/json") -TimeoutSec 30
        $headers[$crumb.crumbRequestField] = $crumb.crumb
    } catch {
        Write-Host "crumb は取得しませんでした。そのまま Script Console を呼びます。"
    }
    return $headers
}

function Invoke-JenkinsGroovy([string]$BaseUrl, [hashtable]$Headers, [string]$Script) {
    $response = Invoke-WebRequest -Method Post -WebSession $script:JenkinsSession -Uri ($BaseUrl + "scriptText") -Headers $Headers -Body @{ script = $Script } -UseBasicParsing -TimeoutSec 600
    return $response.Content
}

function Invoke-PluginCheck([string]$BaseUrl, [hashtable]$Headers, [string]$Script) {
    try {
        return Invoke-JenkinsGroovy -BaseUrl $BaseUrl -Headers $Headers -Script $Script
    } catch {
        return "ERROR: " + $_.Exception.Message
    }
}

function Test-GroovyFailure([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $true
    }
    return $Text -match '(?m)^\s*(Result:\s*)?ERROR:|Exception|groovy\.lang|at hudson\.|at jenkins\.|at java\.'
}

function Ensure-FirewallRule([string]$Name, [int]$LocalPort, [string[]]$RemoteAddress, [string]$Program) {
    # ポートだけの規則では、java.exe の初回待ち受けで Windows が確認画面を出す。
    # 起動前にプログラムを規則へ入れると、その画面は出ない。
    $targets = @([pscustomobject]@{ Name = $Name; Remote = @($RemoteAddress | Where-Object { $_ }) })
    foreach ($target in $targets) {
        try {
            $existing = @(Get-NetFirewallRule -DisplayName $target.Name -ErrorAction SilentlyContinue)
            if (-not $existing) {
                $params = @{
                    DisplayName = $target.Name
                    Direction   = "Inbound"
                    Protocol    = "TCP"
                    LocalPort   = $LocalPort
                    Action      = "Allow"
                }
                if ($target.Remote.Count -gt 0) {
                    $params.RemoteAddress = [string[]]$target.Remote
                }
                New-NetFirewallRule @params | Out-Null
            }
            if ($Program) {
                Set-NetFirewallRule -DisplayName $target.Name -Program $Program -Enabled True | Out-Null
            } else {
                Set-NetFirewallRule -DisplayName $target.Name -Enabled True | Out-Null
            }
            if ($target.Remote.Count -gt 0) {
                Set-NetFirewallRule -DisplayName $target.Name -RemoteAddress ([string[]]$target.Remote) | Out-Null
            }
        } catch {
            $script:FirewallFailures += $target.Name
            Write-Host "ファイアウォール規則を追加できませんでした: $($target.Name)。$($_.Exception.Message)"
        }
    }
}

function Remove-FirewallRule([string]$Name) {
    $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
    if (-not $existing) {
        return
    }
    try {
        Remove-NetFirewallRule -DisplayName $Name
        Write-Host "不要なファイアウォール規則を削除しました: $Name"
    } catch {
        $script:FirewallFailures += $Name
        Write-Host "ファイアウォール規則を削除できませんでした: $Name"
    }
}

function Start-BackgroundBat([string]$BatPath) {
    # スクリプトからは画面を開かない。出力は各ログファイルへ追記する。
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c call `"$BatPath`"" -WindowStyle Hidden
}

function Escape-Groovy([string]$Value) {
    return $Value.Replace("\", "\\").Replace('"', '\"').Replace('$', '\$')
}

function Stop-JavaProcess([string]$CommandLinePattern) {
    $targets = @(Get-CimInstance Win32_Process -Filter "Name = 'java.exe'" |
        Where-Object { $_.CommandLine -match $CommandLinePattern })
    foreach ($target in $targets) {
        $parentId = $target.ParentProcessId
        Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $parentId" -ErrorAction SilentlyContinue
        if ($parent -and $parent.Name -eq "cmd.exe" -and $parent.CommandLine -match 'start-(jenkins|agent)\.bat') {
            Stop-Process -Id $parentId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Stop-JenkinsProcess {
    Stop-JavaProcess 'jenkins\.war'
}

function Stop-AgentLauncher {
    # Java が起動する前の start-agent.bat も止める。待受確認で残った PowerShell を再実行時に重ねない。
    $cmds = @(Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" |
        Where-Object { $_.CommandLine -match 'start-agent\.bat' })
    foreach ($cmd in $cmds) {
        Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $cmd.ProcessId } | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Stop-Process -Id $cmd.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Stop-JavaProcess 'agent\.jar'
}

function Get-LogTail([string]$Path, [int]$Lines = 25) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }
    return ((Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue) -join "`n")
}

function Wait-AgentOnline([string]$Url, [hashtable]$Headers, [int]$Minutes) {
    $deadline = (Get-Date).AddMinutes($Minutes)
    while ((Get-Date) -lt $deadline) {
        try {
            $node = Invoke-RestMethod -WebSession $script:JenkinsSession -Headers $Headers -Uri $Url -TimeoutSec 15
            if (-not $node.offline) {
                return $true
            }
        } catch {
            Write-Host "エージェント状態の取得を再試行します。"
        }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Test-ApiTokenText([string]$Value) {
    return $Value -match '^[0-9a-fA-F]{32,64}$'
}

function Merge-JsonFile([string]$Path, [hashtable]$Updates) {
    $data = [ordered]@{}
    if (Test-Path -LiteralPath $Path) {
        $existing = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        foreach ($property in $existing.PSObject.Properties) {
            $data[$property.Name] = $property.Value
        }
    }
    foreach ($key in $Updates.Keys) {
        $data[$key] = $Updates[$key]
    }
    $json = (ConvertTo-Json -InputObject $data -Depth 6) + "`n"
    [System.IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding $false))
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "管理者として実行してください。Jenkins の導入、PATH、ファイアウォールを変更します。"
}

$localBase = "http://localhost:$Port/"
if (-not $JenkinsUrl) {
    $JenkinsUrl = $localBase
}
$JenkinsUrl = $JenkinsUrl.TrimEnd("/") + "/"

$passwordFile = Join-Path $JenkinsHome "cisetup-admin-password.txt"
if ([string]::IsNullOrEmpty($AdminPassword)) {
    if (Test-Path -LiteralPath $passwordFile) {
        $AdminPassword = (Get-Content -LiteralPath $passwordFile -Raw) -replace '[\r\n]+$', ''
        Write-Host "保存済みの管理者パスワードを使います: $passwordFile"
    } else {
        $AdminPassword = New-RandomPassword 24
        Write-Host "管理者パスワードを生成しました。Jenkins の起動前に $passwordFile へ保存し、完了時にも表示します。"
    }
}
if ($AdminPassword -notmatch '^[\x21-\x7E]+$') {
    throw "管理者パスワードは、空白を含まない ASCII の表示文字で指定してください。保存済みの値が使えない場合は、$passwordFile を削除してから再実行してください。"
}

$script:OwnJdk = $false
$script:OwnDotnet = $false

Write-Step "Git を確認"
Refresh-Path
$git = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path -LiteralPath $git)) {
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCommand -and $gitCommand.Source -and (Test-Path -LiteralPath $gitCommand.Source)) {
        $git = $gitCommand.Source
    }
}
if (Test-Path -LiteralPath $git) {
    Write-Host "入っている Git を使います: $git"
} else {
    $installer = "C:\git-setup.exe"
    Download-File "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.2/Git-2.47.1.2-64-bit.exe" $installer "exe" "5f2350757f9781125cd660478b31c37698d9662aed25b4b02e92da393289564c"
    $gitInstall = Start-Process -FilePath $installer -ArgumentList "/VERYSILENT", "/NORESTART" -PassThru
    $gitCode = Wait-External $gitInstall "Git をインストール"
    if ($gitCode -ne 0) {
        throw "Git のインストーラーが終了コード $gitCode で終了しました。"
    }
    Refresh-Path
    $git = "C:\Program Files\Git\cmd\git.exe"
}
if (-not (Test-Path -LiteralPath $git)) {
    throw "Git のインストール後も $git が見つかりません。C:\git-setup.exe を削除して再実行してください。"
}
& $git --version

if (-not $SkipAgent) {
    $dotnetRequirement = Get-DotNetSdkRequirement $DotNetSdk
    Write-Step ".NET SDK $($dotnetRequirement.Spec) を確認"
    $dotnet = Find-DotNetSdk $dotnetRequirement
    if ($dotnet) {
        Write-Host "入っている .NET SDK $($dotnetRequirement.Spec) を使います: $dotnet"
    } else {
        $dotnet = "C:\dotnet\dotnet.exe"
        # 以前の実行でファイルの権限が空になっている場合は、起動確認より先に継承し直す。
        if (Test-Path -LiteralPath "C:\dotnet") {
            Restrict-Acl "C:\dotnet"
        }
        $installerScript = "C:\dotnet-install.ps1"
        Download-File "https://dot.net/v1/dotnet-install.ps1" $installerScript "text"
        $installArgs = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", $installerScript,
            "-InstallDir", "C:\dotnet"
        )
        if ($dotnetRequirement.Kind -eq "version") {
            $installArgs += @("-Version", $dotnetRequirement.Spec)
        } else {
            $installArgs += @("-Channel", $dotnetRequirement.Spec)
        }
        & powershell @installArgs
        if ($LASTEXITCODE -ne 0) {
            throw ".NET SDK のインストーラーが終了コード $LASTEXITCODE で終了しました。C:\dotnet-install.ps1 を削除して再実行してください。"
        }
    }
    if (-not (Test-Path -LiteralPath $dotnet)) {
        throw ".NET SDK の展開後も $dotnet が見つかりません。C:\dotnet-install.ps1 と C:\dotnet を削除して再実行してください。"
    }
    $sdks = & $dotnet --list-sdks 2>&1 | Out-String
    if (-not (Test-SdkListMatches $sdks $dotnetRequirement)) {
        throw ".NET SDK $($dotnetRequirement.Spec) が見つかりません。C:\dotnet を削除して再実行してください。`n$sdks"
    }
    if (Test-UnderPath $dotnet "C:\dotnet") {
        $script:OwnDotnet = $true
        Restrict-Acl "C:\dotnet"
        Add-MachinePathFront "C:\dotnet"
    }
    & $dotnet --version
}

Write-Step "JDK 21 を確認"
$existingJava = Find-Java21Or25
if ($existingJava) {
    $java = $existingJava.Path
    Write-Host "入っている Java $($existingJava.Major) を使います: $java"
    if (Test-UnderPath $java "C:\jdk21") {
        $script:OwnJdk = $true
        Restrict-Acl "C:\jdk21"
        Add-MachinePathFront (Split-Path -Parent $java)
    }
} else {
    $zip = "C:\jdk21.zip"
    Download-File "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jdk_x64_windows_hotspot_21.0.13_9.zip" $zip "zip" "a4dbaa05fca4bd89d84584e58c459bd732efebb1722af80ab13c6516832004f9"
    if (Test-Path "C:\jdk21") {
        Remove-Item -Path "C:\jdk21" -Recurse -Force
    }
    try {
        Expand-ZipFile $zip "C:\jdk21"
    } catch {
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        throw "JDK 21 の展開に失敗しました。C:\jdk21.zip を削除済みです。再実行してください。詳細: $($_.Exception.Message)"
    }
    $javaCmd = Get-ChildItem -LiteralPath "C:\jdk21" -Filter java.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\bin\\java\.exe$' } |
        Select-Object -First 1
    if (-not $javaCmd) {
        throw "JDK 21 の展開後も java.exe が見つかりません。C:\jdk21.zip を削除して再実行してください。現在の Jenkins LTS は Java 21 または 25 が必要です。"
    }
    $script:OwnJdk = $true
    Restrict-Acl "C:\jdk21"
    $java = $javaCmd.FullName
    Add-MachinePathFront (Split-Path -Parent $java)
}
cmd.exe /c "`"$java`" -version 2>&1" | ForEach-Object { Write-Host $_ }

$msiJenkins = Get-InstalledMsiJenkins
if ($msiJenkins) {
    Write-Step "Jenkins を確認"
    Write-Host "MSI 版の Jenkins が入っているため、WAR の配置、起動、プラグイン導入は行いません。"
    Write-Host "表示名: $($msiJenkins.DisplayName)"
    if ($msiJenkins.DisplayVersion) { Write-Host "バージョン: $($msiJenkins.DisplayVersion)" }
    if ($msiJenkins.InstallLocation) { Write-Host "インストール先: $($msiJenkins.InstallLocation)" }
    Write-Host "既存の Jenkins はそのままです。このスクリプトの Jenkins を使う場合は、MSI 版をアンインストールしてから再実行してください。"
    exit 0
}

Write-Step "Jenkins を配置"
$war = "C:\jenkins.war"
Download-File "https://get.jenkins.io/war-stable/2.580.2/jenkins.war" $war "zip" "d98032d2401c540a35613a82ed358921fcf3166d5e6eaaaf60a7941845be3251"
Restrict-Acl $war
New-Item -ItemType Directory -Force -Path $JenkinsHome, (Join-Path $JenkinsHome "init.groovy.d"), $AgentWorkDir | Out-Null
# 権限を先に絞ってから書き込む。これで以降に作るファイルも、SYSTEM と Administrators だけが読めるようになる。
Restrict-Acl $JenkinsHome
Restrict-Acl $AgentWorkDir
# 生成したパスワードは、初期化の途中で失敗しても残るように、先にファイルへ保存する。
if (-not (Test-Path -LiteralPath $passwordFile)) {
    [System.IO.File]::WriteAllText($passwordFile, $AdminPassword, (New-Object System.Text.UTF8Encoding $false))
}

$groovyPassword = Escape-Groovy $AdminPassword
$groovyUser = Escape-Groovy $AdminUser
$groovyUrl = Escape-Groovy $JenkinsUrl
$initScript = @"
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.security.HudsonPrivateSecurityRealm
import jenkins.model.Jenkins
import jenkins.model.JenkinsLocationConfiguration

def instance = Jenkins.instance
if (!(instance.securityRealm instanceof HudsonPrivateSecurityRealm)) {
    def realm = new HudsonPrivateSecurityRealm(false)
    realm.createAccount("$groovyUser", "$groovyPassword")
    instance.setSecurityRealm(realm)
    def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
    strategy.setAllowAnonymousRead(false)
    instance.setAuthorizationStrategy(strategy)
    instance.save()
}
if (instance.getNumExecutors() != 0) {
    instance.setNumExecutors(0)
    instance.save()
}
if (instance.getSlaveAgentPort() != 50000) {
    instance.setSlaveAgentPort(50000)
    instance.save()
}
def location = JenkinsLocationConfiguration.get()
if (location.getUrl() != "$groovyUrl") {
    location.setUrl("$groovyUrl")
    location.save()
}
"@
[System.IO.File]::WriteAllText((Join-Path $JenkinsHome "init.groovy.d\01-cisetup-bootstrap.groovy"), $initScript, (New-Object System.Text.UTF8Encoding $false))

$startBatPath = Join-Path $JenkinsHome "start-jenkins.bat"
$startBat = @"
@echo off
chcp 65001 >nul
set JENKINS_HOME=$JenkinsHome
if "%1"=="window" goto visible
"$java" -Djenkins.install.runSetupWizard=false -jar "$war" --httpPort=$Port >> "%~dp0jenkins.log" 2>&1
goto :eof
:visible
"$java" -Djenkins.install.runSetupWizard=false -jar "$war" --httpPort=$Port
echo.
echo Jenkins が終了しました。上の表示を確認してください。
pause
"@
[System.IO.File]::WriteAllText($startBatPath, $startBat, (New-Object System.Text.UTF8Encoding $false))
Register-StartupTask "CISetup Jenkins" $startBatPath

Ensure-FirewallRule "CISetup Jenkins HTTP" $Port $null $java
# エージェントは localhost の TCP 50000 へ接続する。外部からは開けない。
# Windows は ::1 を送信元に指定できない。ループバック通信は受信規則の対象外なので 127.0.0.1 だけにする。
Remove-FirewallRule "CISetup Jenkins Agent v6"
if (-not $SkipAgent) {
    Ensure-FirewallRule "CISetup Jenkins Agent" 50000 @("127.0.0.1") $java
} else {
    Remove-FirewallRule "CISetup Jenkins Agent"
}

Write-Step "Jenkins を起動"
$running = Get-CimInstance Win32_Process -Filter "Name = 'java.exe'" | Where-Object { $_.CommandLine -match 'jenkins\.war' }
if (-not $running) {
    Start-BackgroundBat $startBatPath
}
Wait-Jenkins ($localBase + "login")

$headers = Get-BasicHeaders -BaseUrl $localBase -User $AdminUser -Password $AdminPassword
try {
    Invoke-WebRequest -WebSession $script:JenkinsSession -Headers $headers -Uri ($localBase + "api/json") -UseBasicParsing -TimeoutSec 30 | Out-Null
} catch {
    throw "Jenkins へのログインに失敗しました。管理者は初回起動時に一度だけ作られ、再実行でパスワードは変わりません。初回に指定したパスワードで入れない場合は、C:\jenkins を削除してから同じコマンドを再実行してください。起動時の表示は $(Join-Path $JenkinsHome 'jenkins.log') にあります。"
}
Write-Step "CISetup が必要とするプラグインを入れる"
$pluginScript = @'
def required = ["workflow-aggregator", "git", "credentials-binding", "plain-credentials", "parameterized-trigger", "naginator", "timestamper"] as String[]
def instance = jenkins.model.Jenkins.instance
def pm = instance.pluginManager
def uc = instance.updateCenter
def siteError = null
uc.sites.each { site ->
    if (siteError != null) { return }
    try {
        def result = site.updateDirectlyNow(true)
        if (result != null && String.valueOf(result.kind) != "OK") {
            siteError = "ERROR: update site " + site.id + ": " + result.message
        }
    } catch (Exception e) {
        siteError = "ERROR: update site " + site.id + ": " + e.toString()
    }
}
if (siteError != null) {
    return siteError
}
def installed = []
def missing = []
required.each { id ->
    def plugin = pm.getPlugin(id)
    if (plugin == null) { missing << id } else { installed << id }
}
if (missing.isEmpty()) {
    return "OK: all plugins already installed (" + installed.join(", ") + ")"
}
def deployed = []
def notFound = []
missing.each { id ->
    def plugin = uc.getPlugin(id)
    if (plugin == null) { notFound << id; return }
    def future = plugin.deploy()
    if (future != null) { future.get() }
    deployed << id
}
if (!notFound.isEmpty()) {
    return "ERROR: not on update site: " + notFound.join(", ")
}
return "INSTALLED: " + deployed.join(", ") + " | RESTART required"
'@
$pluginCheckScript = @'
def required = ["workflow-aggregator", "git", "credentials-binding", "plain-credentials", "parameterized-trigger", "naginator", "timestamper"] as String[]
def pm = jenkins.model.Jenkins.instance.pluginManager
def missing = []
def inactive = []
required.each { id ->
    def plugin = pm.getPlugin(id)
    if (plugin == null) { missing << id }
    else if (!plugin.isActive()) { inactive << id }
}
if (!missing.isEmpty() || !inactive.isEmpty()) {
    return "ERROR: missing=" + missing.join(",") + " inactive=" + inactive.join(",")
}
return "OK: plugins active (" + required.join(", ") + ")"
'@
$pluginResult = ""
for ($attempt = 1; $attempt -le 3; $attempt++) {
    try {
        $pluginResult = Invoke-JenkinsGroovy -BaseUrl $localBase -Headers $headers -Script $pluginScript
    } catch {
        $pluginResult = "ERROR: " + $_.Exception.Message
    }
    Write-Host $pluginResult
    if (-not (Test-GroovyFailure $pluginResult)) {
        break
    }
    if ($attempt -lt 3) {
        Write-Host "プラグインの導入を 30 秒後にやり直します（$attempt 回目に失敗）。"
        Start-Sleep -Seconds 30
    }
}
if (Test-GroovyFailure $pluginResult) {
    $firstLine = (($pluginResult -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -First 1)
    throw "プラグインの導入に 3 回失敗しました。更新サイトへの通信を確認してください。結果: $firstLine"
}
if ($pluginResult -match "RESTART required") {
    Write-Host "プラグイン反映のため Jenkins を再起動します。"
    Invoke-WithStartupTasksSuspended {
        Stop-JenkinsProcess
        Start-Sleep -Seconds 5
        Start-BackgroundBat $startBatPath
    }
    Wait-Jenkins -LoginUrl ($localBase + "login") -Label "Jenkins の再起動を待つ"
    $headers = Get-BasicHeaders -BaseUrl $localBase -User $AdminUser -Password $AdminPassword
}
$pluginCheck = Invoke-PluginCheck -BaseUrl $localBase -Headers $headers -Script $pluginCheckScript
Write-Host $pluginCheck
if (Test-GroovyFailure $pluginCheck) {
    Write-Host "プラグインが有効になっていません。Jenkins を再起動して、もう一度確認します。"
    Invoke-WithStartupTasksSuspended {
        Stop-JenkinsProcess
        Start-Sleep -Seconds 5
        Start-BackgroundBat $startBatPath
    }
    Wait-Jenkins -LoginUrl ($localBase + "login") -Label "Jenkins の再起動を待つ"
    $headers = Get-BasicHeaders -BaseUrl $localBase -User $AdminUser -Password $AdminPassword
    $pluginCheck = Invoke-PluginCheck -BaseUrl $localBase -Headers $headers -Script $pluginCheckScript
    Write-Host $pluginCheck
}
if (Test-GroovyFailure $pluginCheck) {
    throw "必要なプラグインが再起動しても有効になりませんでした。Jenkins の Plugins 画面と $(Join-Path $JenkinsHome 'jenkins.log') を確認してください。結果: $pluginCheck"
}

$secret = ""
if (-not $SkipAgent) {
    Write-Step "エージェント $AgentName を登録"
    $groovyAgent = Escape-Groovy $AgentName
    $groovyWork = Escape-Groovy $AgentWorkDir
    $agentScript = @"
import hudson.model.Node
import hudson.slaves.DumbSlave
import hudson.slaves.JNLPLauncher
import hudson.slaves.RetentionStrategy
import jenkins.model.Jenkins

def instance = Jenkins.instance
def name = "$groovyAgent"
def root = "$groovyWork"
if (instance.getNode(name) == null) {
    def slave = new DumbSlave(name, root, new JNLPLauncher())
    slave.setNumExecutors(1)
    slave.setMode(Node.Mode.NORMAL)
    slave.setRetentionStrategy(new RetentionStrategy.Always())
    slave.setNodeDescription("CISetup Windows Agent")
    instance.addNode(slave)
}
def computer = instance.getComputer(name)
if (computer == null) {
    return "ERROR: computer not found"
}
return "SECRET=" + computer.getJnlpMac()
"@
    $agentResult = Invoke-JenkinsGroovy -BaseUrl $localBase -Headers $headers -Script $agentScript
    if ($agentResult -notmatch "SECRET=(\S+)") {
        $safe = $agentResult -replace 'SECRET=\S+', 'SECRET=(非表示)'
        throw "エージェントの secret を取得できませんでした。結果: $safe"
    }
    $secret = $Matches[1].Trim()
    Write-Host "エージェントを登録しました。secret は start-agent.bat にだけ保存します。"

    $agentJar = Join-Path $AgentWorkDir "agent.jar"
    if (-not (Test-FileSignature $agentJar "zip")) {
        if (Test-Path -LiteralPath $agentJar) {
            Remove-Item -LiteralPath $agentJar -Force
        }
        Invoke-WebRequest -WebSession $script:JenkinsSession -Headers $headers -Uri ($localBase + "jnlpJars/agent.jar") -OutFile $agentJar -UseBasicParsing
        if (-not (Test-FileSignature $agentJar "zip")) {
            Remove-Item -LiteralPath $agentJar -Force -ErrorAction SilentlyContinue
            throw "agent.jar を確認できませんでした。再実行してください。"
        }
    }
    # 匿名読み取りを止めているため、トップページは 403 になる。login の 200、401、403 を起動済みとみなす。
    $agentLog = Join-Path $AgentWorkDir "agent.log"
    $agentBat = @"
@echo off
chcp 65001 >nul
powershell.exe -NoProfile -WindowStyle Hidden -Command "`$deadline=(Get-Date).AddMinutes(8); while((Get-Date) -lt `$deadline){ try { Invoke-WebRequest -Uri '${localBase}login' -UseBasicParsing -TimeoutSec 5 | Out-Null; break } catch { `$code=`$null; if (`$_.Exception.Response) { `$code=[int]`$_.Exception.Response.StatusCode }; if (`$code -in 200,401,403) { break } }; Start-Sleep -Seconds 5 }"
if "%1"=="window" goto visible
"$java" -jar "$agentJar" -url $localBase -secret $secret -name "$AgentName" -workDir "$AgentWorkDir" >> "$agentLog" 2>&1
goto :eof
:visible
"$java" -jar "$agentJar" -url $localBase -secret $secret -name "$AgentName" -workDir "$AgentWorkDir"
echo.
echo エージェントが終了しました。ログ: $agentLog
pause
"@
    $agentBatPath = Join-Path $AgentWorkDir "start-agent.bat"
    [System.IO.File]::WriteAllText($agentBatPath, $agentBat, (New-Object System.Text.UTF8Encoding $false))
    Register-StartupTask "CISetup Jenkins Agent" $agentBatPath
    $agentRunning = Get-CimInstance Win32_Process -Filter "Name = 'java.exe'" | Where-Object { $_.CommandLine -match 'agent\.jar' }
    if (-not $agentRunning) {
        Stop-AgentLauncher
        Start-BackgroundBat $agentBatPath
    }

    Write-Step "エージェントがオンラインになるのを待つ"
    $agentUrl = $localBase + "computer/" + [Uri]::EscapeDataString($AgentName) + "/api/json"
    $agentOnline = Wait-AgentOnline $agentUrl $headers 3
    if (-not $agentOnline) {
        Write-Host "エージェントがオンラインになりません。起動し直します。"
        Invoke-WithStartupTasksSuspended -TaskNames @("CISetup Jenkins Agent") -Action {
            Stop-AgentLauncher
            Start-Sleep -Seconds 3
            Start-BackgroundBat $agentBatPath
        }
        $agentOnline = Wait-AgentOnline $agentUrl $headers 3
    }
    if (-not $agentOnline) {
        $tail = Get-LogTail $agentLog
        $detail = if ($tail) { "`n--- agent.log ---`n$tail" } else { "`n$agentLog はまだありません。" }
        throw "エージェント $AgentName が起動し直しても 6 分以内にオンラインになりませんでした。$detail"
    }
    Write-Host "エージェントはオンラインです: $AgentName"
}

Write-Step "API トークンを用意"
$tokenFile = Join-Path $JenkinsHome "cisetup-api-token.txt"
$apiToken = ""
if (Test-Path -LiteralPath $tokenFile) {
    $apiToken = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
}
if (-not (Test-ApiTokenText $apiToken)) {
    if ($apiToken) {
        Write-Host "保存済みの API Token がトークンの形式ではないため、発行し直します。"
    }
    $tokenScript = @"
def user = hudson.model.User.getById("$groovyUser", false)
if (user == null) { return "ERROR: user not found" }
def property = user.getProperty(jenkins.security.ApiTokenProperty.class)
if (property == null) {
    user.addProperty(new jenkins.security.ApiTokenProperty())
    user.save()
    property = user.getProperty(jenkins.security.ApiTokenProperty.class)
}
if (property == null) { return "ERROR: ApiTokenProperty missing" }
def issued = property.tokenStore.generateNewToken("cisetup")
user.save()
return issued.plainValue
"@
    $apiToken = ((Invoke-JenkinsGroovy -BaseUrl $localBase -Headers $headers -Script $tokenScript).Trim() -replace '^Result:\s*', '').Trim()
    if (-not (Test-ApiTokenText $apiToken)) {
        if (Test-Path -LiteralPath $tokenFile) {
            Remove-Item -LiteralPath $tokenFile -Force
        }
        throw "API Token を発行できませんでした。結果: $apiToken"
    }
    [System.IO.File]::WriteAllText($tokenFile, $apiToken, (New-Object System.Text.UTF8Encoding $false))
}

if ($ProjectPath) {
    if (-not (Test-Path -LiteralPath $ProjectPath)) {
        throw "プロジェクトフォルダがありません: $ProjectPath"
    }
    Write-Step "CISetup の接続情報を保存"
    $ciDir = Join-Path $ProjectPath "CISetup"
    New-Item -ItemType Directory -Force -Path $ciDir | Out-Null
    $secretsPath = Join-Path $ciDir "cisetup.secrets.local.json"
    Merge-JsonFile $secretsPath @{
        jenkinsUrl      = $JenkinsUrl
        jenkinsUser     = $AdminUser
        jenkinsApiToken = $apiToken
    }
    if (-not (Test-Path -LiteralPath $secretsPath)) {
        throw "接続情報を書けませんでした: $secretsPath"
    }
    $secretsNow = Get-Content -LiteralPath $secretsPath -Raw | ConvertFrom-Json
    if ($secretsNow.PSObject.Properties.Name -notcontains "gitUsername") {
        Merge-JsonFile $secretsPath @{
            gitUsername     = ""
            gitPassword     = ""
            teamsWebhookUrl = ""
        }
    }
    if ($FileShare) {
        $localPath = Join-Path $ciDir "cisetup.local.json"
        if (-not (Test-Path -LiteralPath $localPath)) {
            Merge-JsonFile $localPath @{
                basePaths          = @()
                ciFileServers      = @($FileShare)
                agentWorkspacePath = ""
                releaseUrls        = @()
                analysisUrls       = @()
                logsUrls           = @()
                testsUrls          = @()
                sourceUrls         = @()
            }
        } else {
            Merge-JsonFile $localPath @{ ciFileServers = @($FileShare) }
        }
    }
}

Restrict-Acl $JenkinsHome
Restrict-Acl $AgentWorkDir
if ($script:OwnJdk) { Restrict-Acl "C:\jdk21" }
Restrict-Acl $war
if ($script:OwnDotnet) { Restrict-Acl "C:\dotnet" }

Write-Step "完了"
Write-Host "Jenkins URL : $JenkinsUrl"
Write-Host "ユーザー    : $AdminUser"
Write-Host "パスワード  : $AdminPassword"
Write-Host "API Token   : $apiToken"
Write-Host "プラグイン  : $pluginCheck"
if (-not $SkipAgent) {
    Write-Host "エージェント: $AgentName"
    Write-Host "作業フォルダ: $AgentWorkDir"
}
Write-Host "起動スクリプト: $startBatPath"
Write-Host "パスワードの保存先: $passwordFile"
if ($script:FirewallFailures.Count -gt 0) {
    Write-Host "ファイアウォール規則を処理できませんでした: $($script:FirewallFailures -join ', ')"
}
Write-Host "CISetup の「⑤ Jenkins への接続」に Jenkins URL、ユーザー名、API Token を入れ、接続テストが成功すれば使えます。"
Write-Host "エージェントラベルは空欄にしてください。組み込みノードの実行数は 0 です。"
Write-Host "サーバーを再起動すると、Jenkins とエージェントはタスク スケジューラから SYSTEM で起動します。画面は開きません。"
Write-Host "ログは $(Join-Path $JenkinsHome 'jenkins.log') と $(Join-Path $AgentWorkDir 'agent.log') です。"
Write-Host "ジョブも SYSTEM で動きます。共有フォルダはコンピューターアカウントの権限が必要です。ジョブを編集できる人は SYSTEM 権限で実行できます。"
Write-Host "画面を残して起動するときは start-jenkins.bat window と start-agent.bat window を使います。終了時の表示は pause で残ります。"

if ($CISetupExe) {
    if (-not (Test-Path -LiteralPath $CISetupExe)) {
        throw "CISetup.exe が見つかりません: $CISetupExe"
    }
    if ($ProjectPath) {
        Start-Process -FilePath $CISetupExe -ArgumentList "--open", $ProjectPath
    } else {
        Start-Process -FilePath $CISetupExe
    }
}
