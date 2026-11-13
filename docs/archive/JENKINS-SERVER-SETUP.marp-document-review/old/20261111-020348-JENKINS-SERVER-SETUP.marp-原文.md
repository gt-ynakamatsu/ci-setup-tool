---
marp: true
theme: default
paginate: true
size: 16:9
title: Jenkins サーバー セットアップ手順
description: 何も入っていない Windows サーバーへ、CISetup から接続できる状態まで入れる手順
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

何も入っていない Windows サーバーで  
`tools/Setup-JenkinsServer.ps1` を実行し、  
CISetup の接続テスト成功まで進める

---

<!-- _class: small -->

## 前提

対象は、次が入っていない Windows サーバーです。

- Jenkins（MSI、サービス、WAR のいずれも）
- Git for Windows（`C:\Program Files\Git`）
- JDK（`C:\jdk21`）
- .NET SDK（`C:\dotnet`）
- `C:\jenkins`、`C:\jenkins.war`

エージェントは、このサーバーと同一 PC の `windows-agent` です。ビルドに使う .NET SDK 8 も、このサーバーへ入ります。

次はこの手順では使いません。

- 既に Jenkins、Git、JDK、.NET が入っているサーバー
- 別 PC のエージェント、`-SkipAgent`
- `-ProjectPath`、`-FileShare`、`-CISetupExe`

接続情報は、完了表示を CISetup へ手で転記します。

---

<!-- _class: small -->

## 検証状況

2026-11-10 に Windows Sandbox で手作業の手順を確認しました。確認時の Jenkins は 2.580.2 です。

`Setup-JenkinsServer.ps1` は未実行です。管理者作成、URL 設定、プラグイン導入、ノード作成、トークン発行は、スクリプトとしては確認していません。

CISetup の接続成功時の表示は「Jenkins への接続に成功しました。」です。接続テストが使う入力は Jenkins URL、ユーザー名、API Token です。

未確認なのは、Jenkins 画面の日本語表示名、プロキシ環境、配布元のリダイレクト先、秘密情報フォルダの継承アクセス権です。

本番の前に、同じ前提の検証環境でスクリプトを一度実行するかを決めてください。

---

## この資料の範囲

| 行うこと | 行わないこと |
|---|---|
| Git、JDK 21、.NET SDK 8、Jenkins LTS の新規導入 | プロジェクトごとの CI ジョブ作成 |
| Jenkins 管理者、API トークン、プラグインの準備 | リポジトリ URL、Teams Webhook の設定 |
| 同一 PC エージェントの作成 | テストビルド |
| CISetup からの接続テスト | Windows サービス化、別 PC エージェント |

---

## 完了条件

設定用 PC の CISetup で、次のメッセージが表示されれば接続確認は完了です。

> Jenkins への接続に成功しました。

あわせて、Plugins 画面で 6 個のプラグインが有効であること、`windows-agent` がオンラインであることを確認します。作成されるノードにラベルは付きません。

スクリプトは、接続テストとエージェントのオンライン確認を行いません。

---

## 構成

```text
設定用 PC（CISetup）
    │  http://<Jenkins サーバー>:8080/
    ▼
Jenkins サーバー（未導入の Windows）
    ├─ Jenkins LTS（WAR、JDK 21）
    ├─ Git 2.47.1.2
    └─ windows-agent
         └─ .NET SDK 8
```

エージェントは、このサーバーの待受ポート TCP 50000 へ接続します。CISetup は、このサーバーでも別 PC でも開けます。

---

<!-- _class: lead -->

# 1. 実行前に確認する

---

<!-- _class: small -->

## 実行前に決めること

| 項目 | 内容 |
|---|---|
| 管理者パスワード | 本番用の値を `-AdminPassword` で指定する。省略すると `cisetup-admin` になる |
| Jenkins URL | 設定用 PC から開く URL。例: `http://ci-server:8080/` |
| 入る版 | Git は 2.47.1.2。JDK 21 は実行時点の最新 GA。Jenkins は実行時点の最新 LTS |

