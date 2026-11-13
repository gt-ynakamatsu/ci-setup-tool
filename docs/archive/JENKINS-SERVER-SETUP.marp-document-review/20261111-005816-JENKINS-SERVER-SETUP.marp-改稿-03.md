---
marp: true
theme: default
paginate: true
size: 16:9
title: Jenkins サーバー セットアップ手順
description: CISetup から接続できる状態まで、Windows サーバーで用意する手順
style: |
  section { font-size: 28px; padding: 48px 64px; }
  section.lead h1 { font-size: 48px; }
  section.lead h2 { font-size: 30px; color: #555; }
  h1, h2 { color: #0078D4; }
  table { font-size: 22px; }
  code { font-size: 20px; }
  blockquote { font-size: 24px; border-left: 4px solid #0078D4; }
  section.small { font-size: 24px; }
  section.small table { font-size: 20px; }
  section.small code { font-size: 18px; }
---

<!-- _class: lead -->

# Jenkins サーバー
## セットアップ手順

`tools/Setup-JenkinsServer.ps1` の実行から  
CISetup の接続テスト成功まで

対象: Jenkins を動かす Windows サーバー

---

<!-- _class: small -->

## 検証状況

2026-11-10 に Windows Sandbox で手作業の手順を確認しました。確認時の Jenkins は 2.580.2 です。

`Setup-JenkinsServer.ps1` は、検証環境でも本番環境でも未実行です。管理者作成、URL 設定、プラグイン導入、ノード作成、トークン発行を含む全工程は実行確認していません。

次の事項も未確認です。

- CISetup の画面名、表示文言、設定用 PC が別の場合の環境スキャン結果
- 非対話セッション、プロキシ環境、配布元のリダイレクト先
- 秘密情報を保存するフォルダの継承アクセス権
- 別 PC エージェントの構築方法

本番実行前に、検証環境での試行とサーバーのスナップショット取得の要否を決めてください。

---

## この資料の範囲

| 行うこと | 行わないこと |
|---|---|
| Git、JDK 21、.NET SDK 8、Jenkins LTS の配置 | プロジェクトごとの CI ジョブ作成 |
| Jenkins 管理者、API トークン、プラグインの準備 | Teams Webhook の作成 |
| Jenkins URL、HTTP ポート、同一 PC エージェントの設定 | テストビルド |
| CISetup からの接続テスト | Jenkins とエージェントのサービス化 |

---

## 完了条件

設定用 PC の CISetup で、次のメッセージが表示されれば接続確認は完了です。

> Jenkins への接続に成功しました。

同一 PC をエージェントにする場合は、`<AgentName>`（既定 `windows-agent`）がオンラインであることも確認します。

スクリプトは API トークンを用意しますが、CISetup の接続テストとエージェントのオンライン確認は行いません。

---

## 構成

```text
設定用 PC（CISetup）
    │  http://<Jenkins サーバー>:<Port>/
    ▼
Jenkins サーバー
    ├─ Jenkins LTS（WAR、JDK 21）
    ├─ Git
    └─ <AgentName>（同一 PC 構成のみ）
         └─ .NET SDK 8
```

同一 PC エージェントは Jenkins の待受ポート TCP 50000 へ接続します。

別 PC エージェントの構築手順が決まるまでは、同一 PC 構成を使用します。

---

<!-- _class: lead -->

# 1. 実行前に確認する

---

<!-- _class: small -->

## 本番実行の前に決めること

| 判断事項 | スクリプトの動作 |
|---|---|
| 常時起動の方法 | Windows サービスには登録しない |
| 管理者パスワード | 初回の省略値は `cisetup-admin`。再実行時は保存済みファイルを優先 |
| Git、JDK、Jenkins の版 | 既存物を版の検証なしで再利用。新規取得する JDK と Jenkins は版を固定しない |
| 同一 PC／別 PC エージェント | 別 PC の構築手順はこの資料の対象外 |
| PATH 変更の影響 | JDK 21 と、必要時は .NET SDK 8 をマシン PATH の先頭へ追加 |

ほかのアプリが Java または .NET を PATH 経由で使っている場合は、影響を事前に確認します。

---

<!-- _class: small -->

## 既存の Jenkins を確認する

スクリプトを実行する前に、既存の Jenkins が動いていないことを確認します。MSI 版の Windows サービスも対象です。

既存 Jenkins を運用している場合は、次のどちらかを先に決めます。

- 停止して、この手順の WAR 版へ切り替える
- 既存環境を維持し、このスクリプトを使わない

スクリプトは、コマンドラインに `jenkins.war` を含む `java.exe` があると、新しい Jenkins を起動しません。プラグイン反映で再起動が必要な場合は、該当する `java.exe` を強制終了します。

既存環境と混在させた状態では実行しないでください。

---

<!-- _class: small -->

## 実行条件

- コンソールまたは RDP で対話ログオンし、そのデスクトップで管理者 PowerShell を開ける
- リポジトリ一式が Jenkins サーバー上にある
- 既存の Jenkins が停止している
- 使用する HTTP ポートと TCP 50000 が、ほかのプロセスと競合していない
- 設定用 PC から、指定する Jenkins URL に到達できる
- 同一 PC 構成では、Jenkins サーバー自身から Jenkins URL に到達できる
- 配布元と Jenkins 更新サイトへ HTTPS で接続できる
- プロキシが必要な場合は、PowerShell と Jenkins の通信方法を決めている

---

## 外部通信

スクリプトに記載された取得元:

- Git for Windows: `github.com`
- .NET インストールスクリプト: `dot.net`
- JDK 21: `api.adoptium.net`
- Jenkins LTS: `get.jenkins.io`
- Jenkins プラグイン: Jenkins の更新サイト

.NET SDK 本体は、インストールスクリプトが別ホストから取得します。

許可リスト方式の環境では、検証環境で実通信先を確認してから本番へ適用します。

---

## URL とポートを決める

| 項目 | 例 | 用途 |
|---|---|---|
| `-JenkinsUrl` | `http://ci-server:8080/` | CISetup、Jenkins の設定、エージェント接続 |
| `-Port` | `8080` | Jenkins のローカル待受、ファイアウォール規則 |

`-JenkinsUrl` を省略すると、`http://localhost:<Port>/` になります。設定用 PC が別 PC の場合は、ホスト名または IP アドレスを指定します。

リバースプロキシを使わない場合は、`-JenkinsUrl` のポートを `-Port` と同じにします。

---

<!-- _class: small -->

## 取得版と再利用条件

- Git が無い場合は Git for Windows 2.47.1.2 を取得する
- JDK 21 は実行時点の最新 GA、Jenkins は実行時点の最新 LTS を取得する
- `C:\Program Files\Git\cmd\git.exe`、`C:\jdk21` 配下の `java.exe`、`C:\jenkins.war` があれば再利用する
- `C:\git-setup.exe`、`C:\dotnet-install.ps1`、`C:\jdk21.zip` があれば再ダウンロードしない
- `<AgentWorkDir>\agent.jar` があれば再ダウンロードしない
- API トークンファイルが空でなければ、その内容を再利用する
- `agent.jar` を含む `java.exe` が動作中なら、起動バッチを書き直さず、エージェントも追加起動しない

既存ファイルの版、内容、ハッシュ、有効性は検証しません。

---

<!-- _class: small -->

## 既存ガイドとの違い

`docs/CISetup-CI-Guide.marp.md` の MSI 手順とは別の構成です。

| 項目 | この手順 |
|---|---|
| Java | JDK 21 |
| Jenkins | MSI ではなく WAR を直接起動 |
| Windows サービス | 登録しない |
| 管理者・URL・プラグイン | スクリプトで設定 |
| エージェント | 同一 PC の場合はスクリプトで作成 |

スクリプト実行後は、CISetup の「Jenkins サーバーを初期設定」を実行しないでください。

---

<!-- _class: lead -->

# 2. サーバーで実行する

---

## 管理者 PowerShell を開く

1. コンソールまたは RDP で Jenkins サーバーへログオンする
2. PowerShell を「管理者として実行」する
3. リポジトリルートへ移動する
4. スクリプトの存在を確認する

```powershell
Set-Location "D:\path\to\ci-setup-tool"
Test-Path ".\tools\Setup-JenkinsServer.ps1"
```

`True` が表示されることを確認します。

---

## 本番向け実行コマンド

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin' `
  -AdminPassword '<本番用の管理者パスワード>'
```

パスワードは ASCII 文字だけを使い、前後に空白を入れず、`$` を含めないでください。認証ヘッダーは ASCII で作られ、パスワードは Groovy の文字列へ埋め込まれます。

---

<!-- _class: small -->

## パラメーター

| パラメーター | 既定値 | 用途 |
|---|---|---|
| `-JenkinsUrl` | 空 | 空なら `http://localhost:<Port>/` |
| `-Port` | `8080` | Jenkins の HTTP 待受ポート |
| `-AdminUser` | `admin` | Jenkins 管理者名 |
| `-AdminPassword` | `cisetup-admin` | 新規管理者作成または既存 Jenkins へのログイン |
| `-JenkinsHome` | `C:\jenkins` | `JENKINS_HOME` と設定ファイル |
| `-AgentName` | `windows-agent` | 作成するノード名 |
| `-AgentWorkDir` | `C:\Jenkins\workspace` | agent.jar と作業領域 |
| `-SkipAgent` | オフ | .NET SDK 8 と同一 PC エージェント設定を省略 |

既定値では、`C:\Jenkins\workspace` は `C:\jenkins` の配下です。

---

## パスワードの扱い

`-AdminPassword` を省略した場合:

1. `<JenkinsHome>\cisetup-admin-password.txt` があれば、その内容を使う
2. ファイルがなければ、`cisetup-admin` を使う

新規 Jenkins では、初回起動時に管理者を作成し、パスワードファイルへ保存します。

既存 Jenkins の管理者パスワードは変更しません。既存 Jenkins へ接続する場合は、その管理者の現在のパスワードを指定します。

本番の初回実行では、`-AdminPassword` を明示してください。

---

<!-- _class: small -->

## 保存を伴うパラメーター

| パラメーター | 動作 |
|---|---|
| `-ProjectPath` | `<ProjectPath>\CISetup\cisetup.secrets.local.json` を上書き |
| `-FileShare` | `-ProjectPath` もある場合、指定値を含む `cisetup.local.json` を上書き |
| `-CISetupExe` | 完了表示後に指定した exe を起動 |

`-ProjectPath` で書く接続情報では、Git 資格情報と Teams Webhook が空になります。設定済みのプロジェクトには指定しません。

`-CISetupExe` と `-ProjectPath` を併用すると、`--open <ProjectPath>` を付けて起動します。

存在しない `-ProjectPath` を指定すると、Jenkins 設定後、完了表示の前に停止します。

---

<!-- _class: small -->

## スクリプトが行うこと（起動前）

1. Git を確認し、無ければ 2.47.1.2 をインストール
2. 同一 PC 構成では、`C:\dotnet\dotnet.exe` が無ければ .NET SDK 8 を導入
3. `C:\jdk21` に `java.exe` が無ければ、フォルダを消して JDK 21 を展開
4. JDK 21 と、必要時は .NET SDK 8 をマシン PATH の先頭へ追加
5. Jenkins LTS WAR を `C:\jenkins.war` に配置
6. 初期設定用 Groovy と起動バッチを作成
7. HTTP ポートと、同一 PC 構成では TCP 50000 の受信規則を追加

---

<!-- _class: small -->

## スクリプトが行うこと（起動後）

1. Jenkins が動いていなければ WAR を起動
2. 起動時の Groovy で管理者、Jenkins URL、TCP 50000 を設定
3. CISetup 用プラグインを導入し、必要なら Jenkins を再起動
4. 同一 PC 構成ではノードを登録し、エージェントを起動
5. API トークンファイルが無いか空ならトークンを発行
6. 指定があれば CISetup 設定ファイルを書き、CISetup を起動

既に Jenkins が動いている場合、新しく書いた Groovy はその場では適用されません。プラグイン導入後に再起動が発生した場合は、再起動時に適用されます。

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`

実行中に `OK: all plugins already installed (...)` または `INSTALLED: ...` が表示されます。

`INSTALLED:` に6個すべてが並ぶとは限りません。不足が疑われる場合は Jenkins の Plugins 画面で確認します。

---

<!-- _class: small -->

## ファイアウォール規則

| 表示名 | ポート | 作成条件 |
|---|---:|---|
| `CISetup Jenkins HTTP` | `-Port` の値 | 常に作成を試行 |
| `CISetup Jenkins Agent` | 50000 | `-SkipAgent` を指定しない場合 |

同じ表示名の規則が既にある場合、ポートが異なっていても作り直しません。

出力の途中、Jenkins 起動前に次の表示があった場合は、接続テスト前に規則を確認します。

```text
ファイアウォール規則を追加できませんでした: <規則名>
```

---

## 完了表示を確認する

`==> 完了` の後に、次の値が表示されます。

- Jenkins URL
- ユーザー、パスワード、API Token
- 起動スクリプト
- 同一 PC 構成では、エージェント名と作業フォルダ

最後の行まで確認し、Jenkins とエージェントのウィンドウを閉じないでください。

`-CISetupExe` の指定に誤りがある場合は、完了表示の後にエラーになります。

---

<!-- _class: small -->

## 作成されるファイルと秘密情報

| パス | 内容 | 秘密情報 |
|---|---|---|
| `<JenkinsHome>\start-jenkins.bat` | Jenkins 起動 | なし |
| `<JenkinsHome>\init.groovy.d\01-cisetup-bootstrap.groovy` | 初期設定 | 管理者パスワード |
| `<JenkinsHome>\cisetup-admin-password.txt` | 新規管理者のパスワード | あり |
| `<JenkinsHome>\cisetup-api-token.txt` | API トークン | あり |
| `<AgentWorkDir>\agent.jar` | 同一 PC 用エージェント | なし |
| `<AgentWorkDir>\start-agent.bat` | エージェント起動 | secret |
| `<ProjectPath>\CISetup\cisetup.secrets.local.json` | Jenkins 接続情報 | あり |

完了表示とコマンドラインにも秘密情報が出ます。画面共有、PowerShell の履歴、各フォルダのアクセス権を保護します。

---

<!-- _class: lead -->

# 3. CISetup で接続を確認する

---

## CISetup に入力する

設定用 PC で CISetup を開き、スクリプトの完了表示を転記します。

| CISetup の項目 | 入力値 |
|---|---|
| Jenkins URL | 完了表示の `Jenkins URL` |
| ユーザー名 | 完了表示の `ユーザー` |
| API Token | 完了表示の `API Token` |
| リポジトリ URL | 対象プロジェクトの Git URL |

API トークンは `<JenkinsHome>\cisetup-api-token.txt` でも確認できます。

Git の資格情報と Teams Webhook は、接続テストでは空のまま実行できます。

---

## 環境スキャンの扱い

環境スキャンでは、Git、.NET SDK 8、Java 21 の検出結果を確認します。

この手順は WAR を直接起動し、Jenkins の Windows サービスを作成しません。Jenkins の Windows サービスが未検出でも、追加の MSI 導入へ進まないでください。

環境スキャンの表示だけで判断せず、接続テストの結果を確認します。

---

## 接続テスト

1. Jenkins URL、ユーザー名、API Token を入力する
2. リポジトリ URL に対象プロジェクトの Git URL を入力する
3. 「接続テスト」を実行する
4. 次のメッセージを確認する

> Jenkins への接続に成功しました。

---

## 同一 PC のエージェントを確認する

`-SkipAgent` を指定しなかった場合だけ確認します。

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `<AgentName>`（既定 `windows-agent`）がオンラインであることを確認する

スクリプトはエージェントがオンラインになるのを待たずに完了します。

---

## エージェントがオフラインの場合

- エージェントのコマンドウィンドウが開いているか確認する
- Jenkins サーバーから `-JenkinsUrl` へ到達できるか確認する
- Jenkins のエージェント用 TCP ポートが 50000 になっているか確認する
- 受信規則 `CISetup Jenkins Agent` が TCP 50000 を許可しているか確認する
- Jenkins の応答後、別のウィンドウで `<AgentWorkDir>\start-agent.bat` を実行する

---

<!-- _class: lead -->

# 4. うまくいかないとき・再実行

---

## 接続テストが成功しない場合

1. Jenkins サーバーで `http://localhost:<Port>/login` の応答を確認する
2. 設定用 PC から `-JenkinsUrl` をブラウザで開く
3. URL のホスト名、ポート、パスを確認する
4. ユーザー名と API トークンを転記し直す
5. `<JenkinsHome>\cisetup-api-token.txt` の内容を確認する

トークンを作り直す場合は、トークンファイルを削除してからスクリプトを再実行します。再実行前に Jenkins とエージェントのウィンドウを閉じます。

---

<!-- _class: small -->

## 途中で止まった場合

スクリプトは最初のエラーで停止します。表示されたエラーを解消してから、同じコマンドを再実行します。

| 表示または処理 | 対処 |
|---|---|
| `管理者として実行してください。` | 管理者 PowerShell で再実行 |
| `Git のインストール後も ... が見つかりません。` | `C:\git-setup.exe` を削除し、再取得 |
| `.NET SDK の展開後も ...` | `C:\dotnet-install.ps1` と不完全な `C:\dotnet` を確認 |
| `JDK 21 の java.exe が見つかりません。` | `C:\jdk21.zip` を削除し、再取得 |
| Jenkins WAR の取得失敗または破損 | `C:\jenkins.war` を削除し、再取得 |
| `エージェントの secret を取得できませんでした。` | Jenkins のノードと管理者認証を確認 |

ダウンロード済みファイルは内容を検証せず再利用するため、取得失敗が疑われるファイルを削除してから再実行します。

---

<!-- _class: small -->

## Jenkins の応答・ログインで止まる場合

| 表示または症状 | 確認すること |
|---|---|
| `Jenkins が 8 分以内に ... で応答しませんでした。` | HTTP ポート競合、Jenkins のウィンドウ |
| `Jenkins へのログインに失敗しました。` | `-AdminUser` と `-AdminPassword` |
| 既存 Jenkins でログイン失敗 | 既存管理者の現在のパスワードを明示 |
| 設定用 PC からだけ接続不可 | 名前解決、`CISetup Jenkins HTTP`、`-JenkinsUrl` |
| API Token がトークンに見えない | トークンファイルを削除して再実行 |

パスワードファイルがある状態で `-AdminPassword` を省略すると、そのファイルの内容を使います。

---

<!-- _class: small -->

## URL またはポートを変えて再実行する

1. Jenkins とエージェントのウィンドウを閉じる
2. HTTP ポートを変える場合は、受信規則を削除するか、新しいポートへ変更する
3. パラメーターを変更してスクリプトを再実行する
4. Jenkins の応答後に接続テストをやり直す

規則を削除してスクリプトに作り直させる例:

```powershell
Remove-NetFirewallRule -DisplayName 'CISetup Jenkins HTTP'
```

初期設定用 Groovy は残るため、Jenkins 起動時にファイル内の URL が設定されます。

---

## 再起動・ログオフ後

Jenkins とエージェントは Windows サービスではありません。実行中のウィンドウを閉じた場合、ログオフした場合、サーバーを再起動した場合は停止します。

1. 管理者 PowerShell で `<JenkinsHome>\start-jenkins.bat` を実行する
2. `http://localhost:<Port>/login` の応答を確認する
3. 同一 PC 構成では、別のウィンドウで `<AgentWorkDir>\start-agent.bat` を実行する

常時稼働に必要なサービス化や自動起動は、別途設計します。

---

<!-- _class: small -->

## 別 PC エージェントを採用する場合

構成と接続方式を決めた後、Jenkins サーバーでは `-SkipAgent` を指定します。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin' `
  -AdminPassword '<本番用の管理者パスワード>' `
  -SkipAgent
```

この指定では .NET SDK 8、ノード登録、agent.jar、TCP 50000 の受信規則を用意しません。Jenkins の待受ポート 50000 は設定します。

---

<!-- _class: lead -->

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

同一 PC 構成では、`<AgentName>`（既定 `windows-agent`）のオンライン状態も確認します。

次は、対象プロジェクトの設定を行い、CI ジョブを作成します。
