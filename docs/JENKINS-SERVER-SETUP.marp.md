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

<p class="meta">2026年11月12日<br>version 1.4<br>HW部 仲松</p>

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

---

<!-- _class: tight -->

## 対象

次のソフトウェアとファイルがない Windows サーバーを対象とします。

- Jenkins
- Git for Windows（`C:\Program Files\Git`）
- JDK（`C:\jdk21`）
- .NET SDK（`C:\dotnet`）
- `C:\jenkins`、`C:\jenkins.war`

Jenkins と `windows-agent` は同じサーバーで動かします。スクリプトは .NET SDK 8 もこのサーバーへ導入します。

既存 Jenkins からの移行、別 PC エージェントの構築、プロキシが必要な環境、`-SkipAgent`、`-ProjectPath`、`-FileShare`、`-CISetupExe` の使用方法は扱いません。

---

## この手順で行うこと

| 行うこと | 行わないこと |
|---|---|
| Git、JDK 21、.NET SDK 8 の導入 | プロジェクト用 CI ジョブの作成 |
| Jenkins LTS の配置と起動 | Git や Teams の設定 |
| 管理者、プラグイン、API Token の準備 | HTTPS 化、Windows サービス化 |
| 同一サーバー上のエージェント作成 | |
| サーバー起動時の自動起動 | |
| CISetup からの接続テスト | テストビルド |

---

## 完了条件

設定用 PC の CISetup で、次のメッセージが表示されること。

> Jenkins への接続に成功しました。

あわせて、次の2点を確認します。

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
    ├─ JDK 21
    ├─ Git for Windows
    ├─ .NET SDK 8
    └─ windows-agent（インバウンド接続、ラベルなし）
```

Jenkins とエージェントは Windows サービスではありません。サーバー起動時にタスク スケジューラから自動で起動し、ログオンしていなくても動きます。ウィンドウは開きません。

---

# 1. 実行前の準備

---

<!-- _class: tight -->

## 用意するもの

| 項目 | 内容 |
|---|---|
| リポジトリ一式 | Jenkins サーバー上へコピーする |
| 設定用 PC | CISetup を起動できる PC |
| Jenkins URL | 設定用 PC から開ける URL。例: `http://ci-server:8080/` |
| 管理者ユーザー名 | 既定値は `admin` |
| 管理者パスワード | 省略すると生成する。指定もできる |

`-AdminPassword` を省略すると、英数字 24 文字のパスワードを作ります。Jenkins の起動前に `C:\jenkins\cisetup-admin-password.txt` へ保存し、完了時にも表示します。再実行で省略した場合は、そのファイルの値を使います。

パスワードは、空白を含まない ASCII の表示文字だけを受け付けます。空白や ASCII 以外を指定すると停止します。

`$` は確認済みです。`'`、`"`、`\` は未確認のため使わないでください。

---

<!-- _class: tight -->

## 実行条件

- コンソールまたは RDP でログオンし、そのデスクトップで管理者 PowerShell を開く
- WinRM などのリモート PowerShell は対象外
- TCP 8080（`-Port` の値）と TCP 50000 がほかの用途で使われていない
- 設定用 PC から、指定する Jenkins URL へ到達できる
- 配布元と Jenkins 更新サイトへ HTTPS で接続できる

スクリプト内の Jenkins 操作とエージェント接続には `http://localhost:<Port>/` が使われます。サーバー自身から、指定する Jenkins URL へ到達する必要はありません。

スクリプトはプロキシを設定せず、`start-jenkins.bat` も実行のたびに再生成します。プロキシが必要な環境は、この手順の対象外です。

---

<!-- _class: tight -->

## 初回実行時の外部通信

- Git for Windows: `github.com`
- .NET インストールスクリプト: `dot.net`
- JDK 21: `github.com`（Adoptium Temurin 21.0.13+9）
- Jenkins LTS 2.580.2: `get.jenkins.io`
- Jenkins 更新サイト: `updates.jenkins.io`

.NET SDK 本体は `builds.dotnet.microsoft.com` から取得されます。プラグイン本体を含む配布物は、別ホストへリダイレクトされる場合があります。

許可リスト方式の環境では、検証環境で実際の通信先を確認してから申請してください。

---

<!-- _class: tight -->

## 導入される版と方式

