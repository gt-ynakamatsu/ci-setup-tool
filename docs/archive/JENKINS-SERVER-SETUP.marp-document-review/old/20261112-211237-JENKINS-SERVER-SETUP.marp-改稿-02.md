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
| 1.6 | 2026-11-12 | 入っている Git、.NET SDK 8、Java 21 または 25 は再利用する。MSI 版 Jenkins があるときは WAR を置かない | 仲松 |
| 1.7 | 2026-11-12 | 対象外の条件、ログイン失敗時の回復、エージェントの手動起動、エラーと対処、実行アカウントの説明を追加 | 仲松 |

---

<!-- _class: tight -->

## 対象

Jenkins、Git、JDK、.NET が入っていない Windows サーバーへ、新しい Jenkins 環境を構築する手順です。

初回実行前に次のいずれかがあるサーバーは対象外です。

- MSI 版 Jenkins
- `C:\jdk21`、`C:\dotnet`、`C:\jenkins`、`C:\jenkins.war`
- `jenkins.war` をコマンドラインに含む `java.exe` で動いている Jenkins

この手順の途中まで進んだあとの再実行では、スクリプトが作成した上記のフォルダやファイルがあっても対象外ではありません。「再実行の原則」に従います。

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

MSI 版は Windows の「インストールされているアプリ」で確認します。スクリプトが判定するのは、アンインストール登録の表示名が Jenkins で、`WindowsInstaller` が `1` のものです。

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
    ├─ Java 21
    ├─ Git for Windows
    ├─ .NET SDK 8
    └─ windows-agent（インバウンド接続、ラベルなし）
```

Jenkins とエージェントは Windows サービスではありません。セットアップ中は、スクリプトが実行者と同じユーザーから非表示で起動します。サーバー起動時に SYSTEM で起動するタスクも登録します。再起動後の動作は未確認です。

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
| 管理者パスワード | 省略すると英数字24文字を生成する。指定もできる |

パスワードは空白を含まない ASCII の表示文字だけを受け付けます。`$` は確認済みです。`'`、`"`、`\` は未確認のため使わないでください。

省略時は `C:\jenkins\cisetup-admin-password.txt` へ保存します。再実行時に同ファイルがあれば、その値を使います。

---

<!-- _class: tight -->

## 実行条件

- コンソールまたは RDP でログオンし、そのデスクトップで管理者 PowerShell を開く
- WinRM などのリモート PowerShellは使わない
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

## 入っていた場合のスクリプトの動き

次の分岐はスクリプトから確認できますが、検証環境では未確認です。

- Git: `C:\Program Files\Git\cmd\git.exe` または PATH 上の `git.exe` を使う。版は確認しない
- .NET: PATH、`C:\Program Files\dotnet`、`C:\dotnet` の順で SDK 8 を探して使う
- Java: `C:\jdk21`、PATH、主要な `C:\Program Files` 配下で Java 21 または 25 を探して使う

PATH、`C:\Program Files\dotnet`、`C:\dotnet` のどこにも SDK 8 がなく、`C:\dotnet` が存在するときは、導入前に同フォルダのアクセス権を制限します。

---

<!-- _class: tight -->

## 再利用とアクセス権

`C:\jdk21` 配下の Java または `C:\dotnet` 配下の .NET SDK 8 を使う場合は、そのフォルダのアクセス権を SYSTEM と Administrators に限定し、実行ファイルのあるフォルダをマシン PATH の先頭へ追加します。

探索先に Java 21 または 25 がなければ、既存の `C:\jdk21` を削除して JDK 21 を展開します。

Program Files や PATH にある既存 Java、既存 .NET SDK 8 を使う場合、その導入先のアクセス権は変更しません。

アクセス権を限定するのは、サーバー起動時に SYSTEM が実行するファイルと秘密情報を、一般ユーザーから書き換え・読み取りできないようにするためです。

---

<!-- _class: tight -->

## MSI 版 Jenkins が見つかった場合

スクリプトは Git、.NET SDK 8、Java 21 または 25 を確認し、必要な導入、`C:\jdk21` と `C:\dotnet` のアクセス権制限、PATH 追加を行ったあとで MSI 版 Jenkins を判定します。

MSI 版が見つかると、WAR の配置、起動、プラグイン導入を行わず、終了コード `0` で終了します。`==> 完了` は表示されません。ここまでの導入、PATH 変更、アクセス権変更は残ります。

