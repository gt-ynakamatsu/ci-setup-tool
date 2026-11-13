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
      url("./images/genetec-logo-h.png") right 32px bottom 16px / 168px auto no-repeat,
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

前半は `Setup-JenkinsServer.ps1` を実行する手順

スクリプトを使わない場合は、後半の手順に従う

<p class="meta">2026年11月13日<br>version 2.0<br>HW部 仲松</p>

---

<!-- _class: tight -->

# 改版履歴（1.0～1.5）

| version | 日付 | 変更内容 | 改版者 |
|---|---|---|---|
| 1.0 | <span style="white-space:nowrap">2026-11-11</span> | 初版制定 | |
| 1.1 | <span style="white-space:nowrap">2026-11-11</span> | パスワード生成、アクセス権、受信規則、起動タスクの見直し | 仲松 |
| 1.2 | <span style="white-space:nowrap">2026-11-12</span> | 受信規則を java.exe に限定。通信許可の確認画面を抑止 | 仲松 |
| 1.3 | <span style="white-space:nowrap">2026-11-12</span> | TCP 50000 の受信規則を IPv4 と IPv6 に分割 | 仲松 |
| 1.4 | <span style="white-space:nowrap">2026-11-12</span> | TCP 50000 を `127.0.0.1` の1件に戻し、`timestamper` を追加 | 仲松 |
| 1.5 | <span style="white-space:nowrap">2026-11-12</span> | 進捗表示、secret 非表示、環境スキャンを見直し | 仲松 |

---

<!-- _class: tight -->

# 改版履歴（1.6～2.0）

| version | 日付 | 変更内容 | 改版者 |
|---|---|---|---|
| 1.6 | <span style="white-space:nowrap">2026-11-12</span> | 既存 Git、.NET SDK 8、Java 21/25 を再利用。MSI 版検出時は WAR を配置しない | 仲松 |
| 1.7 | <span style="white-space:nowrap">2026-11-13</span> | 対象条件、再利用、導入手順、削除条件、確認日を修正 | 仲松 |
| 1.8 | <span style="white-space:nowrap">2026-11-13</span> | `-DotNetSdk` でチャネルまたは版を指定可能にした。既定は 8.0 | 仲松 |
| 1.9 | <span style="white-space:nowrap">2026-11-13</span> | 全体の流れ、構成、完了表示、CISetup 入力の図を追加。本文を整理し、確認事項を分割 | 仲松 |
| 2.0 | <span style="white-space:nowrap">2026-11-13</span> | スクリプトを使う手順を前にまとめ、使わない場合の手順を後半へ分けた | 仲松 |

---

# スクリプトを使う場合

---

<!-- _class: tight -->

## この資料の進み方

前半は `tools/Setup-JenkinsServer.ps1` を使う手順です。サーバーでスクリプトを実行し、設定用 PC の CISetup で接続テストと `windows-agent` のオンラインを確認します。

スクリプトを使わず、Jenkins の MSI を入れて CISetup の「Jenkins サーバー初回設定」を使う場合は、後半の「スクリプトを使わない場合」へ進んでください。

---

## この手順で行うこと

![全体の流れ](./images/jenkins-setup-flow.svg)

---

## 完了条件

次の3点を確認できれば、初回セットアップは完了です。

1. スクリプトの出力に `OK: plugins active (...)` があり、7個のプラグイン ID が並んでいる
2. CISetup の接続テストで `Jenkins への接続に成功しました。` と表示される
3. Jenkins の Nodes 画面で `windows-agent` がオンラインになっている

---

<!-- _class: tight -->

## 対象

Jenkins が入っていない Windows サーバーが対象です。実行前に、次がないことを確認します。

- MSI 版 Jenkins
- `C:\jenkins`、`C:\jenkins.war`
- `jenkins.war` をコマンドラインに含む `java.exe`

Git、Java 21 または 25、指定した .NET SDK（既定は 8.0）が入っていても対象です。探索順は「入っているものの再利用」に書きます。

スクリプトは、これらがあることを検出しても停止しません。フォルダの削除、アクセス権、MSI 版が見つかったときの終了は、「再利用とアクセス権」と「MSI 版 Jenkins が見つかった場合」を確認してください。

---

<!-- _class: tight -->

## 初回実行前の確認

管理者 PowerShell で確認します。

