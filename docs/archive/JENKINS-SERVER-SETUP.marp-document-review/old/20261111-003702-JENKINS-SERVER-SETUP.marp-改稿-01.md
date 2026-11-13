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
検証日: 2026-11-10（Windows Sandbox）

---

## この資料の範囲

| この資料で行うこと | この資料では行わないこと |
|---|---|
| Git、JDK 21、.NET SDK 8、Jenkins LTS の配置 | プロジェクトごとの Git URL 設定 |
| Jenkins 管理者、API トークン、プラグインの準備 | Teams Webhook の作成 |
| Jenkins URL、HTTP ポート、エージェントの設定 | CI ジョブの作成とテストビルド |
| CISetup からの接続テスト | Jenkins とエージェントのサービス化 |

サンドボックスは手作業の確認に使用した環境です。  
スクリプトの実行場所は、本番の Jenkins サーバーです。

---

## 完了条件

設定用 PC の CISetup で、次のメッセージが表示されれば完了です。

> Jenkins への接続に成功しました。

スクリプトは API トークンを発行しますが、CISetup の接続テストは実行しません。  
接続テストは、スクリプト完了後に設定用 PC で実行します。

同一 PC に作成する `windows-agent` のオンライン状態も、スクリプトは確認しません。  
エージェントが必要な構成では、Jenkins の Nodes 画面で別途確認します。

---

## 構成

```text
設定用 PC（CISetup）
    │  http://<Jenkins サーバー>:8080/
    ▼
Jenkins サーバー
    ├─ Jenkins LTS
    └─ windows-agent（-SkipAgent を付けない場合）
         ├─ Git
         ├─ .NET SDK 8
         └─ JDK 21
```

ビルドエージェントを別 PC にする場合は、`-SkipAgent` を指定します。  
この場合、スクリプトは .NET SDK 8 とエージェントを設定しません。

---

<!-- _class: lead -->

# 1. 実行前に確認する

---

## 実行条件

- Jenkins サーバーへ管理者権限でログオンできる
- リポジトリ一式が Jenkins サーバー上にあり、リポジトリルートを開ける
- 配布元へ HTTPS で接続できる
  - Git for Windows: `github.com`
  - .NET: `dot.net`
  - JDK 21: `api.adoptium.net`
  - Jenkins LTS: `get.jenkins.io`
- CISetup を実行する PC から、指定する Jenkins URL に到達できる
- 使用する HTTP ポートが、ほかのプロセスと競合していない

既存ファイルがある場合、ダウンロード済みとして再利用します。  
スクリプトは既存ファイルの版や内容を検証しません。

---

## URL とポートを決める

直接 HTTP で公開する場合の例:

| 項目 | 例 | 用途 |
|---|---|---|
| `-JenkinsUrl` | `http://ci-server:8080/` | CISetup、Jenkins の設定、エージェント接続 |
| `-Port` | `8080` | Jenkins のローカル待受、ファイアウォール規則 |

`-JenkinsUrl` を省略すると、実効値は `http://localhost:<Port>/` です。  
設定用 PC が別 PC の場合、`localhost` では接続できないため、ホスト名または IP アドレスを指定します。

スクリプトは `-JenkinsUrl` からの外部接続を確認しません。  
リバースプロキシなどを使う場合は、外部 URL とローカル待受ポートの対応を別途確認します。

---

<!-- _class: lead -->

# 2. サーバーで実行する

---

## 管理者 PowerShell を開く

1. PowerShell を「管理者として実行」する
2. リポジトリルートへ移動する
3. スクリプトが存在することを確認する

```powershell
Set-Location "D:\path\to\ci-setup-tool"
Test-Path ".\tools\Setup-JenkinsServer.ps1"
```

`True` が表示されることを確認してから実行します。

管理者権限がない場合、スクリプトは処理を開始せず、  
「管理者として実行してください」と表示して終了します。

---

## 基本コマンド

Jenkins サーバーとビルドエージェントを同じ PC に作成します。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl http://ci-server:8080/ `
  -Port 8080
