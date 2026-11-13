---
marp: true
theme: default
paginate: true
size: 16:9
title: Jenkins サーバー セットアップ手順
description: 未導入の Windows サーバーを、CISetup から接続できる状態にする手順
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
## 初回セットアップ手順

未導入の Windows サーバーで  
`tools/Setup-JenkinsServer.ps1` を実行し、  
CISetup の接続テスト成功まで進める

---

<!-- _class: small -->

## 対象

次のソフトウェアとファイルがない Windows サーバーを対象とします。

- Jenkins
- Git for Windows（`C:\Program Files\Git`）
- JDK（`C:\jdk21`）
- .NET SDK（`C:\dotnet`）
- `C:\jenkins`、`C:\jenkins.war`

Jenkins と `windows-agent` は同じサーバーで動かします。スクリプトは .NET SDK 8 もこのサーバーへ導入します。

既存 Jenkins からの移行、別 PC エージェントの構築、`-SkipAgent`、`-ProjectPath`、`-FileShare`、`-CISetupExe` の使用方法は扱いません。

---

## この手順で行うこと

| 行うこと | 行わないこと |
|---|---|
| Git、JDK 21、.NET SDK 8 の導入 | プロジェクト用 CI ジョブの作成 |
| Jenkins LTS の配置と起動 | Git や Teams の設定 |
| 管理者、プラグイン、API Token の準備 | テストビルド |
| 同一サーバー上のエージェント作成 | Windows サービス化 |
| CISetup からの接続テスト | サーバー起動時の自動起動設定 |

---

## 完了条件

設定用 PC の CISetup で、次のメッセージが表示されること。

> Jenkins への接続に成功しました。

あわせて、次の2点を確認します。

- スクリプトの出力に `OK: plugins active (...)` があり、6個のプラグイン ID が並んでいる
- Jenkins の Nodes 画面で `windows-agent` がオンラインになっている

---

## 構成

```text
設定用 PC（CISetup）
    │  http://<Jenkinsサーバー>:8080/
    ▼
Jenkins サーバー（未導入の Windows）
    ├─ Jenkins LTS（WAR、組み込みノードの実行数 0）
    ├─ JDK 21
    ├─ Git for Windows
    ├─ .NET SDK 8
    └─ windows-agent（WebSocket、ラベルなし）
```

Jenkins とエージェントは Windows サービスではなく、それぞれ別ウィンドウで動きます。

---

<!-- _class: lead -->

# 1. 実行前の準備

---

<!-- _class: small -->

## 用意するもの

| 項目 | 内容 |
|---|---|
| リポジトリ一式 | Jenkins サーバー上へ配置する |
| Jenkins URL | 設定用 PC から開ける URL。例: `http://ci-server:8080/` |
| 管理者ユーザー名 | 既定値は `admin` |
| 管理者パスワード | `-AdminPassword` で指定する |

`-AdminPassword` を省略した場合は `cisetup-admin` になります。本番環境では明示的に指定してください。

認証処理が ASCII を前提としているため、管理者パスワードには ASCII 文字を使用します。先頭と末尾には空白を入れません。PowerShell のコマンドでは、値を単一引用符で囲みます。

---

## 実行条件

コンソールまたは RDP でサーバーへログオンし、そのデスクトップで管理者 PowerShell を開きます。

- TCP 8080 と TCP 50000 がほかの用途で使われていない
- Jenkins サーバー自身から、指定する Jenkins URL へ到達できる
- 設定用 PC から、その Jenkins URL へ到達できる
- 配布元と Jenkins 更新サイトへ HTTPS で接続できる

スクリプトはプロキシを設定しません。プロキシが必要な環境では、PowerShell と Jenkins の外部通信経路を事前に用意します。

---

## 初回実行時の外部通信

- Git for Windows: `github.com`
- .NET インストールスクリプト: `dot.net`
- JDK 21: `api.adoptium.net`
- Jenkins LTS: `get.jenkins.io`
- Jenkins プラグイン: Jenkins 更新サイト

.NET SDK 本体や各配布物は、別のホストへリダイレクトされる場合があります。許可リスト方式の環境では、実際の通信先を事前に確認してください。

---

<!-- _class: small -->

## 導入される版と方式

| 対象 | 導入内容 |
|---|---|
| Git | Git for Windows 2.47.1.2 |
| .NET | .NET SDK 8.0 チャネル |
| Java | Adoptium JDK 21 の最新 GA |
| Jenkins | Jenkins LTS の最新 WAR |
| Jenkins の起動 | `java -jar`。セットアップウィザードは無効 |
| エージェント | 同一サーバーから WebSocket 接続 |