```powershell
Test-Path 'C:\jenkins'
Test-Path 'C:\jenkins.war'
Get-CimInstance Win32_Process -Filter "Name = 'java.exe'" |
  Select-Object ProcessId, CommandLine
```

2つの結果が `False` で、`CommandLine` に `jenkins.war` を含む `java.exe` がないことを確認します。MSI 版は次のページで確認します。

---

<!-- _class: tight -->

## MSI 版 Jenkins の確認

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

<!-- _class: tight -->

## 用意するもの

| 項目 | 内容 |
|---|---|
| リポジトリ一式 | Jenkins サーバー上へコピーする |
| 設定用 PC | `CISetup.exe` がある PC |
| Jenkins URL | 設定用 PC から開ける URL。例: `http://ci-server:8080/` |
| 管理者ユーザー名 | 既定値は `admin` |
| 管理者パスワード | ファイルがなく、省略した場合は英数字24文字を生成する |

パスワードは空白を含まない ASCII の表示文字だけを受け付けます。

---

<!-- _class: tight -->

## パスワードファイル

MSI 版 Jenkins が検出されず、`C:\jenkins\cisetup-admin-password.txt` がなければ、指定した値または生成した値を同ファイルへ保存します。

ファイルがある場合は上書きしません。`-AdminPassword` を省略して再実行すると、保存済みの値を使います。

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

# サーバーで実行する

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

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin' `
  -AdminPassword '<管理者パスワード>'
```

`ci-server` は設定用 PC から名前解決できるサーバー名に置き換え、URL のポートを `-Port` と一致させます。

パスワードは PowerShell の履歴と実行中プロセスのコマンドラインに残ります。

---

<!-- _class: tight -->

## 実行コマンド（パスワードを生成）

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin'
```

パスワードファイルがなければ英数字24文字を生成します。URL のポートを `-Port` と一致させます。

---

<!-- _class: tight -->

## 実行中の注意と .NET SDK の指定

`==> 完了` または MSI 版の案内まで、PowerShell を閉じないでください。

`==> 完了` 後も、CISetup の接続テストと `windows-agent` のオンライン確認が終わるまで、サインアウトしないでください。

.NET SDK を変えるときは、コマンドに次のいずれかを追加します。

```powershell
-DotNetSdk '9.0'
-DotNetSdk '8.0.428'
```

CISetup の「.NET SDK」欄にも同じ値を入力します。

---

## 完了表示

![完了表示の画面イメージ](./images/jenkins-setup-completion.svg)

画面イメージです。パスワードと API Token は伏せています。

---

<!-- _class: tight -->

## 完了表示で確認する値

`==> 完了` の後に、Jenkins URL、ユーザー、パスワード、API Token、プラグインの確認結果、エージェント名、作業フォルダ、起動スクリプト、パスワードの保存先が表示されます。

次を控えます。

1. `Jenkins URL`
2. `ユーザー`
3. `API Token`

`プラグイン` に7個の ID があり、`エージェント` が `windows-agent` であることも確認します。

完了表示の「ジョブも SYSTEM で動きます」は、再起動後に起動タスクから起動した場合の説明です。

---

# CISetup で接続を確認する

---

## CISetup へ入力して接続を確認する

![CISetup の入力画面と接続成功の画面イメージ](./images/jenkins-setup-cisetup.svg)

画面イメージです。完了表示の URL、ユーザー名、API Token を使います。

---

<!-- _class: tight -->

## CISetup での操作

設定用 PC で CISetup のアイコンをダブルクリックし、「⑤ Jenkins への接続」までスクロールします。

| CISetup の項目 | 入力値 |
|---|---|
| Jenkins URL | 完了表示の `Jenkins URL` |
| ユーザー名 | 完了表示の `ユーザー` |
| API Token | 完了表示の `API Token` |
| 詳細設定のエージェントラベル | 空欄 |

API Token は `C:\jenkins\cisetup-api-token.txt` でも確認できます。安全な方法で設定用 PC へ渡してください。

---

<!-- _class: tight -->

## 接続テスト

1. 「接続テスト」を押す
2. 「接続成功」ダイアログを確認する

> Jenkins への接続に成功しました。

エージェントラベルに `windows` を入力すると、ラベルなしの `windows-agent` へビルドが割り当てられません。空欄の場合、CISetup は Jenkinsfile に `agent any` を生成します。

