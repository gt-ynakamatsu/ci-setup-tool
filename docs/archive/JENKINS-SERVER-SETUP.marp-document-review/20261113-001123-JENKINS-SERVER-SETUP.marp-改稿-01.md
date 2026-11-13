---
marp: true
theme: genetec
paginate: true
size: 16:9
title: Jenkins サーバー セットアップ手順
description: 未導入の Windows サーバーを、CISetup から接続できる状態にする手順
footer: "©2026 GENETEC CORPORATION All Rights Reserved."
style: |
  section:not(.cover) {
    background:
      linear-gradient(#003894, #003894) top / 100% 14px no-repeat,
      url("./genetec-logo-h.png") right 32px bottom 16px / 168px auto no-repeat,
      #fff;
  }
  footer {
    left: 86px;
    right: 230px;
    bottom: 20px;
    font-size: 14px;
  }
  section.cover::after {
    content: "" !important;
  }
  section.cover footer {
    left: 48px;
  }
---

<!-- _class: cover -->
<!-- _paginate: false -->

# Jenkins サーバー

<p class="lead">初回セットアップ手順</p>

未導入の Windows サーバーで `tools/Setup-JenkinsServer.ps1` を実行し、CISetup の接続テスト成功まで進める

<p class="meta">2026年11月12日<br>version 1.7<br>HW部 仲松</p>

---

<!-- _class: tight -->

# 改版履歴

| version | 日付 | 変更内容 | 改版者 |
|---|---|---|---|
| 1.0 | 2026-11-11 | 初版制定 | |
| 1.1 | 2026-11-11 | パスワード生成、アクセス権、受信規則、起動タスクの見直し | 仲松 |
| 1.2 | 2026-11-12 | 受信規則を java.exe に限定し、通信許可の確認画面を出さない | 仲松 |
| 1.3 | 2026-11-12 | TCP 50000 の受信規則を IPv4 と IPv6 で分けた | 仲松 |
| 1.4 | 2026-11-12 | TCP 50000 の受信規則を `127.0.0.1` の1件に戻した。`timestamper` プラグインを追加した | 仲松 |
| 1.5 | 2026-11-12 | 再起動待ちとアクセス権設定の経過を1行で更新する。エージェント secret は画面に出さない。環境スキャンはタスクと jenkins.war も見る | 仲松 |
| 1.6 | 2026-11-12 | 入っている Git、.NET SDK 8、Java 21 または 25 は再利用する。MSI 版の Jenkins があるときは WAR を置かない | 仲松 |
| 1.7 | 2026-11-12 | 対象条件と再実行条件を整理。パスワード保存、続行表示、エラー対処、手動起動、API Token の扱いを修正・集約 | 仲松 |

---

<!-- _class: tight -->

## 対象

Jenkins が入っておらず、初回実行前に次のいずれもない Windows サーバーが対象です。

- MSI 版 Jenkins
- `C:\jdk21`、`C:\dotnet`、`C:\jenkins`、`C:\jenkins.war`
- `jenkins.war` をコマンドラインに含む `java.exe` で動いている Jenkins

Git が入っているサーバーも対象です。2026-11-11 に、Git 2.47.1.windows.2 が入った環境で `==> 完了` まで進むことを確認しています。PATH または所定の探索先に Java 21 または 25、PATH、`C:\Program Files\dotnet`、`C:\dotnet` のいずれかに .NET SDK 8 があるサーバーも対象ですが、これらの再利用は未確認です。

初回実行前の対象判定は実行者が行います。スクリプトは上記の項目を検出しても初回実行として停止しません。Java 21 または 25 がない場合は既存の `C:\jdk21` を削除し、JDK 21 を展開します。既存の `C:\jenkins` はアクセス権を変更して使います。MSI 版 Jenkins がある場合は、Git、.NET、Java の導入、PATH 変更、アクセス権変更を行ったあと、終了コード `0` で終了します。起動中の `jenkins.war` がある場合は、新たに起動せず、その Jenkins を使います。

---

<!-- _class: tight -->

## 初回実行前の確認

管理者 PowerShell で確認します。

```powershell
Test-Path 'C:\jdk21'
Test-Path 'C:\dotnet'
Test-Path 'C:\jenkins'
Test-Path 'C:\jenkins.war'
Get-CimInstance Win32_Process -Filter "Name = 'java.exe'" |
  Select-Object ProcessId, CommandLine
```

4つの結果がすべて `False` で、`CommandLine` に `jenkins.war` を含む `java.exe` がないことを確認します。

---

<!-- _class: tight -->

## MSI 版 Jenkins の確認

スクリプトと同じ条件で、64 bit 側と WOW6432Node 側の Uninstall キーを確認します。

```powershell
@(
  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
) | ForEach-Object {
  Get-ItemProperty -Path $_ -ErrorAction SilentlyContinue
} | Where-Object {
  [string]$_.DisplayName -match '^Jenkins( \d|$)' -and
  $_.WindowsInstaller -eq 1
} | Select-Object DisplayName, DisplayVersion, InstallLocation
```

結果が何も表示されないことを確認します。

---

## この手順で行うこと

| 行うこと | 行わないこと |
|---|---|
| Git、Java 21、.NET SDK 8 の導入 | 既存 Jenkins からの移行 |
| Jenkins LTS の配置と起動 | 別 PC のエージェント構築 |
| 管理者、プラグイン、API Token の準備 | プロキシ設定、HTTPS 化 |
| 同一サーバー上のエージェント作成 | プロジェクト用 CI ジョブの作成 |
| サーバー起動時の自動起動 | Git や Teams の設定 |
| CISetup からの接続テスト | テストビルド |

`-SkipAgent`、`-ProjectPath`、`-FileShare`、`-CISetupExe` の使用方法も扱いません。

---

## 完了条件

設定用 PC の CISetup で、次のメッセージが表示されること。

> Jenkins への接続に成功しました。

あわせて、次を確認します。

- スクリプトの出力に `OK: plugins active (...)` があり、7個のプラグイン ID が並んでいる
- Jenkins の Nodes 画面で `windows-agent` がオンラインになっている

---

## 構成

```text
設定用 PC（CISetup）
    │  http://<Jenkinsサーバー>:<Port>/
    ▼
Jenkins サーバー（未導入の Windows）
    ├─ Jenkins LTS（WAR、組み込みノードの実行数 0）
    ├─ Java 21 または 25
    ├─ Git for Windows
    ├─ .NET SDK 8
    └─ windows-agent（インバウンド接続、ラベルなし）
```

Jenkins とエージェントは Windows サービスではありません。セットアップ中は、スクリプトが実行者と同じユーザーとして、ウィンドウを開かずに起動します。サーバー起動時に SYSTEM で起動するタスクも登録します。

---

# 1. 実行前の準備

---

<!-- _class: tight -->

## 用意するもの

| 項目 | 内容 |
|---|---|
| リポジトリ一式 | Jenkins サーバー上へコピーする |
| 設定用 PC | `CISetup.exe` がある PC |
| Jenkins URL | 設定用 PC から開ける URL。例: `http://ci-server:8080/` |
| 管理者ユーザー名 | 既定値は `admin` |
| 管理者パスワード | パスワードファイルがなく、省略した場合は英数字24文字を生成する。指定もできる |

パスワードは空白を含まない ASCII の表示文字だけを受け付けます。`$` は確認済みです。`'`、`"`、`\` は未確認のため使わないでください。

MSI 版 Jenkins が検出されず、`C:\jenkins\cisetup-admin-password.txt` がなければ、指定した値または生成した値を同ファイルへ保存します。ファイルがある場合は上書きしません。`-AdminPassword` を省略して再実行すると、保存済みの値を使います。

---

<!-- _class: tight -->

## 実行条件

- コンソールまたは RDP でログオンし、そのデスクトップで管理者 PowerShell を開く
- WinRM などのリモート PowerShell は使わない
- TCP 8080（`-Port` の値）と TCP 50000 がほかの用途で使われていない
- 設定用 PC から指定する Jenkins URL へ到達できる
- 配布元と Jenkins 更新サイトへ HTTPS で接続できる

スクリプト内の Jenkins 操作とエージェント接続には `http://localhost:<Port>/` が使われます。プロキシが必要な環境は対象外です。

---

<!-- _class: tight -->

## 初回実行時の外部通信

- Git for Windows: `github.com`
- .NET インストールスクリプト: `dot.net`
- .NET SDK 本体: `builds.dotnet.microsoft.com`
- JDK 21: `github.com`（Adoptium Temurin 21.0.13+9）
- Jenkins LTS 2.580.2: `get.jenkins.io`
- Jenkins 更新サイト: `updates.jenkins.io`

プラグイン本体を含む配布物は、別ホストへリダイレクトされる場合があります。許可リスト方式では、検証環境で実際の通信先を確認してから申請してください。

---

<!-- _class: tight -->

## 入っているものの再利用

- Git: `C:\Program Files\Git\cmd\git.exe` または PATH 上の `git.exe` を使う。版は確認しない
- .NET: PATH、`C:\Program Files\dotnet`、`C:\dotnet` の順で SDK 8 を探して使う
- Java: `C:\jdk21`、PATH、`C:\Program Files` 配下の `Eclipse Adoptium\jdk-2*`、`Java\jdk-2*`、`Microsoft\jdk-2*`、`Zulu\zulu-2*` にある `bin\java.exe` の順で Java 21 または 25 を探して使う

2026-11-11 に、Git 2.47.1.windows.2 が入った環境で完了まで進むことを確認しています。PATH 上の `git.exe` を当時のスクリプト版が再利用したかは未確認です。既存 .NET SDK 8 と既存 Java 21 または 25 の再利用も未確認です。

---

<!-- _class: tight -->

## 再利用とアクセス権

使用する Java が `C:\jdk21` 配下にある場合は、同フォルダのアクセス権を SYSTEM と Administrators に限定し、`java.exe` のあるフォルダをマシン PATH の先頭へ追加します。

使用する .NET SDK 8 が `C:\dotnet` 配下にある場合は、同フォルダのアクセス権を限定し、`C:\dotnet` をマシン PATH の先頭へ追加します。SDK 8 が見つからず、既存の `C:\dotnet` へ導入する場合も、導入前後にアクセス権を限定します。

Java 21 または 25 が見つからなければ、既存の `C:\jdk21` を削除して JDK 21 を展開します。Program Files や PATH にあるほかの Java、.NET SDK 8 の導入先は変更しません。

---

<!-- _class: tight -->

## MSI 版 Jenkins が見つかった場合

スクリプトは Git、.NET SDK 8、Java 21 または 25 を確認し、必要な導入を行ったあとで MSI 版 Jenkins を判定します。使用する Java が `C:\jdk21` 配下の場合、使用する .NET が `C:\dotnet` 配下の場合、または SDK 8 が見つからず既存の `C:\dotnet` へ導入する場合は、判定前に該当フォルダのアクセス権制限と PATH 追加も行います。

MSI 版が見つかると、WAR の配置、起動、プラグイン導入を行わず、終了コード `0` で終了します。`==> 完了` は表示されません。ここまでの導入、PATH 変更、アクセス権変更は残ります。

このスクリプトの Jenkins を使うには、MSI 版をアンインストールして再実行します。アンインストール時の既存データの扱いは、この手順の対象外です。

---

<!-- _class: tight -->

## 使用する版と方式

| 対象 | 内容 |
|---|---|
| Git | 既存の `git.exe`。ない場合は Git for Windows 2.47.1.2 |
| .NET | 既存の .NET SDK 8。ない場合は .NET SDK 8.0 チャネル |
| Java | 既存の Java 21 または 25。ない場合は Temurin 21.0.13+9 |
| Jenkins | Jenkins LTS 2.580.2 の WAR |
| Jenkins の起動 | `java -jar`。セットアップウィザードは無効 |
| エージェント | 同一サーバーからのインバウンド接続 |

CISetup の画面が案内する MSI 版 Jenkins と「Jenkins サーバー初回設定」は使いません。

---

<!-- _class: tight -->

## 検証状況

確認日: 2026-11-11

- `-JenkinsUrl http://localhost:8080/` で実行し、約7分で `==> 完了` まで進んだ（Git の導入時間は含まない）
- Jenkins 2.580.2、Temurin 21.0.13+9、.NET SDK 8.0.428 を導入。Git 2.47.1.windows.2 は導入済み
- `$` を含むパスワードで初期化とログインに成功した
- サーバー内から API Token で接続し、`windows-agent` のオンラインを確認した
- 組み込みノードの実行数 0、受信規則2件の有効、`agent any` のビルド成功を確認した
- プラグイン無効化時の自動再起動、再確認、エラー終了と、修正後の再実行を確認した
- `timestamper` 追加後、CISetup のテストビルド #2 が成功した（1分58秒）

---

<!-- _class: tight -->

## 未確認事項

- 設定用 PC の CISetup からの接続テスト、サーバー名での接続、受信規則を通る通信、名前解決
- Windows Server、プロキシ環境、.NET 以外の配布元のリダイレクト先
- Git の新規導入、PATH 上の `git.exe` の再利用、既存 .NET SDK 8 と既存 Java 21 または 25 の再利用、MSI 版 Jenkins の検出
- パスワードの `'`、`"`、`\`、自動生成、権限制限後の再実行
- アクセス権の制限、`127.0.0.1` に限った TCP 50000 の受信規則
- RDP 切断またはサインアウト後の継続動作
- 再起動後に起動タスクから Jenkins とエージェントが起動した記録
- Jenkins とエージェントを手動で安全に停止する手順
- 2026-11-11 の各検証項目で使用したスクリプトの版
- Marp 表示時の文字切れ、折り返し、余白、重なり

---

# 2. サーバーで実行する

---

## 管理者 PowerShell を開く

1. Jenkins サーバーへコンソールまたは RDP でログオンする
2. PowerShell を「管理者として実行」する
3. リポジトリルートへ移動する

```powershell
Set-Location "D:\path\to\ci-setup-tool"
Test-Path ".\tools\Setup-JenkinsServer.ps1"
```

`True` が表示されたことを確認します。

---

<!-- _class: tight -->

## 実行コマンド（パスワードを指定）

管理者パスワードを決めて管理する場合に使います。パスワードは PowerShell の履歴と実行中の `powershell.exe` のコマンドラインに残ります。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin' `
  -AdminPassword '<管理者パスワード>'
```

`ci-server` は、設定用 PC から名前解決できるサーバー名に置き換えます。

---

<!-- _class: tight -->

## 実行コマンド（パスワードを生成）

コマンド履歴と実行中の `powershell.exe` のコマンドラインへパスワードを残したくない場合に使います。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin'
```

パスワードファイルがなければ英数字24文字を生成します。`-JenkinsUrl` のポート番号は `-Port` と一致させます。`==> 完了` または MSI 版の案内まで、この PowerShell を閉じたりサインアウトしたりしないでください。

---

<!-- _class: tight -->

## スクリプトの処理

1. Git を確認し、なければ導入する
2. .NET SDK 8 を確認し、必要な場合だけ `C:\dotnet` のアクセス権を制限して PATH へ追加する
3. Java 21 または 25 を確認し、必要な場合だけ `C:\jdk21` のアクセス権を制限して PATH へ追加する
4. MSI 版 Jenkins を確認し、見つかれば案内を表示して終了する
5. WAR を `C:\jenkins.war` へ保存し、アクセス権を制限する
6. `C:\jenkins` と `C:\Jenkins\workspace` のアクセス権を制限し、パスワードファイルを保存する
7. 初期設定用 Groovy、Jenkins の起動バッチと起動タスクを作る
8. ファイアウォール規則を追加し、Jenkins を起動する
9. 管理者、基本設定、プラグインを用意する
10. エージェントを登録し、`start-agent.bat` と起動タスクを作って、オンラインを確認する
11. API Token を発行し、最後にアクセス権を再度制限する

---

<!-- _class: tight -->

## 待ち時間

| 処理 | 上限 |
|---|---:|
| Jenkins の応答待ち | 1回につき8分 |
| Groovy 呼び出し1回 | 10分 |
| プラグイン導入 | 最大3回。失敗時は30秒待つ |
| エージェントのオンライン待ち | 3分。1回起動し直し、さらに3分 |

プラグイン反映の再起動では、`CISetup Jenkins` と `CISetup Jenkins Agent` の両タスクを一時的に無効化し、`jenkins.war` を含む `java.exe` と親の `cmd.exe` を停止してから Jenkins を起動します。

エージェントの起動し直しでは、`CISetup Jenkins Agent` だけを一時的に無効化し、`agent.jar` を含む `java.exe` と `start-agent.bat` の `cmd.exe` を停止します。

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`
- `timestamper`

導入後、次の内容を含む行が表示されます。

```text
OK: plugins active (workflow-aggregator, git, credentials-binding, plain-credentials, parameterized-trigger, naginator, timestamper)
```

この内容が出ない場合は、プラグインの準備が完了していません。

---

<!-- _class: tight -->

## ファイアウォール規則

| 表示名 | ポート | リモートアドレス |
|---|---:|---|
| `CISetup Jenkins HTTP` | `-Port` の値 | スクリプトでは限定しない |
| `CISetup Jenkins Agent` | 50000 | `127.0.0.1` |

どちらも使用する JDK の `java.exe` が対象です。エージェントは同じサーバーの localhost から TCP 50000 へ接続します。

規則の追加または削除に失敗しても処理は続き、発生時点で規則名が表示されます。完了時にも失敗した規則名が表示されます。古い規則 `CISetup Jenkins Agent v6` の削除に成功した場合は、`不要なファイアウォール規則を削除しました:` に続けて規則名が表示されます。

---

<!-- _class: tight -->

## 完了表示

`==> 完了` の後に、Jenkins URL、ユーザー、パスワード、API Token、プラグインの確認結果、エージェント名、作業フォルダ、起動スクリプト、パスワードの保存先が表示されます。

セットアップ中の Jenkins とエージェントは、`Start-Process` により、スクリプト実行者と同じユーザーとして起動します。

完了表示の「ジョブも SYSTEM で動きます」は、サーバー再起動後に、起動タスクから Jenkins とエージェントが起動した場合の説明です。

CISetup へ入力するのは Jenkins URL、ユーザー、API Token の3項目です。

---

<!-- _class: tight -->

## 作成される主なファイル

| パス | 内容 | 含む秘密情報 |
|---|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動 | なし |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者と基本設定 | 管理者パスワード |
| `C:\jenkins\cisetup-admin-password.txt` | 保存した管理者パスワード。既存時は上書きしない | 管理者パスワード |
| `C:\jenkins\cisetup-api-token.txt` | API Token | API Token |
| `C:\Jenkins\workspace\agent.jar` | エージェント本体 | なし |
| `C:\Jenkins\workspace\start-agent.bat` | エージェント起動 | エージェント secret |

`C:\Jenkins\workspace` は `C:\jenkins` の配下です。`C:\jenkins`、同作業フォルダ、`C:\jenkins.war` は SYSTEM と Administrators だけがアクセスできるようにします。

---

<!-- _class: tight -->

## 初期設定用 Groovy の注意

- パスワードを変えて再実行しても、既存アカウントのパスワードは変わらない
- 起動のたびに Jenkins URL、待受ポート50000、組み込みノードの実行数0を設定する
- AD や LDAP へ切り替える前に、`01-cisetup-bootstrap.groovy` を `init.groovy.d` から外す

Groovy を残したまま AD や LDAP へ切り替えると、起動時にセキュリティレルムが `HudsonPrivateSecurityRealm` でない場合、Jenkins 独自のユーザーデータベースと認可設定へ戻されます。

---

<!-- _class: tight -->

## 秘密情報の扱い

秘密情報は、完了表示、初期設定用 Groovy、パスワードファイル、Token ファイル、`start-agent.bat`、エージェントのプロセスのコマンドラインに残ります。

`-AdminPassword` を指定した場合は、PowerShell の履歴と実行中の `powershell.exe` のコマンドラインにも残ります。

共有サーバーでは、プロセス情報や監査ログを閲覧できる利用者にも注意してください。実行中の画面共有を避け、保存するログから秘密情報を除きます。

---

# 3. CISetup で接続を確認する

---

<!-- _class: tight -->

## CISetup へ入力する

設定用 PC で `CISetup.exe` のアイコンをダブルクリックし、「⑤ Jenkins への接続」へ入力します。

| CISetup の項目 | 入力値 |
|---|---|
| Jenkins URL | 完了表示の `Jenkins URL` |
| ユーザー名 | 完了表示の `ユーザー` |
| API Token | 完了表示の `API Token` |
| 詳細設定のエージェントラベル | 空欄 |

エージェントラベルに `windows` を入力すると、ラベルなしで作られた `windows-agent` へビルドが割り当てられません。空欄の場合、CISetup は Jenkinsfile に `agent any` を生成します。

API Token は `C:\jenkins\cisetup-api-token.txt` でも確認できます。安全な方法で設定用 PC へ渡します。

---

## 接続テスト

1. Jenkins URL、ユーザー名、API Token を入力する
2. 「接続テスト」を押す
3. 次のメッセージを確認する

> Jenkins への接続に成功しました。

設定用 PC から指定 URL へ到達し、入力したユーザー名と API Token で Jenkins API に認証できたことを示します。

---

## エージェントを確認する

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `windows-agent` がオンラインであることを確認する

`windows-agent` はラベルなしで作成され、組み込みノードの実行数は 0 です。

---

# 4. 初回実行が止まったとき

---

## 再実行の原則

表示されたエラーと `C:\jenkins\jenkins.log`、`C:\Jenkins\workspace\agent.log` を確認します。

1. エラーの原因を解消する
2. 最初と同じコマンドを再実行する
3. `==> 完了` まで進める

スクリプトは起動中の Jenkins を検出して再利用します。通常の再実行前に、手作業で停止する必要はありません。途中で作成されたフォルダやファイルは、エラーの対処で指示がある場合を除き、手作業で削除しないでください。スクリプト自身は、Java 21 または 25 がない `C:\jdk21`、壊れた取得物などを条件に応じて削除します。

---

<!-- _class: tight -->

## 続けてよい表示

次の表示だけでは停止しません。

```text
不要なファイアウォール規則を削除しました: CISetup Jenkins Agent v6
crumb は取得しませんでした。そのまま Script Console を呼びます。
ERROR: <プラグイン導入時のエラー>
プラグインの導入を 30 秒後にやり直します（<回数> 回目に失敗）。
プラグインが有効になっていません。Jenkins を再起動して、もう一度確認します。
エージェント状態の取得を再試行します。
エージェントがオンラインになりません。起動し直します。
保存済みの API Token がトークンの形式ではないため、発行し直します。
```

`ERROR:` のあとに再試行の表示が続く場合は待ちます。ファイアウォール規則の追加または削除に失敗した表示が出ても処理は続きます。後続処理の成否は、`==> 完了` とプラグインの確認結果で判断します。

---

<!-- _class: tight -->

## 停止するエラーと対処（導入）

| 表示 | 対処 |
|---|---|
| `管理者として実行してください。` | 管理者 PowerShell で再実行 |
| `ダウンロードしたファイルの SHA256 が一致しません:` | 配布元と通信経路を確認して再実行 |
| `ダウンロードしたファイルを確認できませんでした:` | 配布元と通信経路を確認して再実行 |
| `Git のインストーラーが終了コード ... で終了しました。` | 原因を解消して再実行。不明なら `C:\git-setup.exe` を削除して再実行 |
| `Git のインストール後も ... が見つかりません。` | `C:\git-setup.exe` を削除して再実行 |
| `.NET SDK のインストーラーが終了コード ... で終了しました。` | `C:\dotnet-install.ps1` を削除して再実行 |
| `.NET SDK の展開後も ... が見つかりません。` | `C:\dotnet-install.ps1` と `C:\dotnet` を削除して再実行 |
| `.NET SDK 8 が見つかりません。` | `C:\dotnet` を削除して再実行 |
| 表にない表示でダウンロード中に停止 | 外部通信の通信先と経路を確認して再実行 |

---

<!-- _class: tight -->

## 停止するエラーと対処（JDK・Jenkins）

| 表示 | 対処 |
|---|---|
| `JDK 21 の展開に失敗しました。` | zip は削除済み。そのまま再実行 |
| `JDK 21 の展開後も java.exe が見つかりません。` | `C:\jdk21.zip` を削除して再実行 |
| `PATH に追加する場所がありません:` | 表示されたフォルダを確認して再実行 |
| `アクセス権を制限できませんでした:` | 表示されたパスを確認して再実行 |
| `管理者パスワードは、空白を含まない ASCII の表示文字で指定してください。` | 指定値を直して再実行。保存済みの値が使えない場合は、表示されたパスワードファイルを削除して再実行 |
| `Jenkins が 8 分以内に ... で応答しませんでした。` | `C:\jenkins\jenkins.log` を確認。「起動を確認する」も参照 |
| `Jenkins へのログインに失敗しました。` | 初回の値を `-AdminPassword` に指定して再実行。分からなければ「Jenkins の設定を作り直す場合」を参照 |
| 表にない表示で Jenkins 呼び出し（Groovy）中に停止 | `C:\jenkins\jenkins.log` を確認して再実行 |

---

<!-- _class: tight -->

## 停止するエラーと対処（プラグイン・エージェント）

| 表示 | 対処 |
|---|---|
| `プラグインの導入に 3 回失敗しました。` | `結果:` から通信、認証、HTTP エラーを確認して再実行 |
| `必要なプラグインが再起動しても有効になりませんでした。` | Plugins 画面と `C:\jenkins\jenkins.log` を確認し、直して再実行 |
| `エージェントの secret を取得できませんでした。` | 結果と Nodes 画面を確認して再実行 |
| `agent.jar を確認できませんでした。` | Jenkins への通信を確認して再実行 |
| `エージェント ... が起動し直しても 6 分以内にオンラインになりませんでした。` | `C:\Jenkins\workspace\agent.log` と Nodes 画面を確認して再実行 |
| `API Token を発行できませんでした。` | 結果を確認して再実行 |
| 表にない表示で停止 | 表示された処理、`jenkins.log`、`agent.log` を確認して再実行 |

エージェント待ちで停止した時点では、API Token 発行と完了表示は未実行です。

---

<!-- _class: tight -->

## 起動を確認する

画面を表示して起動する前に、対象の `java.exe` と、エージェントの起動待ちを確認します。

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    ($_.Name -eq 'java.exe' -and $_.CommandLine -match 'jenkins\.war|agent\.jar') -or
    ($_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'start-agent\.bat')
  } |
  Select-Object ProcessId, Name, CommandLine
```

`start-agent.bat` は、Java を起動する前に Jenkins の応答を最大8分待ちます。その間は `agent.jar` を含む `java.exe` がまだ表示されません。

---

<!-- _class: tight -->

## 画面を表示して起動する場合

`jenkins.war` が表示されない場合だけ、別の管理者 PowerShell で実行します。

```powershell
& 'C:\jenkins\start-jenkins.bat' window
```

`agent.jar` と `start-agent.bat` のどちらも表示されない場合だけ、さらに別の管理者 PowerShell で実行します。

```powershell
& 'C:\Jenkins\workspace\start-agent.bat' window
```

`window` を付けると、各 PowerShell は対象プロセスが終了するまで戻りません。Jenkins の応答確認と再実行は、別の管理者 PowerShell で行います。

---

<!-- _class: tight -->

## 接続テストが失敗したとき

「Jenkins サーバーに接続できませんでした。」の場合:

1. `<Port>` を実行時の `-Port` の値へ置き換える
2. サーバーで `http://localhost:<Port>/login` を開く
3. 開けなければ Jenkins の起動状態と `-Port` を確認する
4. 設定用 PC で完了表示の Jenkins URL を開く
5. 設定用 PC だけ開けなければ、HTTP の受信規則、ポート、名前解決を確認する

---

<!-- _class: tight -->

## 認証エラーと API Token の再発行

「Jenkins 認証エラー (401 Unauthorized)」の場合:

1. CISetup のユーザー名と API Token を転記し直す
2. `C:\jenkins\cisetup-api-token.txt` の内容と照合する
3. 解決しなければ、Token ファイルを削除する
4. 最初と同じコマンドを再実行する
5. 新しい API Token を安全な方法で設定用 PC へ渡し、CISetup へ入力する

```powershell
Remove-Item 'C:\jenkins\cisetup-api-token.txt'
```

再実行で `cisetup` という名前の Token が追加されます。古い Token は自動では失効しません。Jenkins の API Token 画面で失効させます。

---

<!-- _class: tight -->

## Jenkins の設定を作り直す場合

ログイン失敗時、スクリプトは、初回に指定したパスワードで入れない場合に `C:\jenkins` を削除して同じコマンドを再実行するよう案内します。

先に、初回の値を `-AdminPassword` に指定して再実行してください。値が分からない場合、または値を確認してもログインできない場合は、作業を中断して担当者へ相談してください。Jenkins とエージェントを手動で安全に停止する手順は未確認のため、この手順では `C:\jenkins` を削除しません。

`C:\jenkins` を削除すると、設定、管理者アカウント、パスワード、API Token、エージェント作業フォルダが消えます。Git、`C:\jdk21`、`C:\dotnet`、`C:\jenkins.war`、PATH、ファイアウォール規則、起動タスクは残ります。

---

<!-- _class: tight -->

## 取得物を削除して再実行する場合

取得物が壊れている場合は、エラー表示と対象ファイルを照合してから削除します。

- Jenkins WAR: `C:\jenkins.war`
- JDK: `C:\jdk21.zip`
- Git: `C:\git-setup.exe`
- .NET: `C:\dotnet-install.ps1` と `C:\dotnet`
- エージェント: `C:\Jenkins\workspace\agent.jar`

再利用時は `既存のファイルを使います: <パス>`、壊れた取得物の検出時は `取得済みファイルが壊れているため削除します: <パス>` と表示されます。

Git、JDK、Jenkins は SHA256 を確認します。一致しないファイルは削除して取り直します。取り直しても一致しなければ停止します。.NET のインストールスクリプトは空でないことだけを確認します。

---

<!-- _class: tight -->

## 再起動後

タスク スケジューラへ、サーバー起動時に `CISetup Jenkins` と `CISetup Jenkins Agent` を SYSTEM で起動するタスクを登録します。異常終了したときは、1分間隔で10回まで起動し直す設定です。

手動起動する場合は「起動を確認する」と同じプロセス確認を行い、「画面を表示して起動する場合」に従います。エージェントは Jenkins の応答を最大8分待ってから接続します。

Jenkins のログイン画面と、Nodes 画面の `windows-agent` のオンラインを確認します。

---

<!-- _class: tight -->

## 再起動後のジョブ実行アカウント

登録される起動タスクは、Jenkins とエージェントを SYSTEM で起動します。その場合、ジョブも SYSTEM で実行されます。

- 共有フォルダへはコンピューターアカウントでアクセスする
- ユーザープロファイルの Git 資格情報は使われない
- ジョブを編集できる人は SYSTEM 権限でコマンドを実行できる

専用のサービスアカウントへ変える手順は対象外です。再起動後の起動記録と、再起動前のジョブの実行アカウント、資格情報、権限レベルは未確認です。

---

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

`OK: plugins active` に7個の ID があり、  
`windows-agent` がオンラインであれば、  
初回セットアップは完了です。

次は、対象プロジェクトの Git URL などを入力し、CI ジョブを作成します。