この手順では MSI 版 Jenkins を導入しません。CISetup 内の「Jenkins サーバー初回設定」も使用しません。

---

<!-- _class: lead -->

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

<!-- _class: small -->

## スクリプトの処理

1. Git for Windows 2.47.1.2 を導入する
2. .NET SDK 8 を `C:\dotnet` へ導入する
3. JDK 21 を `C:\jdk21` へ展開する
4. JDK と .NET SDK のパスをマシン PATH の先頭へ追加する
5. Jenkins LTS WAR を `C:\jenkins.war` へ配置する
6. 初期設定用 Groovy と `start-jenkins.bat` を作成する
7. Windows ファイアウォールの受信規則を追加する
8. Jenkins を起動し、管理者と基本設定を作成する
9. 必要なプラグインを導入して、有効化を確認する
10. `windows-agent` を登録、起動して、オンラインを確認する
11. `cisetup` という名前の API Token を発行する

---

## 待ち時間

| 処理 | 上限 |
|---|---:|
| Jenkins の初回応答待ち | 8分 |
| プラグイン反映後の再起動待ち | 8分 |
| Groovy 呼び出し1回 | 10分 |
| エージェントのオンライン待ち | 3分 |

上限を超えるとスクリプトは停止します。Jenkins とエージェントのウィンドウは閉じないでください。

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`

導入後、スクリプトは次の形式の行を出力します。

```text
OK: plugins active (workflow-aggregator, git, credentials-binding, plain-credentials, parameterized-trigger, naginator)
```

この行が出ない場合は、プラグインの準備が完了していません。

---

<!-- _class: small -->

## ファイアウォール規則

| 表示名 | ポート |
|---|---:|
| `CISetup Jenkins HTTP` | `-Port` の値 |
| `CISetup Jenkins Agent` | 50000 |

規則の追加に失敗しても、その時点では処理が続きます。完了時にも失敗した規則名が表示されます。

設定用 PC から Jenkins URL を開けない場合は、`CISetup Jenkins HTTP`、`-Port` の値、サーバー名の名前解決を確認します。

---

## 完了表示

`==> 完了` の後に、次の情報が表示されます。

- Jenkins URL
- ユーザー
- パスワード
- API Token
- プラグインの確認結果
- エージェント名
- エージェントの作業フォルダ
- Jenkins の起動スクリプト

CISetup へ入力するのは、Jenkins URL、ユーザー、API Token の3項目です。

---

<!-- _class: small -->

## 作成される主なファイル

| パス | 内容 | 秘密情報 |
|---|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動 | なし |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者と Jenkins 基本設定 | パスワード |
| `C:\jenkins\cisetup-admin-password.txt` | 管理者パスワード | あり |
| `C:\jenkins\cisetup-api-token.txt` | API Token | あり |
| `C:\Jenkins\workspace\agent.jar` | エージェント本体 | なし |
| `C:\Jenkins\workspace\start-agent.bat` | エージェント起動 | secret |

`C:\jenkins` と `C:\Jenkins\workspace` は、サーバーの運用方針に従ってアクセスを制限してください。

---

## 管理者設定の注意

管理者アカウントは、Jenkins のセキュリティ設定が未作成のときだけ作られます。

- パスワードを変えて再実行しても、既存アカウントのパスワードは変わらない
- `-AdminPassword` を省略し、パスワードファイルがあれば、その保存値を使用する
- 初期設定用 Groovy は残り、Jenkins 起動時に URL、待受ポート、組み込みノードの実行数を設定する

完了表示、PowerShell のコマンド履歴、Groovy、パスワードファイル、エージェント起動ファイルには秘密情報が含まれます。

---

<!-- _class: lead -->

# 3. CISetup で接続を確認する

---

## CISetup へ入力する

設定用 PC で CISetup を開き、「⑤ Jenkins への接続」へ入力します。

| CISetup の項目 | 入力値 |
|---|---|
| Jenkins URL | 完了表示の `Jenkins URL` |
| ユーザー名 | 完了表示の `ユーザー` |
| API Token | 完了表示の `API Token` |

API Token は `C:\jenkins\cisetup-api-token.txt` でも確認できます。

Git リポジトリ URL、Git の資格情報、Teams Webhook は、この接続テストには不要です。

---

## 接続テスト

1. スクリプトの `OK: plugins active` に6個の ID があることを確認する
2. Jenkins URL、ユーザー名、API Token を入力する
3. 「接続テスト」を押す
4. 次のメッセージを確認する

> Jenkins への接続に成功しました。

このメッセージは、CISetup が入力された接続情報で Jenkins への接続に成功したときに表示されます。

---

## エージェントラベル

CISetup のエージェントラベルは空欄にします。

- `windows-agent` はラベルなしで作成される
- Jenkins の組み込みノードは実行数 0 に設定される
- CISetup はラベルが空欄の場合、Jenkinsfile に `agent any` を生成する

この構成では、オンラインの `windows-agent` がビルドの実行先になります。

---

## エージェントを確認する

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `windows-agent` がオンラインであることを確認する

スクリプトはエージェントがオンラインになるまで最大3分待ちます。オンラインにならなければ、処理は完了表示の前に停止します。

---

<!-- _class: lead -->

# 4. 初回実行が止まったとき

---

## 再実行の前に

スクリプトが停止したら、表示されたエラーを確認します。再実行の前に、起動済みの Jenkins とエージェントのウィンドウを閉じてください。

次の表示は、その場では停止しません。

```text
ファイアウォール規則を追加できませんでした: <規則名>
crumb は取得しませんでした。そのまま Script Console を呼びます。
```

後続処理が成功したかどうかは、最終的な完了表示で判断します。

---

<!-- _class: small -->

## 主なエラーと対処

| 表示 | 対処 |
|---|---|
| `管理者として実行してください。` | 管理者 PowerShell で再実行 |
| `Git のインストール後も ... が見つかりません。` | `C:\git-setup.exe` を削除して再実行 |
| `.NET SDK の展開後も ...` | `C:\dotnet-install.ps1` と `C:\dotnet` を削除して再実行 |
| `JDK 21 の展開に失敗しました` | `C:\jdk21.zip` を削除して再実行 |
| `Jenkins が 8 分以内に ... 応答しませんでした。` | Jenkins ウィンドウを確認。必要に応じて `start-jenkins.bat` を実行 |
| `Jenkins へのログインに失敗しました。` | 初回指定のパスワードを確認 |
| `プラグインの導入に失敗しました` | Jenkins 更新サイトへの通信を確認 |
| `必要なプラグインが有効ではありません` | Jenkins の Plugins 画面で状態を確認 |
| `エージェント ... が 3 分以内にオンラインになりませんでした` | エージェントウィンドウを閉じ、`start-agent.bat` を実行 |

---

## Jenkins の起動を確認する

Jenkins のウィンドウが残っていない場合は、管理者 PowerShell から起動します。

```powershell
& 'C:\jenkins\start-jenkins.bat'
```

このバッチは Jenkins 終了後にメッセージを表示し、キー入力を待ちます。起動に失敗した理由は、そのウィンドウの表示で確認します。

---

## 接続テストが失敗したとき

1. Jenkins サーバーで `http://localhost:8080/login` を開く
2. 設定用 PC のブラウザで、完了表示の Jenkins URL を開く
3. 開けない場合は HTTP の受信規則、ポート、名前解決を確認する
4. CISetup のユーザー名と API Token を転記し直す
5. `C:\jenkins\cisetup-api-token.txt` の内容と照合する