このスクリプトの Jenkins を使うには、MSI 版をアンインストールして再実行します。アンインストール時の既存データの扱いは、この手順では扱いません。

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
- API Token で接続し、`windows-agent` のオンラインを確認した
- 組み込みノードの実行数 0、受信規則2件の有効、`agent any` のビルド成功を確認した
- プラグイン無効化時の自動再起動、再確認、エラー終了と、修正後の再実行を確認した
- `timestamper` 追加後、CISetup のテストビルド #2 が成功した（1分58秒）

---

<!-- _class: tight -->

## 未確認事項

- 設定用 PC の CISetup からの接続テスト、サーバー名での接続、受信規則を通る通信、名前解決
- Windows Server、プロキシ環境、配布元のリダイレクト先
- Git の新規導入、既存 .NET SDK 8 と既存 Java 21 または 25 の再利用、MSI 版 Jenkins の検出
- パスワードの `'`、`"`、`\`、初回の自動生成、権限制限後の再実行
- RDP 切断またはサインアウト後の継続動作
- 再起動後に起動タスクから Jenkins とエージェントが起動した記録
- 再起動前のジョブの実行アカウント、資格情報の扱い、権限レベル
- Jenkins とエージェントを手動で安全に停止する手順
- 2026-11-11 の各検証項目で使用したスクリプトの版

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

## 実行コマンド

`ci-server` は、設定用 PC から名前解決できるサーバー名に置き換えます。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin' `
  -AdminPassword '<管理者パスワード>'