---

## エージェントを確認する

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `windows-agent` がオンラインであることを確認する

`windows-agent` はラベルなしで作成され、組み込みノードの実行数は 0 です。

確認が終わるまでサインアウトしないでください。

---

# スクリプトを使う場合の完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

`OK: plugins active` に7個の ID があり、  
`windows-agent` がオンラインであれば、  
初回セットアップは完了です。

次は、対象プロジェクトの Git URL などを入力し、CI ジョブを作成します。

---

# スクリプトの詳細

---

<!-- _class: tight -->

## ここから先の読み方

ここまでは、スクリプトを実行して CISetup で確認する手順です。

ここから「再起動後のジョブ実行アカウント」までは、スクリプトが行う内容と、止まったときの対処です。実行だけで足りる場合は、ここを飛ばして「スクリプトを使わない場合」へ進んでも構いません。

---

## この手順の範囲

| 行うこと | 行わないこと |
|---|---|
| Git、Java、指定した .NET SDK の確認と導入 | 既存 Jenkins からの移行 |
| Jenkins LTS の配置と起動 | 別 PC のエージェント構築 |
| 管理者、プラグイン、API Token の準備 | プロキシ設定、HTTPS 化 |
| 同一サーバー上のエージェント作成 | プロジェクト用 CI ジョブの作成 |
| サーバー起動時の自動起動 | Git や Teams の設定 |
| CISetup からの接続テスト | テストビルド |

`-SkipAgent`、`-ProjectPath`、`-FileShare`、`-CISetupExe` の使用方法も扱いません。

---

## 構成

![Jenkins サーバーの構成](./images/jenkins-setup-architecture.svg)

.NET SDK は `-DotNetSdk` でチャネルまたは版を指定します。既定は 8.0 です。

---

<!-- _class: tight -->

## セットアップ中の起動方式

Jenkins とエージェントは Windows サービスではありません。

セットアップ中は、スクリプトが実行者と同じユーザーとして、ウィンドウを開かずに起動します。サーバー起動時に SYSTEM で起動するタスクも登録します。

<div class="callout warn">

`==> 完了` または MSI 版の案内まで PowerShell を閉じないでください。接続テストとオンライン確認が終わるまで、サインアウトしないでください。

</div>

---

<!-- _class: tight -->

## 初回実行時の外部通信

- Git for Windows: `github.com`
- .NET インストールスクリプト: `dot.net`
- .NET SDK 本体: `builds.dotnet.microsoft.com`
- JDK 21: `github.com`（Adoptium Temurin 21.0.13+9）
- Jenkins LTS 2.580.2: `get.jenkins.io`
- Jenkins 更新サイト: `updates.jenkins.io`

プラグイン本体を含む配布物は、別ホストへリダイレクトされる場合があります。許可リスト方式では、本番サーバーとは別の環境で実行して接続先を記録し、その結果で申請してください。

---

<!-- _class: tight -->

## 入っているものの再利用

- Git: `C:\Program Files\Git\cmd\git.exe` または PATH 上の `git.exe`。版は確認しない
- .NET: PATH、`C:\Program Files\dotnet`、`C:\dotnet` の順で、指定に合う SDK
- Java: `C:\jdk21`、PATH、`C:\Program Files` 配下の `Eclipse Adoptium\jdk-2*`、`Java\jdk-2*`、`Microsoft\jdk-2*`、`Zulu\zulu-2*` にある `bin\java.exe` の順で Java 21 または 25

起動タスクは SYSTEM で動くため、PATH 上の Java を使う場合は `Get-Command java` で場所を表示し、一般ユーザーが書き換えられない場所（`C:\Program Files` 配下など）にあることを確認してください。

---

<!-- _class: tight -->

## 再利用とアクセス権

使用する Java が `C:\jdk21` 配下にある場合は、同フォルダのアクセス権を SYSTEM と Administrators に限定し、`java.exe` のあるフォルダをマシン PATH の先頭へ追加します。

使用する .NET SDK が `C:\dotnet` 配下にある場合も、同フォルダのアクセス権を限定し、`C:\dotnet` をマシン PATH の先頭へ追加します。

Java 21 または 25 が見つからなければ、既存の `C:\jdk21` を削除して JDK 21 を展開します。ほかの Java、.NET SDK の導入先は変更しません。