手作業で確認した Jenkins は 2.580.2 です。版を固定して入れる手順は、この資料にはありません。

パスワードは ASCII だけを使います。前後の空白、`$`、`'`、`"` は入れません。認証ヘッダーは ASCII で作られ、パスワードは Groovy の文字列へ埋め込まれます。

---

## 実行条件

コンソールまたは RDP でログオンし、そのデスクトップの管理者 PowerShell で実行します。WinRM などのリモート PowerShell では実行しません。

- リポジトリ一式が、このサーバー上にある
- TCP 8080 と TCP 50000 が空いている
- このサーバー自身から、指定する Jenkins URL を開ける
- 設定用 PC からも、その URL を開ける
- 配布元と Jenkins の更新サイトへ HTTPS で接続できる

プロキシが必要な環境では、PowerShell と Jenkins の通り道を先に決めてから実行します。

---

## 外部通信

初回実行で取得する先:

- Git for Windows: `github.com`
- .NET のインストールスクリプト: `dot.net`（SDK 本体は、そのスクリプトが別ホストから取得する）
- JDK 21: `api.adoptium.net`
- Jenkins LTS: `get.jenkins.io`
- プラグイン: Jenkins の更新サイト

許可リスト方式の環境では、検証環境で実通信先を確認してから本番へ適用します。

---

## 既存ガイドとの違い

`docs/CISetup-CI-Guide.marp.md` は、この手順では使いません。

| 項目 | 既存ガイド | この手順 |
|---|---|---|
| Java | Java 17 | JDK 21 |
| Jenkins | MSI | WAR を直接起動 |
| Windows サービス | 登録する | 登録しない |
| 初回設定 | Web のセットアップウィザード | スクリプト（ウィザードは出さない） |
| エージェント | CISetup の「Jenkins サーバーを初期設定」 | スクリプトが同一 PC に作る |

現行 LTS は Java 21 または 25 が必要です。検証時、Java 17 では起動しませんでした。

スクリプトの後に、CISetup の「Jenkins サーバーを初期設定」は押さないでください。検証環境では、そのノード作成（`computer/doCreateItem`）が HTTP 400 になりました。ノードはスクリプトが作ります。

---

<!-- _class: lead -->

# 2. サーバーで実行する

---

## 管理者 PowerShell を開く

1. コンソールまたは RDP でサーバーへログオンする
2. PowerShell を「管理者として実行」する
3. リポジトリルートへ移動する

```powershell
Set-Location "D:\path\to\ci-setup-tool"
Test-Path ".\tools\Setup-JenkinsServer.ps1"
```

`True` が表示されることを確認してから、次のコマンドを実行します。

---

## 実行コマンド

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin' `
  -AdminPassword '<本番用の管理者パスワード>'
```

`-JenkinsUrl` のポートは `-Port` と同じにします。設定用 PC が別 PC のときは、`localhost` ではなく、その PC から届くホスト名か IP アドレスを指定します。

Jenkins の応答待ちは最大 8 分です。プラグイン反映で再起動すると、さらに最大 8 分待ちます。プラグイン導入とノード登録の呼び出しは、1 回あたり最大 10 分です。

---

<!-- _class: small -->

## この実行で使う値

| パラメーター | この手順での値 |
|---|---|
| `-JenkinsUrl` | 設定用 PC から開く URL |
| `-Port` | `8080` |
| `-AdminUser` | `admin` |
| `-AdminPassword` | 本番用のパスワード |
| `-JenkinsHome` | 既定の `C:\jenkins` |
| `-AgentName` | 既定の `windows-agent` |
| `-AgentWorkDir` | 既定の `C:\Jenkins\workspace` |

Windows ではパスの大文字と小文字を区別しません。作業フォルダは `C:\jenkins` の配下になり、secret を含む `start-agent.bat` もそこに置かれます。アクセス権とバックアップは `C:\jenkins` を一つのツリーとして扱います。

---

<!-- _class: small -->

## スクリプトが行うこと

1. Git for Windows 2.47.1.2 をインストールする
2. .NET SDK 8 を `C:\dotnet` に入れる
3. JDK 21 を `C:\jdk21` に展開する
4. JDK 21 と .NET SDK 8 を、マシンの PATH の先頭へ追加する
5. Jenkins LTS の WAR を `C:\jenkins.war` に置く
6. 初期設定用 Groovy と `start-jenkins.bat` を作る
7. TCP 8080 と TCP 50000 の受信規則を追加する
8. ウィザードを出さずに Jenkins を起動する
9. 管理者、Jenkins URL、待受ポート 50000 を設定する
10. プラグインを導入し、必要なら Jenkins を再起動する
11. ラベルなしの `windows-agent` を登録し、エージェントを起動する
12. 名前 `cisetup` の API トークンを発行する

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`