```

既定の Jenkins 管理者は `admin`、新規作成時の既定パスワードは  
`cisetup-admin` です。パスワードは本番用の値を明示指定します。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl http://ci-server:8080/ `
  -Port 8080 `
  -AdminUser "admin" `
  -AdminPassword "<管理者パスワード>"
```

---

## エージェントを別 PC にする場合

Jenkins サーバーでは `-SkipAgent` を指定します。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl http://ci-server:8080/ `
  -Port 8080 `
  -AdminPassword "<管理者パスワード>" `
  -SkipAgent
```

この指定でも、Git、JDK 21、Jenkins は Jenkins サーバーへ配置されます。  
.NET SDK 8、エージェント登録、TCP 50000 のファイアウォール規則は省略されます。

別 PC のエージェント構築は、このスクリプトの対象外です。

---

<!-- _class: small -->

## パラメーター

| パラメーター | 既定値 | スクリプトでの用途 |
|---|---|---|
| `-JenkinsUrl` | 空 | 空なら `http://localhost:<Port>/`。Jenkins URL とエージェント接続先 |
| `-Port` | `8080` | Jenkins の HTTP 待受ポート |
| `-AdminUser` | `admin` | Jenkins 管理者名 |
| `-AdminPassword` | `cisetup-admin` | 新規管理者作成または既存 Jenkins へのログイン |
| `-JenkinsHome` | `C:\jenkins` | `JENKINS_HOME` と設定ファイルの保存先 |
| `-AgentName` | `windows-agent` | 作成するノード名 |
| `-AgentWorkDir` | `C:\Jenkins\workspace` | agent.jar とエージェント作業領域 |
| `-SkipAgent` | オフ | .NET SDK 8 とエージェント設定を省略 |

---

<!-- _class: small -->

## 保存を伴うパラメーター

| パラメーター | 動作 |
|---|---|
| `-ProjectPath` | `<ProjectPath>\CISetup\cisetup.secrets.local.json` を作成 |
| `-FileShare` | `-ProjectPath` も指定した場合、`cisetup.local.json` へ保存 |
| `-CISetupExe` | 最後に指定した exe を起動 |

`-ProjectPath` が存在しない場合、処理の終盤でエラーになります。  
`-CISetupExe` が存在しない場合も、Jenkins の設定後にエラーになります。

`-ProjectPath` を指定した場合、接続情報には Jenkins URL、ユーザー名、  
API トークンが平文で保存されます。Git と Teams の値は空で作成されます。

---

## スクリプトが行うこと

1. Git for Windows 2.47.1 を確認し、なければインストール
2. `-SkipAgent` がなければ .NET SDK 8 を `C:\dotnet` へ配置
3. 最新の Temurin JDK 21 を `C:\jdk21` へ展開
4. 最新の Jenkins LTS WAR を `C:\jenkins.war` へ配置
5. セットアップウィザードを無効にして Jenkins を起動
6. 管理者、Jenkins URL、エージェント待受ポート 50000 を設定
7. HTTP ポートと、必要な場合は TCP 50000 の受信規則を追加
8. CISetup 用プラグインを導入
9. 必要な場合はエージェントを登録して起動
10. API トークンを発行してファイルへ保存

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`

再起動が必要と Jenkins が返した場合、スクリプトは Jenkins を再起動します。

更新サイトに対象プラグインが見つからない場合でも、スクリプトは  
6 個すべてが導入されたかを最後に再確認しません。

処理後に Jenkins の Plugins 画面で確認するか、CISetup の後続処理で  
プラグイン不足が示された場合は不足分を確認します。

---

## 完了表示を確認する

最後に次の値が表示されます。

```text
Jenkins URL
ユーザー
パスワード
API Token
エージェント名、作業フォルダ
起動スクリプト
```

途中で赤いエラーが表示されず、`==> 完了` まで進んだことを確認します。

ファイアウォール規則の追加に失敗した場合だけは、警告を表示して処理を続けます。  
その警告がある場合、設定用 PC からの接続前に受信規則を確認します。

---

## 作成される主なファイル

| パス | 内容 |
|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動スクリプト |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 初期設定 |
| `C:\jenkins\cisetup-api-token.txt` | API トークン |
| `C:\jenkins\cisetup-admin-password.txt` | 新規管理者を作成した場合のパスワード |
| `C:\Jenkins\workspace\agent.jar` | 同一 PC 用エージェント |
| `C:\Jenkins\workspace\start-agent.bat` | 同一 PC 用エージェント起動スクリプト |

パスは `-JenkinsHome` と `-AgentWorkDir` の指定で変わります。  
認証情報とエージェント secret が平文で残るため、アクセス権を制限します。

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

API トークンは、Jenkins サーバーの  
`<JenkinsHome>\cisetup-api-token.txt` でも確認できます。

リポジトリ URL、Git 資格情報、Teams Webhook は、接続テストだけであれば  
このスクリプトが設定する対象ではありません。

---

## 接続テスト

1. CISetup で Jenkins URL、ユーザー名、API Token を入力する
2. 「接続テスト」を実行する
3. 次のメッセージを確認する

> Jenkins への接続に成功しました。

成功しない場合は、次の順に切り分けます。

1. Jenkins サーバー上で `http://localhost:<Port>/login` が応答するか
2. 設定用 PC から `-JenkinsUrl` をブラウザで開けるか
3. URL のホスト名、ポート、末尾のパスが正しいか
4. ユーザー名と API トークンを転記し直したか