---

<!-- _class: tight -->

## MSI 版 Jenkins が見つかった場合

Git、指定した .NET SDK、Java を確認し、必要な導入と対象フォルダのアクセス権制限、PATH 追加を行ったあとに MSI 版を判定します。

MSI 版が見つかると、WAR の配置、起動、プラグイン導入を行わず、終了コード `0` で終了します。`==> 完了` は表示されません。ここまでの変更は残ります。

このスクリプトの Jenkins を使うには、MSI 版をアンインストールして再実行します。既存データの扱いは、この手順の対象外です。

---

<!-- _class: tight -->

## 使用する版と方式

| 対象 | 内容 |
|---|---|
| Git | 既存の `git.exe`。ない場合は 2.47.1.2 |
| .NET | 指定 SDK。ない場合はチャネルまたは版を指定して導入。既定 `8.0` |
| Java | 既存の 21/25。ない場合は Temurin 21.0.13+9 |
| Jenkins | Jenkins LTS 2.580.2 の WAR |
| Jenkins の起動 | `java -jar`。セットアップウィザードは無効 |
| エージェント | 同一サーバーからのインバウンド接続 |

MSI を入れて CISetup の「Jenkins サーバー初回設定」を使う手順は、後半の「スクリプトを使わない場合」です。このスクリプトは WAR を配置して起動します。

---

<!-- _class: tight -->

## スクリプトの処理（1/2）

1. Git を確認し、なければ導入する
2. 指定した .NET SDK を確認し、なければ `C:\dotnet` へ導入する
3. Java 21 または 25 を確認し、なければ JDK 21 を展開する
4. MSI 版 Jenkins を確認し、見つかれば案内を表示して終了する
5. WAR を `C:\jenkins.war` へ保存し、アクセス権を制限する
6. `C:\jenkins` と作業フォルダのアクセス権を制限し、パスワードを保存する

---

<!-- _class: tight -->

## スクリプトの処理（2/2）

7. 初期設定用 Groovy、起動バッチ、起動タスクを作る
8. ファイアウォール規則を追加し、Jenkins を起動する
9. 管理者、基本設定、プラグインを用意する
10. エージェントを登録し、起動タスクを作ってオンラインを確認する
11. API Token を発行し、最後にアクセス権を再度制限する

---

<!-- _class: tight -->

## 待ち時間

| 処理 | 上限 |
|---|---:|
| Jenkins の応答待ち | 1回につき8分 |
| Groovy 呼び出し1回 | 10分 |
| プラグイン導入 | 最大3回。失敗時は30秒待つ |
| エージェントのオンライン待ち | 3分。起動し直してさらに3分 |