初回は `INSTALLED:` に、今回入ったプラグインが並びます。更新サイトに見つからないものは表示されず、スクリプトも止まりません。結果の文面は表示するだけで、中身は検査しません。

完了後、Plugins 画面で 6 個すべてが有効か確認します。接続テストでは不足は分かりません。

---

<!-- _class: small -->

## ファイアウォールと完了表示

作る受信規則は次の 2 つです。追加に失敗してもスクリプトは止まりません。

| 表示名 | ポート |
|---|---:|
| `CISetup Jenkins HTTP` | 8080 |
| `CISetup Jenkins Agent` | 50000 |

起動前に `ファイアウォール規則を追加できませんでした: <規則名>` と出た場合は、接続テストの前にその規則を確認します。

`==> 完了` の後に、Jenkins URL、ユーザー、パスワード、API Token、起動スクリプト、エージェント名、作業フォルダが出ます。エージェント登録の途中では、`SECRET=` に続けて secret が出ます。

ウィンドウは閉じないでください。閉じたとき、およびログオフしたときは停止します。

---

<!-- _class: small -->

## 作成されるファイル

| パス | 内容 | 秘密情報 |
|---|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動 | なし |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者、URL、待受ポート。パスワードを平文で含む | あり |
| `C:\jenkins\cisetup-admin-password.txt` | 管理者パスワード | あり |
| `C:\jenkins\cisetup-api-token.txt` | API トークン | あり |
| `C:\Jenkins\workspace\agent.jar` | エージェント本体 | なし |
| `C:\Jenkins\workspace\start-agent.bat` | 起動コマンド。secret を含む | あり |

初期設定用 Groovy は残ります。Jenkins の画面で URL を変えても、次回起動時にファイルの値へ戻ります。

完了表示、`SECRET=`、コマンドラインにも秘密情報が出ます。画面共有を避け、PowerShell の履歴と `C:\jenkins` のアクセス権を保護します。

---

<!-- _class: lead -->

# 3. CISetup で接続を確認する

---

## CISetup に入力する

設定用 PC で CISetup を開き、完了表示を転記します。

| CISetup の項目 | 入力値 |
|---|---|
| Jenkins URL | 完了表示の `Jenkins URL` |
| ユーザー名 | 完了表示の `ユーザー` |
| API Token | 完了表示の `API Token` |

API トークンは `C:\jenkins\cisetup-api-token.txt` でも確認できます。

接続テストにリポジトリ URL は要りません。Git の資格情報と Teams Webhook も空のまま実行できます。これらは、接続確認の後に入れます。

---

## 環境スキャンの扱い

CISetup をこのサーバーで開くと、Git、.NET SDK 8、Java 21 が検出されます。

Jenkins の Windows サービスは作りません。「Jenkins サービス（この PC）」が未検出でも、MSI は入れないでください。

CISetup を別 PC で開いた場合、その PC では Git や JDK が未検出のことがあります。未検出でも、接続テストが成功すれば先へ進みます。

---

## 接続テスト