```

パスワードを生成する場合は、最後の行を省略します。省略すれば、パスワードはコマンド履歴と実行中の `powershell.exe` のコマンドラインに引数として残りません。

`-JenkinsUrl` のポート番号は `-Port` と一致させます。`==> 完了` または MSI 版の案内まで、この PowerShell を閉じたりサインアウトしたりしないでください。

---

<!-- _class: tight -->

## スクリプトの処理

1. Git を確認し、なければ導入する
2. .NET SDK 8 を確認し、必要なら `C:\dotnet` のアクセス権を制限して導入する。`C:\dotnet` を使う場合は PATH の先頭へ追加する
3. Java 21 または 25 を確認し、なければ JDK 21 を `C:\jdk21` へ展開する。`C:\jdk21` を使う場合はアクセス権を制限し、PATH の先頭へ追加する
4. MSI 版 Jenkins を確認し、見つかれば案内を表示して終了する
5. WAR を `C:\jenkins.war` へ保存し、アクセス権を制限する
6. `C:\jenkins` と、その配下に作る `C:\Jenkins\workspace` のアクセス権を制限し、パスワードファイルを保存する
7. 初期設定用 Groovy と起動バッチを作り、Jenkins の起動タスクを登録する
8. ファイアウォール規則を追加し、Jenkins を起動する
9. 管理者、基本設定、プラグインを用意する
10. エージェントを登録し、起動バッチと起動タスクを作って起動する
11. エージェントのオンラインを確認し、API Token を発行する
12. 最後に各フォルダと WAR のアクセス権を再度制限する

---

<!-- _class: tight -->

## 待ち時間

| 処理 | 上限 |
|---|---:|
| Jenkins の応答待ち | 1回につき8分 |
| Groovy 呼び出し1回 | 10分 |
| プラグイン導入 | 最大3回。失敗時は30秒待つ |
| エージェントのオンライン待ち | 3分。1回起動し直し、さらに3分 |

プラグイン反映の再起動では、スクリプトが起動タスクを一時的に無効化し、`jenkins.war` を含む `java.exe` と親の `cmd.exe` を停止してから Jenkins を起動します。エージェントの起動し直しでは、同様にエージェントの起動タスクを一時的に無効化し、`agent.jar` を含む `java.exe` と起動バッチの `cmd.exe` を停止します。

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

## ファイアウォール規則

| 表示名 | ポート | リモートアドレス |
|---|---:|---|
| `CISetup Jenkins HTTP` | `-Port` の値 | スクリプトでは限定しない |
| `CISetup Jenkins Agent` | 50000 | `127.0.0.1` |

どちらも使用する JDK の `java.exe` が対象です。エージェントは同じサーバーの localhost から TCP 50000 へ接続します。規則の追加に失敗しても処理は続き、完了時に規則名が表示されます。

---

<!-- _class: tight -->

## 完了表示

`==> 完了` の後に、Jenkins URL、ユーザー、パスワード、API Token、プラグインの確認結果、エージェント名、作業フォルダ、起動スクリプト、パスワードの保存先が表示されます。

セットアップ中の Jenkins とエージェントは、`Start-Process` により、スクリプト実行者と同じユーザーから起動します。再起動前のジョブの実行アカウント、資格情報、権限レベルは未確認です。

完了表示の「ジョブも SYSTEM で動きます」は、サーバー再起動後に、起動タスクから Jenkins とエージェントが起動した場合の説明です。

CISetup へ入力するのは Jenkins URL、ユーザー、API Token の3項目です。

---

<!-- _class: tight -->

## 作成される主なファイル

| パス | 内容 | 含む秘密情報 |
|---|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動 | なし |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者と基本設定 | 管理者パスワード |
| `C:\jenkins\cisetup-admin-password.txt` | 管理者パスワード | 管理者パスワード |
| `C:\jenkins\cisetup-api-token.txt` | API Token | API Token |
| `C:\Jenkins\workspace\agent.jar` | エージェント本体 | なし |
| `C:\Jenkins\workspace\start-agent.bat` | エージェント起動 | エージェント secret |

`C:\Jenkins\workspace` は `C:\jenkins` の配下です。`C:\jenkins`、同作業フォルダ、`C:\jenkins.war` は SYSTEM と Administrators だけがアクセスできるようにします。

---

<!-- _class: tight -->

## 秘密情報の扱い

秘密情報は、完了表示、初期設定用 Groovy、パスワードファイル、Token ファイル、`start-agent.bat`、エージェントのプロセスのコマンドラインに残ります。

`-AdminPassword` を指定した場合は、PowerShell の履歴と実行中の `powershell.exe` のコマンドラインにも残ります。

共有サーバーでは、プロセス情報や監査ログを閲覧できる利用者にも注意してください。実行中の画面共有を避け、保存するログから秘密情報を除きます。

---

# 3. CISetup で接続を確認する

---

## CISetup へ入力する

設定用 PC で `CISetup.exe` のアイコンをダブルクリックし、「⑤ Jenkins への接続」へ入力します。

| CISetup の項目 | 入力値 |
|---|---|
| Jenkins URL | 完了表示の `Jenkins URL` |
| ユーザー名 | 完了表示の `ユーザー` |
| API Token | 完了表示の `API Token` |

API Token は `C:\jenkins\cisetup-api-token.txt` でも確認できます。Git リポジトリ URL、Git の資格情報、Teams Webhook は、この接続テストには不要です。

---

## 接続テスト

1. `OK: plugins active` に7個の ID があることを確認する
2. Jenkins URL、ユーザー名、API Token を入力する
3. 「接続テスト」を押す
4. 次のメッセージを確認する

> Jenkins への接続に成功しました。

設定用 PC から指定 URL へ到達し、入力したユーザー名と API Token で Jenkins API に認証できたことを示します。

---

## エージェントを確認する

詳細設定の「エージェントラベル」は空欄にします。

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `windows-agent` がオンラインであることを確認する

`windows-agent` はラベルなしで作成され、組み込みノードの実行数は 0 です。ラベルが空欄なら、CISetup は Jenkinsfile に `agent any` を生成します。

---

# 4. 初回実行が止まったとき

---

## 再実行の原則

表示されたエラーと `C:\jenkins\jenkins.log`、`C:\Jenkins\workspace\agent.log` を確認します。

1. エラーの原因を解消する
2. 最初と同じコマンドを再実行する
3. `==> 完了` まで進める

スクリプトは起動中の Jenkins を検出して再利用します。通常の再実行前に、手作業で停止する必要はありません。途中で作成されたフォルダやファイルは、エラーの対処で指示がある場合を除き削除しません。

---

<!-- _class: tight -->

## 主なエラーと対処

| 表示 | 対処 |
|---|---|
| `管理者として実行してください。` | 管理者 PowerShell で再実行 |
| ダウンロードまたは SHA256 のエラー | 配布元と通信経路を確認して再実行 |
| Git または .NET の導入エラー | 表示された取得物を削除して再実行 |
| `JDK 21 の展開に失敗しました` | zip は削除済み。そのまま再実行 |
| `Jenkins が 8 分以内に ... 応答しませんでした` | `jenkins.log` を確認。「起動を確認する」も参照 |
| `Jenkins へのログインに失敗しました` | 保存済みパスワードを照合。解決しなければ「設定を作り直す場合」へ進む |
| プラグインの導入または有効化エラー | 結果、Plugins 画面、`jenkins.log` を確認して再実行 |
| エージェントがオンラインにならない | `agent.log` と Nodes 画面を確認して再実行 |
| `API Token を発行できませんでした` | 結果を確認して再実行 |

---

<!-- _class: tight -->

## 起動を確認する

画面を残す前に、対象の `java.exe` が動いていないことを確認します。

```powershell
Get-CimInstance Win32_Process -Filter "Name = 'java.exe'" |
  Where-Object { $_.CommandLine -match 'jenkins\.war|agent\.jar' } |
  Select-Object ProcessId, CommandLine