再起動時は起動タスクを一時的に無効化し、対象の `java.exe` と親の `cmd.exe` を停止してから起動します。

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`
- `timestamper`

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

どちらも使用する JDK の `java.exe` が対象です。エージェントは localhost から TCP 50000 へ接続します。

規則の追加または削除に失敗しても処理は続き、発生時点と完了時に規則名が表示されます。

---

<!-- _class: tight -->

## 作成される主なファイル

| パス | 内容 | 秘密情報 |
|---|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動 | なし |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者と基本設定 | パスワード |
| `C:\jenkins\cisetup-admin-password.txt` | 管理者パスワード | パスワード |
| `C:\jenkins\cisetup-api-token.txt` | API Token | API Token |
| `C:\Jenkins\workspace\agent.jar` | エージェント本体 | なし |
| `C:\Jenkins\workspace\start-agent.bat` | エージェント起動 | secret |

`C:\Jenkins\workspace` は `C:\jenkins` の配下です。対象フォルダと WAR は SYSTEM と Administrators だけがアクセスできます。

---

<!-- _class: tight -->

## 初期設定用 Groovy の注意

- パスワードを変えて再実行しても、既存アカウントのパスワードは変わらない
- 起動のたびに Jenkins URL、待受ポート50000、組み込みノードの実行数0を設定する
- AD や LDAP へ切り替える前に、`01-cisetup-bootstrap.groovy` を `init.groovy.d` から外す

Groovy を残したまま AD や LDAP へ切り替えると、Jenkins 独自のユーザーデータベースと認可設定へ戻されます。

---

<!-- _class: tight -->

## 秘密情報の扱い

秘密情報は、完了表示、初期設定用 Groovy、パスワードファイル、Token ファイル、`start-agent.bat`、エージェントのプロセスのコマンドラインに残ります。

`-AdminPassword` を指定した場合は、PowerShell の履歴と実行中の `powershell.exe` のコマンドラインにも残ります。

共有サーバーでは、プロセス情報や監査ログを閲覧できる利用者にも注意してください。実行中の画面共有を避け、保存するログから秘密情報を除きます。

---

# 初回実行が止まったとき

---

## 再実行の原則

表示されたエラーと `C:\jenkins\jenkins.log`、`C:\Jenkins\workspace\agent.log` を確認します。

1. エラーの原因を解消する
2. 最初と同じコマンドを再実行する
3. `==> 完了` まで進める

起動中の Jenkins は再利用されます。指示がある場合を除き、途中で作成されたフォルダやファイルを手作業で削除しないでください。

---

<!-- _class: tight -->

## 続けてよい表示

```text
不要なファイアウォール規則を削除しました: CISetup Jenkins Agent v6
crumb は取得しませんでした。そのまま Script Console を呼びます。
プラグインの導入を 30 秒後にやり直します（<回数> 回目に失敗）。
プラグインが有効になっていません。Jenkins を再起動して、もう一度確認します。
エージェント状態の取得を再試行します。
エージェントがオンラインになりません。起動し直します。
保存済みの API Token がトークンの形式ではないため、発行し直します。
```

再試行の直前に `ERROR:` を含む行が出ることがあります。そのあとに再試行の表示が続くあいだは待ちます。`プラグインの導入に 3 回失敗しました。` は停止です。ファイアウォール規則の追加または削除に失敗しても処理は続きます。後続処理の成否は、`==> 完了` とプラグインの確認結果で判断します。

---

<!-- _class: tight -->

## 停止するエラーと対処（導入）

| 表示 | 対処 |
|---|---|
| `管理者として実行してください。` | 管理者 PowerShell で再実行 |
| `ダウンロードしたファイルの SHA256 が一致しません:` | 配布元と通信経路を確認 |
| `ダウンロードしたファイルを確認できませんでした:` | 配布元と通信経路を確認 |
| `Git のインストーラーが終了コード ...` | 原因を解消。不明なら `C:\git-setup.exe` を削除 |
| `Git のインストール後も ... が見つかりません。` | `C:\git-setup.exe` を削除 |
| `.NET SDK のインストーラーが終了コード ...` | `C:\dotnet-install.ps1` を削除 |
| `.NET SDK の展開後も ... が見つかりません。` | `C:\dotnet-install.ps1` と `C:\dotnet` を削除 |
| `.NET SDK <指定> が見つかりません。` | `C:\dotnet` を削除 |
| 表にない表示でダウンロード中に停止 | 外部通信の通信先と経路を確認 |

原因を解消または指定物を削除したあと、再実行します。

---

<!-- _class: tight -->

## 停止するエラーと対処（JDK・Jenkins）

| 表示 | 対処 |
|---|---|
| `JDK 21 の展開に失敗しました。` | zip は削除済み。そのまま再実行 |
| `JDK 21 の展開後も java.exe が見つかりません。` | `C:\jdk21.zip` を削除 |
| `PATH に追加する場所がありません:` | 表示されたフォルダを確認 |
| `アクセス権を制限できませんでした:` | 表示されたパスを確認 |
| `管理者パスワードは ...` | 指定値を直す。保存値ならファイルを削除 |
| `Jenkins が 8 分以内に ...` | `jenkins.log` と起動状態を確認 |
| `Jenkins へのログインに失敗しました。` | パスワードを省略して再実行 |
| 表にない表示で Groovy 呼び出し中に停止 | `jenkins.log` を確認 |

確認後、再実行します。

---

<!-- _class: tight -->

## 停止するエラーと対処（プラグイン・エージェント）

| 表示 | 対処 |
|---|---|
| `プラグインの導入に 3 回失敗しました。` | `結果:` から通信、認証、HTTP エラーを確認 |
| `必要なプラグインが ... 有効になりませんでした。` | Plugins 画面と `jenkins.log` を確認 |
| `エージェントの secret を取得できませんでした。` | 結果と Nodes 画面を確認 |
| `agent.jar を確認できませんでした。` | Jenkins への通信を確認 |
| `エージェント ... オンラインになりませんでした。` | `agent.log` と Nodes 画面を確認 |
| `API Token を発行できませんでした。` | 結果を確認 |
| 表にない表示で停止 | 表示された処理と `jenkins.log`、`agent.log` を確認 |

エージェント待ちで停止した場合、API Token 発行と完了表示は未実行です。確認後、再実行します。

---

<!-- _class: tight -->

## 起動を確認する

別の管理者 PowerShell で実行します。

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    ($_.Name -eq 'java.exe' -and
      $_.CommandLine -match 'jenkins\.war|agent\.jar') -or
    ($_.Name -eq 'cmd.exe' -and
      $_.CommandLine -match 'start-agent\.bat')
  } |
  Select-Object ProcessId, Name, CommandLine
```