| 対象 | 導入内容 |
|---|---|
| Git | Git for Windows 2.47.1.2 |
| .NET | .NET SDK 8.0 チャネル |
| Java | Adoptium Temurin 21.0.13+9 |
| Jenkins | Jenkins LTS 2.580.2 の WAR |
| Jenkins の起動 | `java -jar`。セットアップウィザードは無効 |
| エージェント | 同一サーバーからのインバウンド接続 |

CISetup の画面は MSI 版 Jenkins と「Jenkins サーバー初回設定」を案内しますが、この手順ではどちらも使用しません。WAR の配置からエージェント登録までを PowerShell スクリプトが行います。

Windows サービスとして登録しないため、環境スキャンの「Jenkins サービス（この PC）」が未検出でも正常です。

---

<!-- _class: tight -->

## 検証状況

**確認日: 2026-11-11**

- `-JenkinsUrl http://localhost:8080/` で実行し、約7分で `==> 完了` まで進んだ（Git の導入時間は含まない）
- Jenkins 2.580.2、Temurin 21.0.13+9、.NET SDK 8.0.428 を導入。Git 2.47.1.windows.2 は導入済み
- `$` を含むパスワードで初期化とログインに成功した
- サーバー内から API Token で接続し、`windows-agent` のオンラインを確認した
- 組み込みノードの実行数 0、受信規則2件の有効、`agent any` のビルド成功を確認した
- プラグイン無効化時に、自動再起動、再確認、終了コード 1 のエラー終了を確認した
- 無効化を戻して再実行し、最後まで完了することを確認した

---

<!-- _class: tight -->

## 未確認事項

- 設定用 PC の CISetup からの接続テスト
- 設定用 PC からサーバー名の URL への接続
- 受信規則を通る通信、名前解決
- Windows Server、プロキシ環境
- .NET 以外の配布元のリダイレクト先
- RDP 切断時の Jenkins とエージェントの継続動作
- Git for Windows の新規導入（検証環境には導入済み）
- パスワードの `\`、`"`
- パスワードの自動生成、アクセス権の制限、localhost だけに限った TCP 50000 の受信規則
- `timestamper` を追加した後の、CISetup のテストビルド
- 既定値のランダム生成と、フォルダの権限制限を入れた後の再実行（再確認が必要）

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

## 実行コマンド

`ci-server` は、設定用 PC から名前解決できる Jenkins サーバー名に置き換えます。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin' `
  -AdminPassword '<管理者パスワード>'
```

`-JenkinsUrl` のポート番号は `-Port` と一致させます。

---

<!-- _class: tight -->

## スクリプトの処理

1. Git for Windows 2.47.1.2 を導入する
2. .NET SDK 8 を `C:\dotnet` へ導入し、マシン PATH の先頭へ追加する
3. JDK 21 を `C:\jdk21` へ展開し、マシン PATH の先頭へ追加する
4. Jenkins LTS WAR を `C:\jenkins.war` へ配置する
5. 初期設定用 Groovy と `start-jenkins.bat` を作成する
6. Windows ファイアウォールへ、JDK の `java.exe` を対象にした HTTP の受信規則と、localhost だけの TCP 50000 の受信規則を追加する
7. Jenkins を起動し、管理者と基本設定を作成する
8. 必要なプラグインを導入し、有効化を確認する
9. `windows-agent` を登録、起動し、オンラインを確認する
10. `cisetup` という名前の API Token を発行する

---

<!-- _class: tight -->

## 待ち時間

| 処理 | 上限 |
|---|---:|
| Jenkins の応答待ち | 1回につき8分 |
| Groovy 呼び出し1回 | 10分 |
| プラグイン導入 | 最大3回試す。失敗時は30秒待つ |
| エージェントのオンライン待ち | 3分。1回起動し直し、さらに3分 |

プラグイン導入後に再起動が必要な場合は、スクリプトが再起動します。有効化の確認で問題を検出した場合も、1回だけ自動で再起動して確認し直します。

停止した場合は原因を解消し、同じコマンドを再実行します。`==> 完了` より前は、API Token が未発行の場合があります。

---

<!-- _class: tight -->

## プラグイン反映時の再起動

プラグイン導入後に再起動が必要な場合、スクリプトは Jenkins を停止して起動し直します。画面は開きません。出力は `C:\jenkins\jenkins.log` に追記します。

有効化の確認に失敗した場合は、次を表示して同じ再起動と再確認を1回行います。

```text
プラグインが有効になっていません。Jenkins を再起動して、もう一度確認します。
```

実行元の PowerShell は閉じないでください。Jenkins とエージェントの画面は開きません。

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`
- `timestamper`（CISetup が作るパイプラインの `timestamps()` で使う）