```

`jenkins.war` が表示されない場合だけ、`& 'C:\jenkins\start-jenkins.bat' window` を実行します。`agent.jar` が表示されない場合だけ、別の管理者 PowerShell で `& 'C:\Jenkins\workspace\start-agent.bat' window` を実行します。

停止が必要なときは、この手順では止め方を扱いません。確認されるまではこのサーバーで続けず、サーバーの管理者と相談してください。

---

<!-- _class: tight -->

## 接続テストが失敗したとき

接続できない場合:

1. サーバーで `http://localhost:8080/login` を開く
2. 開けなければ Jenkins の起動状態と `-Port` を確認する
3. 設定用 PC で完了表示の Jenkins URL を開く
4. 設定用 PC だけ開けなければ、HTTP の受信規則、ポート、名前解決を確認する

認証エラーの場合は、CISetup のユーザー名と API Token を `C:\jenkins\cisetup-api-token.txt` と照合します。解決しなければ Token ファイルを削除し、同じコマンドを再実行して新しい Token を入力します。

---

<!-- _class: tight -->

## Jenkins の設定を作り直す場合

ログインに失敗すると、`C:\jenkins` を削除して再実行する案内がエラーの一部として表示されます。先に保存済みパスワードと初回指定値を照合してください。

作り直しには Jenkins とエージェントの停止が必要ですが、手動の停止手順は未確認です。確認されるまでは削除を始めず、サーバーの管理者と相談してください。

`C:\jenkins` を削除すると、設定、管理者アカウント、パスワード、API Token、エージェント作業フォルダが消えます。Git、`C:\jdk21`、`C:\dotnet`、`C:\jenkins.war`、PATH、ファイアウォール規則、起動タスク `CISetup Jenkins` と `CISetup Jenkins Agent` は残ります。再実行時に起動タスクは登録し直されます。

---

<!-- _class: tight -->

## 再起動後

タスク スケジューラへ、サーバー起動時に `CISetup Jenkins` と `CISetup Jenkins Agent` を SYSTEM で起動するタスクを登録します。異常終了したときは、1分間隔で10回まで起動し直す設定です。再起動後の動作は未確認です。

画面を残す場合は「起動を確認する」と同じ確認を行い、`jenkins.war` を含む `java.exe` がなければ `start-jenkins.bat window`、`agent.jar` を含む `java.exe` がなければ `start-agent.bat window` を別々の管理者 PowerShellで実行します。

Jenkins のログイン画面と、Nodes 画面の `windows-agent` のオンラインを確認します。

---

<!-- _class: tight -->

## 再起動後のジョブ実行アカウント

起動タスクから起動した Jenkins とエージェントは SYSTEM で動き、ジョブも SYSTEM で実行されます。

- 共有フォルダへはコンピューターアカウントでアクセスする
- ユーザープロファイルの Git 資格情報は使われない
- ジョブを編集できる人は SYSTEM 権限でコマンドを実行できる

専用のサービスアカウントへ変える手順は対象外です。再起動前のジョブについては、実行アカウント、資格情報、権限レベルを確認できていません。

---

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

`OK: plugins active` に7個の ID があり、  
`windows-agent` がオンラインであれば、  
初回セットアップは完了です。

次は、対象プロジェクトの Git URL などを入力し、CI ジョブを作成します。