`start-agent.bat` は Jenkins の応答を最大8分待ってから接続します。その間は `agent.jar` を含む `java.exe` がまだ表示されません。

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

Jenkins の応答確認と再実行は、起動用とは別の管理者 PowerShell で行います。

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
2. `C:\jenkins\cisetup-api-token.txt` と照合する
3. 解決しなければ Token ファイルを削除する
4. 最初と同じコマンドを再実行する
5. 新しい Token を安全な方法で設定用 PC へ渡す

```powershell
Remove-Item 'C:\jenkins\cisetup-api-token.txt'
```

再実行で `cisetup` という名前の Token が追加されます。古い Token は Jenkins の API Token 画面で失効させます。

---

<!-- _class: tight -->

## ログインできないときの扱い

1. `C:\jenkins\cisetup-admin-password.txt` の値を確認する
2. `-AdminPassword` を省略して再実行する
3. 保存済みのパスワードでもログインできなければ中断する

この手順では `C:\jenkins` を削除しません。削除すると、設定、管理者アカウント、パスワード、API Token、エージェント作業フォルダが消えます。

---

<!-- _class: tight -->

## 取得物を削除して再実行する場合

- Jenkins WAR: `C:\jenkins.war`
- JDK: `C:\jdk21.zip`
- Git: `C:\git-setup.exe`
- .NET: `C:\dotnet-install.ps1` と `C:\dotnet`
- エージェント: `C:\Jenkins\workspace\agent.jar`

再利用時は `既存のファイルを使います:`、壊れているときは `取得済みファイルが壊れているため削除します:` と表示されます。`agent.jar` は ZIP 形式でなければ、表示せず削除して取り直します。

Git、JDK、Jenkins は SHA256 を確認します。.NET のスクリプトは空でないことだけを確認し、`agent.jar` は SHA256 を確認しません。

---

<!-- _class: tight -->

## 再起動後

サーバー起動時に `CISetup Jenkins` と `CISetup Jenkins Agent` を SYSTEM で起動するタスクを登録します。異常終了時は1分間隔で10回まで起動し直します。

エージェントは Jenkins の応答を最大8分待ってから接続します。

Jenkins のログイン画面を開き、`Manage Jenkins → Nodes` で `windows-agent` がオンラインであることを確認します。

---

<!-- _class: tight -->

## 再起動後のジョブ実行アカウント

起動タスクは Jenkins とエージェントを SYSTEM で起動します。その場合、ジョブも SYSTEM で実行されます。

- 共有フォルダへはコンピューターアカウントでアクセスする
- ユーザープロファイルの Git 資格情報は使われない
- ジョブを編集できる人は SYSTEM 権限でコマンドを実行できる


---

# スクリプトを使わない場合

---

<!-- _class: tight -->

## いつこちらを使うか

`tools/Setup-JenkinsServer.ps1` を実行せず、Jenkins の Windows MSI 版と CISetup の「Jenkins サーバー初回設定」を使う場合の手順です。

この進め方では、スクリプトが行う次の作業は自動化されません。

- Git、.NET SDK、JDK の導入
- WAR の配置、起動タスク、ファイアウォール規則の追加
- 管理者パスワードファイルと API Token ファイルの作成

Jenkins は MSI でインストールします。API Token は Jenkins の画面で発行し、エージェントに必要なソフトウェアはエージェント PC へインストールします。

---

<!-- _class: tight -->

## 1. Jenkins をインストールする

Jenkins サーバーで操作します。