導入後、スクリプトは次の形式の行を出力します。

```text
Result: OK: plugins active (workflow-aggregator, git, credentials-binding, plain-credentials, parameterized-trigger, naginator, timestamper)
```

この行が出ない場合は、プラグインの準備が完了していません。

---

<!-- _class: tight -->

## ファイアウォール規則

| 表示名 | ポート | プロファイル／リモートアドレス |
|---|---:|---|
| `CISetup Jenkins HTTP` | `-Port` の値 | スクリプトでは限定しない |
| `CISetup Jenkins Agent` | 50000 | 送信元は `127.0.0.1` だけ |

どの規則も、導入した JDK の `java.exe` だけが対象です。起動前にこの規則を作るため、Windows が OpenJDK の通信許可を尋ねる画面は出ません。Windows は `::1` を送信元に指定できません。同じ PC 内の通信は受信規則の対象外のため、`127.0.0.1` の1件だけにしています。

規則の追加に失敗しても処理は続き、完了時にも失敗した規則名が表示されます。

エージェントは同じサーバーの localhost から TCP 50000 へ接続します。この受信規則は外部へは開けません。

---

## 完了表示

`==> 完了` の後に、次の情報が表示されます。

- Jenkins URL
- ユーザー、パスワード、API Token
- パスワードの保存先
- プラグインの確認結果
- エージェント名と作業フォルダ
- Jenkins の起動スクリプト
- ジョブが SYSTEM で動くこと

CISetup へ入力するのは、Jenkins URL、ユーザー、API Token の3項目です。

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

`C:\jenkins`、`C:\Jenkins\workspace`、`C:\jdk21`、`C:\dotnet`、`C:\jenkins.war` は、継承を切り、SYSTEM と Administrators だけがアクセスできるようにします。サーバー起動時に SYSTEM がこれらを実行するため、一般ユーザーに書き換えさせないためです。

---

<!-- _class: tight -->

## 秘密情報の扱い

次の場所に秘密情報が残ります。

- 完了表示: 管理者パスワード、API Token
- 実行途中の出力: エージェント secret
- PowerShell の履歴: 管理者パスワード
- 実行中の `powershell.exe` のコマンドライン: 管理者パスワード
- エージェントのプロセスのコマンドライン: エージェント secret
- 初期設定用 Groovy、パスワードファイル: 管理者パスワード
- Token ファイル: API Token
- `start-agent.bat`: エージェント secret

共有サーバーでは、プロセス情報や監査ログを閲覧できる利用者にも注意してください。実行中の画面共有を避け、保存するログから秘密情報を除きます。

---

<!-- _class: tight -->

## 管理者設定の注意

Jenkins の起動時に、セキュリティレルムが `HudsonPrivateSecurityRealm` でない場合、初期設定用 Groovy は Jenkins 独自のユーザーデータベースを作り、指定した管理者アカウントを登録します。

- パスワードを変えて再実行しても、既存アカウントのパスワードは変わらない
- `-AdminPassword` を省略し、パスワードファイルがあれば、その保存値を使う
- パスワードファイルがなければ生成して、Jenkins の起動前に保存する
- 空白や ASCII 以外のパスワードは受け付けない
- 起動時に Jenkins URL、待受ポート 50000、組み込みノードの実行数 0 を設定する

後で Active Directory や LDAP などへ切り替える場合は、先に `01-cisetup-bootstrap.groovy` を `init.groovy.d` から外してください。残したまま起動すると、Jenkins 独自のユーザーデータベースと認可設定へ戻ります。

---

# 3. CISetup で接続を確認する

---

## CISetup へ入力する

設定用 PC で CISetup を開き、「⑤ Jenkins への接続」へ入力します。

| CISetup の項目 | 入力値 |
|---|---|
| Jenkins URL | 完了表示の `Jenkins URL` |
| ユーザー名 | 完了表示の `ユーザー` |
| API Token | 完了表示の `API Token` |

API Token は `C:\jenkins\cisetup-api-token.txt` でも確認できます。安全な方法で設定用 PC へ渡し、転記ミスを避けます。

Git リポジトリ URL、Git の資格情報、Teams Webhook は、この接続テストには不要です。

---

## 接続テスト

1. `OK: plugins active` に7個の ID があることを確認する
2. Jenkins URL、ユーザー名、API Token を入力する
3. 「接続テスト」を押す
4. 次のメッセージを確認する

> Jenkins への接続に成功しました。