スクリプトで `-Port` を 8080 以外にした場合は、確認 URL のポートも置き換えます。

---

## 初回状態からやり直す場合

管理者アカウントを含めて作り直す場合は、Jenkins とエージェントのウィンドウを閉じてから `C:\jenkins` を削除し、同じコマンドを再実行します。

取得物が壊れている場合は、該当ファイルを削除して再実行します。

- Jenkins WAR: `C:\jenkins.war`
- JDK: `C:\jdk21.zip`
- Git: `C:\git-setup.exe`
- .NET: `C:\dotnet-install.ps1` と `C:\dotnet`
- エージェント: `C:\Jenkins\workspace\agent.jar`

削除は、エラー表示と対象ファイルを照合してから行ってください。

---

## 再起動・ログオフ後

Jenkins とエージェントは Windows サービスではありません。ウィンドウを閉じたとき、ログオフしたとき、サーバーを再起動したときは停止します。

1. 管理者 PowerShell で `C:\jenkins\start-jenkins.bat` を実行する
2. `http://localhost:8080/login` が開くことを確認する
3. 別のウィンドウで `C:\Jenkins\workspace\start-agent.bat` を実行する
4. Jenkins の Nodes 画面で `windows-agent` のオンラインを確認する

---

<!-- _class: lead -->

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

`OK: plugins active` に6個の ID があり、  
`windows-agent` がオンラインであれば、  
初回セットアップは完了です。