1. [jenkins.io/download](https://www.jenkins.io/download/) を開く
2. Jenkins LTS の Windows MSI を入手する
3. MSI を実行し、画面の案内に従ってインストールする
4. インストール後、ブラウザで Jenkins を開く
5. Jenkins の画面に従って初期設定を完了する
6. Jenkins のホーム画面が開くことを確認する

CISetup の「環境チェック（まず確認）」にある「アプリで自動化できない準備（手順とリンク）」からも、Jenkins のダウンロードページを開けます。

---

<!-- _class: tight -->

## 2. API Token を発行する

Jenkins の画面で操作します。

1. 右上のユーザー名を押す
2. `Configure` を開く
3. `API Token` の `Add new Token` を押す
4. 発行された API Token をコピーし、安全な場所に保管する

API Token は発行直後にコピーします。CISetup には Jenkins のログインパスワードではなく、この API Token を入力します。

---

<!-- _class: tight -->

## 3. CISetup から接続を確認する

設定用 PC で操作します。

1. CISetup のアイコンをダブルクリックする
2. 「⑤ Jenkins への接続」までスクロールする
3. Jenkins URL、ユーザー名、API Token を入力する
4. 「接続テスト」を押す
5. 「接続成功」ダイアログに次の文が表示されることを確認する

> Jenkins への接続に成功しました。

別 PC の CISetup から接続する場合、Jenkins URL には `localhost` ではなく、設定用 PC から到達できるホスト名または IP アドレスを使います。

---

<!-- _class: tight -->

## 4. Jenkins サーバーを初期設定する

1. 「詳細設定（ふだんは開かなくて OK・自動入力されています）」を開く
2. 「Jenkins サーバー初回設定（はじめてのときだけ）」までスクロールする
3. エージェント名が `windows-agent` であることを確認する
4. エージェント作業フォルダが `C:\Jenkins\workspace` であることを確認する
5. 「Jenkins サーバーを初期設定」を押す
6. 「Jenkins サーバーの初期設定が完了しました。」と表示されるまで待つ

この操作は、Jenkins への接続確認、必須プラグイン7個の導入、Jenkins URL の設定、Windows エージェントの登録、起動コマンドの取得を行います。

---

<!-- _class: tight -->

## 5. Jenkins の再起動が必要な場合

「プラグインインストール後、Jenkins の再起動が必要です。」と表示された場合は、次の順で進めます。

1. Jenkins を再起動する
2. Jenkins のホーム画面が開くまで待つ
3. CISetup に戻る
4. 「Jenkins サーバーを初期設定」をもう一度押す
5. 初期設定の完了メッセージを確認する

再起動が必要と表示されなかった場合は、次の「エージェント起動コマンドをコピーする」へ進みます。

---

<!-- _class: tight -->

## 6. エージェント起動コマンドをコピーする

「Jenkins サーバー初回設定」の下にある「エージェント PC で実行するコマンド」を確認します。

1. コマンドが表示されていることを確認する
2. 「起動コマンドをコピー」を押す
3. エージェントにする PC へコマンドを安全な方法で渡す

起動コマンドにはエージェント接続用の secret が含まれます。資料や作業記録へ貼り付けず、取り扱いに注意します。

同一サーバーをエージェントにする場合は、Jenkins サーバー上で次の操作を行います。

---

<!-- _class: tight -->

## 7. エージェントを起動する

エージェントにする PC で操作します。

1. Java 11 以上をインストールする
2. CISetup の「.NET SDK」で指定した .NET SDK をインストールする
3. Git をインストールする
4. PowerShell を開く
5. コピーした起動コマンドを貼り付けて実行する
6. エージェントの接続中は PowerShell を閉じない

起動コマンドは `agent.jar` を取得し、エージェント名 `windows-agent`、作業フォルダ `C:\Jenkins\workspace` で Jenkins へ接続します。

---

<!-- _class: tight -->

## 8. オンラインと接続成功を確認する

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `windows-agent` がオンラインであることを確認する
4. 設定用 PC の CISetup で「接続テスト」を押す
5. 次の文が表示されることを確認する

> Jenkins への接続に成功しました。

`windows-agent` のオンラインと CISetup の接続成功を確認できれば、初回セットアップは完了です。

次は、対象プロジェクトの Git URL などを入力し、CI ジョブを作成します。