設定用 PC から指定した URL へ到達し、入力したユーザー名と API Token で Jenkins API に認証できたことを示します。

---

## エージェントラベル

詳細設定の「エージェントラベル」は空欄にします。既定値も空欄です。

- `windows-agent` はラベルなしで作成される
- Jenkins の組み込みノードは実行数 0 に設定される
- ラベルが空欄の場合、CISetup は Jenkinsfile に `agent any` を生成する

ヘルプの例にある `windows` は入力しません。`windows-agent` にそのラベルがないため、入力するとビルドが割り当てられません。

---

## エージェントを確認する

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `windows-agent` がオンラインであることを確認する

オンラインにならない場合、スクリプトは1回だけ起動し直します。それでも接続できなければ、完了表示の前に停止します。

エージェントは同じサーバー上の `http://localhost:<Port>/` を指定して起動し、TCP 50000 へ接続します。

---

# 4. 初回実行が止まったとき

---

## 再実行の原則

スクリプトが停止したら、表示されたエラーと `C:\jenkins\jenkins.log`、`C:\Jenkins\workspace\agent.log` を確認します。

1. エラーの原因を解消する
2. 最初に使用したものと同じコマンドを再実行する
3. `==> 完了` が表示されるまで続ける

スクリプトは起動中の Jenkins を検出して再利用します。エージェントが起動中でもオンラインでなければ、終了させて起動し直します。再実行前に Jenkins やエージェントを手作業で終了する必要はありません。

---

<!-- _class: tight -->

## 停止しない表示

次の表示だけでは、スクリプトは停止しません。

```text
ファイアウォール規則を追加できませんでした: <規則名>
ファイアウォール規則を削除できませんでした: <規則名>
crumb は取得しませんでした。そのまま Script Console を呼びます。
プラグインの導入を 30 秒後にやり直します（1 回目に失敗）。
プラグインが有効になっていません。Jenkins を再起動して、もう一度確認します。
エージェント状態の取得を再試行します。
エージェントがオンラインになりません。起動し直します。
保存済みの API Token がトークンの形式ではないため、発行し直します。
```

後続処理が成功したかは、`==> 完了` とプラグインの確認結果で判断します。

---

<!-- _class: tight -->

## 主なエラーと対処（導入）

| 表示 | 対処 |
|---|---|
| `管理者として実行してください。` | 管理者 PowerShell で再実行 |
| ダウンロード中の例外 | 外部通信を確認して再実行 |
| `ダウンロードしたファイルを確認できませんでした` | 配布元と通信経路を確認して再実行 |
| `Git のインストーラーが終了コード ...` | 原因を解消して再実行。不明なら `C:\git-setup.exe` を削除 |
| `Git のインストール後も ... が見つかりません` | `C:\git-setup.exe` を削除して再実行 |
| `.NET SDK のインストーラーが終了コード ...` | `C:\dotnet-install.ps1` を削除して再実行 |
| `.NET SDK の展開後も ...` | `C:\dotnet-install.ps1` と `C:\dotnet` を削除して再実行 |
| `.NET SDK 8 が見つかりません` | `C:\dotnet` を削除して再実行 |

---

<!-- _class: tight -->

## 主なエラーと対処（JDK・Jenkins）

| 表示 | 対処 |
|---|---|
| `JDK 21 の展開に失敗しました` | zip は削除済み。そのまま再実行 |
| `JDK 21 の展開後も java.exe が見つかりません` | `C:\jdk21.zip` を削除して再実行 |
| `PATH に追加する場所がありません` | 表示されたフォルダを確認して再実行 |
| `Jenkins が 8 分以内に ... 応答しませんでした` | Jenkins の表示を確認。WAR 読込エラーなら WAR を削除 |

---

<!-- _class: tight -->

## 主なエラーと対処（JDK・Jenkins）

| 表示 | 対処 |
|---|---|
| `Jenkins へのログインに失敗しました` | 初回のパスワードを確認。作り直す場合は後述 |
| `プラグインの導入に 3 回失敗しました` | `結果:` から通信、認証、HTTP エラーを確認して再実行 |
| `必要なプラグインが再起動しても有効になりませんでした` | Plugins 画面の状態と `C:\jenkins\jenkins.log` を確認。直して同じコマンドを再実行 |

再実行時も、スクリプトが必要に応じて Jenkins を再起動し、有効化を確認します。

---

<!-- _class: tight -->

## 主なエラーと対処（エージェント・Token）