---

## 同一 PC のエージェントを確認する

`-SkipAgent` を指定しなかった場合だけ確認します。

1. Jenkins を開く
2. **Manage Jenkins → Nodes** を開く
3. `windows-agent` がオンラインであることを確認する

オフラインの場合:

- エージェントのコマンドウィンドウが開いているか確認する
- `C:\Jenkins\workspace\start-agent.bat` を実行する
- Jenkins URL へ Jenkins サーバー自身から到達できるか確認する
- TCP 50000 の受信規則を確認する

スクリプトはエージェントのオンライン到達を待たずに完了します。

---

## Jenkins が応答しない場合

| 表示または症状 | 確認すること |
|---|---|
| `Jenkins が 8 分以内に ... で応答しませんでした` | HTTP ポート競合、Jenkins の起動ウィンドウ |
| `Jenkins へのログインに失敗しました` | `-AdminUser` と `-AdminPassword` |
| 既存 Jenkins でログイン失敗 | 既存管理者のパスワードを明示して再実行 |
| 設定用 PC からだけ接続不可 | 名前解決、受信規則、`-JenkinsUrl` |
| `API Token` の処理で停止 | Jenkins のユーザーと Script Console 呼び出し結果 |

既存 Jenkins のパスワードファイルが `<JenkinsHome>` にあり、  
`-AdminPassword` を省略した場合は、そのファイルの値が使用されます。

---

## 再起動・ログオフ後

Jenkins とエージェントは Windows サービスとして登録されません。  
開いているプロセスを停止した場合やサーバー再起動後は、次を実行します。

```text
C:\jenkins\start-jenkins.bat
C:\Jenkins\workspace\start-agent.bat
```

`-SkipAgent` を指定した場合は Jenkins だけを起動します。  
パスを変更した場合は、それぞれ `-JenkinsHome`、`-AgentWorkDir` 配下です。

常時稼働に必要なサービス化や自動起動の設定は、  
このスクリプトでは行いません。

---

## 実装上の留意点

- Git は 2.47.1 に固定されています
- JDK 21 と Jenkins LTS は実行時点の最新を取得します
- `C:\git-setup.exe`、`C:\jdk21.zip`、`C:\jenkins.war` などが既にあれば再利用します
- Jenkins のローカル操作は `http://localhost:<Port>/` に対して行います
- Jenkins とエージェントを Windows サービスへ登録しません
- API トークン、管理者パスワード、エージェント secret を平文で保存します
- Jenkins URL への外部接続と CISetup の接続テストは確認しません
- エージェントがオンラインになったことは確認しません

本番サーバーでのスクリプト実行結果は、検証環境では未確認です。

---

<!-- _class: lead -->

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。