1. Plugins 画面で 6 個のプラグインが有効か確認する
2. Jenkins URL、ユーザー名、API Token を入力する
3. 「接続テスト」を実行する
4. 次のメッセージを確認する

> Jenkins への接続に成功しました。

---

<!-- _class: small -->

## エージェントを確認する

1. Jenkins を開く
2. `Manage Jenkins → Nodes`（日本語表示ではノード管理）を開く
3. `windows-agent` がオンラインであることを確認する

スクリプトは、オンラインになるのを待たずに完了します。

作成されるノードにラベルは付きません。CISetup のエージェントラベルは空欄にします。既存ガイドの例 `windows` を付けたままにすると、オンラインでもビルドが割り当てられません。

オフラインのときは、エージェントのウィンドウ、サーバーから Jenkins URL への到達、待受ポート 50000、受信規則 `CISetup Jenkins Agent` を確認します。応答を確認してから、別のウィンドウで `C:\Jenkins\workspace\start-agent.bat` を実行します。

---

<!-- _class: lead -->

# 4. 初回実行が途中で止まったとき

---

<!-- _class: small -->

## 止まったときの再実行

多くの処理は最初のエラーで止まります。再実行の前に、起動した Jenkins とエージェントのウィンドウを閉じます。

次の表示が出ても、スクリプトは止まりません。

- `ファイアウォール規則を追加できませんでした: <規則名>`
- `crumb は取得しませんでした。そのまま Script Console を呼びます。`
- プラグイン処理の結果（失敗の文面でも続行する）
- 更新サイトに無いプラグイン（表示されず、飛ばす）

初回の取得物は、同じパスにファイルがあると内容を見ずに使います。取得に失敗したファイルは削除してから、同じコマンドを再実行します。

| 削除するファイル | とき |
|---|---|
| `C:\git-setup.exe` | Git のインストール後に `git.exe` が見つからない |
| `C:\dotnet-install.ps1` と `C:\dotnet` | .NET SDK の展開後に `C:\dotnet\dotnet.exe` が見つからない |
| `C:\jdk21.zip` | JDK の展開に失敗した、または `java.exe` が見つからない |
| `C:\jenkins.war` | WAR の取得に失敗した、または壊れている |

Groovy の呼び出しは 1 回あたり最大 10 分で時間切れになります。

---

<!-- _class: small -->

## 接続できないとき

1. サーバーで `http://localhost:8080/login` が開くか確認する
2. 設定用 PC から `-JenkinsUrl` をブラウザで開く
3. ユーザー名と API Token を転記し直す
4. `C:\jenkins\cisetup-api-token.txt` と完了表示を突き合わせる

`Jenkins が 8 分以内に ... で応答しませんでした。` と出たときは、8080 番の競合と Jenkins のウィンドウを確認します。プラグイン後の再起動では、さらに最大 8 分待ちます。

`Jenkins へのログインに失敗しました。` と出たときは、実行コマンドの `-AdminUser` と `-AdminPassword` を確認して再実行します。再実行でパスワードを省略すると、初回に保存した `C:\jenkins\cisetup-admin-password.txt` を使います。

---

## 再起動・ログオフ後

Jenkins とエージェントは Windows サービスではありません。ウィンドウを閉じたとき、ログオフしたとき、サーバーを再起動したときは停止します。

1. 管理者 PowerShell で `C:\jenkins\start-jenkins.bat` を実行する
2. `http://localhost:8080/login` が開くのを確認する
3. 別のウィンドウで `C:\Jenkins\workspace\start-agent.bat` を実行する

`start-jenkins.bat` は Jenkins が終わるまで戻りません。同じウィンドウでエージェントを続けて起動しません。

サーバー起動のたびに自動で上げる仕組みは、この手順では作りません。

---

<!-- _class: lead -->

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

Plugins 画面の 6 個が有効であること、`windows-agent` がオンラインであることも確認します。エージェントラベルは空欄のままにします。

次は、対象プロジェクトの Git URL を入れて CI ジョブを作成します。