| 表示 | 対処 |
|---|---|
| `エージェントの secret を取得できませんでした` | 結果と Nodes 画面を確認して再実行 |
| `agent.jar を確認できませんでした` | Jenkins への通信を確認して再実行 |
| `エージェント ... が起動し直しても 6 分以内にオンラインになりませんでした` | `C:\Jenkins\workspace\agent.log` と Nodes 画面のログを確認して再実行 |
| `API Token を発行できませんでした` | 結果を確認して再実行。成功するまで Token ファイルは作られない |

エージェント待ちで停止した時点では、API Token 発行と完了表示は未実行です。同じコマンドを再実行します。

---

## Jenkins の起動を確認する

スクリプトは Jenkins とエージェントの画面を開きません。出力は `C:\jenkins\jenkins.log` と `C:\Jenkins\workspace\agent.log` に追記します。

画面で追うときは、管理者 PowerShell から起動します。

```powershell
& 'C:\jenkins\start-jenkins.bat' window
```

`window` を付けると、終了時に表示が残ります。この PowerShell は Jenkins が終了するまで戻りません。応答確認とスクリプトの再実行は、別の管理者 PowerShell で行います。

---

<!-- _class: tight -->

## 接続テストが失敗したとき

「Jenkins サーバーに接続できませんでした。」の場合:

1. サーバーで `http://localhost:8080/login` を開く
2. 開けなければ Jenkins の起動状態と `-Port` を確認する
3. 設定用 PC で完了表示の Jenkins URL を開く
4. 設定用 PC だけ開けなければ、HTTP の受信規則、ポート、名前解決を確認する

`-Port` を 8080 以外にした場合は、確認 URL のポートも置き換えます。

---

<!-- _class: tight -->

## 認証エラーと API Token の再発行

「Jenkins 認証エラー (401 Unauthorized)」の場合:

1. CISetup のユーザー名と API Token を転記し直す
2. `C:\jenkins\cisetup-api-token.txt` の内容と照合する
3. 解決しなければ、トークンファイルを削除する
4. 最初に使用したものと同じコマンドを再実行する
5. 新しい API Token を CISetup へ入力する

```powershell
Remove-Item 'C:\jenkins\cisetup-api-token.txt'
```

再実行で `cisetup` という名前のトークンが追加されます。古いトークンは Jenkins の API Token 画面で失効させます。

---

## Jenkins の設定を作り直す場合

管理者アカウントを含めて作り直す場合は、Jenkins とエージェントを終了してから `C:\jenkins` を削除し、同じコマンドを再実行します。

`C:\jenkins` を削除すると、配下のエージェント作業フォルダ、`agent.jar`、`start-agent.bat` も消え、再実行で作り直されます。

Git for Windows、`C:\jdk21`、`C:\dotnet`、`C:\jenkins.war`、マシン PATH、ファイアウォール規則は残り、再実行時に再利用されます。

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

## 再起動後

サーバーを再起動すると、タスク スケジューラの `CISetup Jenkins` と `CISetup Jenkins Agent` が SYSTEM で起動します。ログオンは不要で、ウィンドウは開きません。エージェントは Jenkins の応答を最大8分待ってから接続します。起動に失敗したときは、1分間隔で10回まで起動し直します。

手動で起動して画面を残すときは、次の順に実行します。

1. 管理者 PowerShell で `C:\jenkins\start-jenkins.bat window` を実行する
2. 別のウィンドウで `http://localhost:8080/login` が開くことを確認する
3. 別のウィンドウで `C:\Jenkins\workspace\start-agent.bat window` を実行する
4. Jenkins の Nodes 画面で `windows-agent` のオンラインを確認する

`-Port` が 8080 以外なら、確認 URL のポートを置き換えます。`window` を付けたときだけ、終了時に `pause` で表示が残ります。

---

<!-- _class: tight -->

## ジョブは SYSTEM で動く

自動起動した Jenkins のジョブは SYSTEM で実行されます。

- 共有フォルダへは、ログオン中のユーザーではなく、コンピューターアカウントでアクセスします
- ユーザープロファイルの Git 資格情報は使われません
- ジョブを編集できる人は、SYSTEM 権限でコマンドを実行できます

専用のサービスアカウントへ変える手順は、この手順の対象外です。

---

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

`OK: plugins active` に7個の ID があり、  
`windows-agent` がオンラインであれば、  
初回セットアップは完了です。

次は、対象プロジェクトの Git URL などを入力し、CI ジョブを作成します。
