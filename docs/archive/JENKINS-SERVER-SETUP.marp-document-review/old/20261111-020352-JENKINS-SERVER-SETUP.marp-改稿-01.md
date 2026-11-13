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

次は対象外です。

- 既に Jenkins、Git、JDK、.NET が入っているサーバー
- 既存 Jenkins からの移行
- 別 PC のエージェント、`-SkipAgent`
- `-ProjectPath`、`-FileShare`、`-CISetupExe`

接続情報は、完了表示を CISetup へ手で転記します。

---

<!-- _class: small -->

## 検証状況

2026-11-10 に Windows Sandbox で手作業の手順を確認しました。確認時の Jenkins は 2.580.2 です。

`Setup-JenkinsServer.ps1` 自体は未実行です。管理者作成、URL 設定、プラグイン導入、ノード作成、トークン発行は、実機での一連動作を確認していません。

CISetup の実装上、接続成功時の表示は「Jenkins への接続に成功しました。」です。接続テストが使う入力は Jenkins URL、ユーザー名、API Token です。

Jenkins 画面の日本語表示名、プロキシ環境、配布元のリダイレクト先、秘密情報を置くフォルダの継承アクセス権は未確認です。

本番へ適用する前に、同じ前提の検証環境でスクリプトを一度実行するか判断してください。

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

設定用 PC の CISetup で、次のメッセージが表示されることを確認します。

> Jenkins への接続に成功しました。

あわせて、Jenkins の Plugins 画面で 6 個のプラグインが有効であること、`windows-agent` がオンラインであることを確認します。作成されるノードにラベルは付きません。

スクリプトは、CISetup の接続テストとエージェントのオンライン確認を行いません。

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

エージェントは、このサーバーの TCP 50000 へ接続します。CISetup は、このサーバーでも別 PC でも開けます。

---

<!-- _class: lead -->

# 1. 実行前に確認する

---

<!-- _class: small -->

## 実行前に決めること

| 項目 | 内容 |
|---|---|
| 管理者パスワード | 本番用の値を `-AdminPassword` で指定する。省略時は `cisetup-admin` |
| Jenkins URL | 設定用 PC から開く URL。例: `http://ci-server:8080/` |
| 導入される版 | Git は 2.47.1.2。JDK 21 は取得時点の最新 GA。Jenkins は取得時点の最新 LTS |

手作業で確認した Jenkins は 2.580.2 です。版を固定して導入する手順ではありません。

パスワードは ASCII 文字だけを使い、前後の空白、`$`、`"` は避けます。認証ヘッダーは ASCII で作られ、パスワードは初期設定用 Groovy の二重引用符文字列へ埋め込まれます。

---

## 実行条件

コンソールまたは RDP でログオンし、そのデスクトップで管理者 PowerShell を開きます。WinRM などのリモート PowerShell からは実行しません。

- リポジトリ一式が、このサーバー上にある
- TCP 8080 と TCP 50000 が空いている
- このサーバー自身から、指定する Jenkins URL を開ける
- 設定用 PC からも、その URL を開ける
- 配布元と Jenkins の更新サイトへ HTTPS で接続できる

プロキシが必要な環境での動作は未確認です。PowerShell と Jenkins の外部通信経路を決めてから実行します。

---

## 外部通信

初回実行で取得する先:

- Git for Windows: `github.com`
- .NET のインストールスクリプト: `dot.net`
- JDK 21: `api.adoptium.net`
- Jenkins LTS: `get.jenkins.io`
- プラグイン: Jenkins の更新サイト

.NET SDK 本体の取得先、各配布元のリダイレクト先、プラグイン取得時の実通信先は固定していません。許可リスト方式の環境では、検証環境で通信先を確認してから本番へ適用します。

---

## 既存ガイドとの違い

`docs/CISetup-CI-Guide.marp.md` の Jenkins 導入手順は、このセットアップでは使いません。

| 項目 | 既存ガイド | この手順 |
|---|---|---|
| Java | Java 17 | JDK 21 |
| Jenkins | MSI | WAR を直接起動 |
| Windows サービス | 登録する | 登録しない |
| 初回設定 | Web のセットアップウィザード | スクリプトで設定し、ウィザードは出さない |
| エージェント | CISetup から設定 | スクリプトが同一 PC に作る |

スクリプトは JDK 21 を導入し、JDK 21 が見つからない場合は「現在の Jenkins LTS は Java 21 または 25 が必要」と表示して停止します。

スクリプト実行後に、CISetup の「Jenkins サーバーを初期設定」は実行しません。ノードはスクリプトが作成します。この操作は検証環境で HTTP 400 になった実績があります。

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

`-JenkinsUrl` のポートは `-Port` と同じにします。設定用 PC が別 PC の場合は、`localhost` ではなく、その PC から到達できるホスト名または IP アドレスを指定します。

Jenkins の応答待ちは最大 8 分です。プラグイン反映のため再起動した場合も、最大 8 分待ちます。プラグイン導入、ノード登録、トークン発行に使う Groovy の呼び出しは、1 回あたり最大 10 分です。

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

Windows ではパスの大文字と小文字を区別しないため、既定の作業フォルダは `C:\jenkins` の配下です。secret を含む `start-agent.bat` も同じツリーに置かれます。

`C:\jenkins` の継承アクセス権は実機で未確認です。導入後にアクセス権を確認し、このツリーを秘密情報として扱います。

---

<!-- _class: small -->

## スクリプトが行うこと

1. Git for Windows 2.47.1.2 をインストールする
2. .NET SDK 8 を `C:\dotnet` に入れる
3. JDK 21 を `C:\jdk21` に展開する
4. JDK 21 と .NET SDK 8 をマシンの PATH の先頭へ追加する
5. Jenkins LTS の WAR を `C:\jenkins.war` に置く
6. 初期設定用 Groovy と `start-jenkins.bat` を作る
7. TCP 8080 と TCP 50000 の受信規則を追加する
8. セットアップウィザードを出さずに Jenkins を起動する
9. 管理者、Jenkins URL、エージェント待受ポート 50000 を設定する
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

初回は `INSTALLED:` に、今回導入したプラグインが並びます。更新サイトで見つからないプラグインは一覧に含まれず、その理由ではスクリプトは停止しません。

スクリプトは表示結果を網羅的には検査しません。完了後、Jenkins の Plugins 画面で 6 個すべてが有効か確認します。CISetup の接続テストだけでは不足を検出できません。

---

<!-- _class: small -->

## ファイアウォールと完了表示

作る受信規則は次の 2 つです。追加に失敗してもスクリプトは停止しません。

| 表示名 | ポート |
|---|---:|
| `CISetup Jenkins HTTP` | 8080 |
| `CISetup Jenkins Agent` | 50000 |

`ファイアウォール規則を追加できませんでした: <規則名>` と表示された場合は、接続テストの前に該当ポートの受信許可を確認します。

`==> 完了` の後に、Jenkins URL、ユーザー、パスワード、API Token、エージェント名、作業フォルダ、起動スクリプトが表示されます。エージェント登録の途中では、`SECRET=` に続けて secret が表示されます。

スクリプトを実行した PowerShell は、完了後に閉じても Jenkins を停止しません。別に開いた Jenkins とエージェントの各ウィンドウは閉じないでください。ログオフ時の動作は実機で未確認のため、運用上は停止するものとして扱います。

---

<!-- _class: small -->

## 作成されるファイル

| パス | 内容 | 秘密情報 |
|---|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動 | なし |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者、URL、待受ポート。パスワードを含む | あり |
| `C:\jenkins\cisetup-admin-password.txt` | 管理者パスワード | あり |
| `C:\jenkins\cisetup-api-token.txt` | API トークン | あり |
| `C:\Jenkins\workspace\agent.jar` | エージェント本体 | なし |
| `C:\Jenkins\workspace\start-agent.bat` | 起動コマンド。secret を含む | あり |

初期設定用 Groovy は削除されません。Jenkins の画面で URL を変更しても、次回起動時にファイル内の値へ設定されます。

完了表示、`SECRET=`、起動中のエージェントのコマンドラインにも秘密情報が出ます。画面共有を避け、PowerShell の履歴と `C:\jenkins` のアクセス権を保護します。

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

接続テストにリポジトリ URL は不要です。Git の資格情報と Teams Webhook も空のまま実行できます。接続確認後の設定は、この資料の対象外です。

---

## 環境スキャンの扱い

CISetup をこのサーバーで起動すると、実装上は PATH 上の `git`、`dotnet`、`java` を検査します。.NET は 8.x SDK の有無も検査します。

この手順では Jenkins の Windows サービスを作りません。「Jenkins サービス（この PC）」が未検出でも、MSI を追加導入しません。

CISetup を別 PC で開いた場合、環境スキャンはその PC を検査します。Git、.NET SDK 8、Java が未検出でも、Jenkins の接続テストとは別の結果です。

---

## 接続テスト

1. Jenkins の Plugins 画面で 6 個のプラグインが有効か確認する
2. Jenkins URL、ユーザー名、API Token を入力する
3. 「接続テスト」を実行する
4. 次のメッセージを確認する

> Jenkins への接続に成功しました。

---

<!-- _class: small -->

## エージェントを確認する

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `windows-agent` がオンラインであることを確認する

日本語表示でのメニュー名は未確認です。画面上で Nodes に相当する項目を開いてください。

スクリプトは、エージェントがオンラインになるのを待たずに完了します。作成されるノードにラベルは付きません。CISetup のエージェントラベルは空欄にします。

オフラインの場合は、エージェントのウィンドウ、サーバーから Jenkins URL への到達、TCP 50000、受信規則 `CISetup Jenkins Agent` を確認します。Jenkins の応答を確認してから、別のウィンドウで `C:\Jenkins\workspace\start-agent.bat` を実行します。

---

<!-- _class: lead -->

# 4. 初回実行が途中で止まったとき

---

<!-- _class: small -->

## 再実行の前に

多くの処理は最初のエラーで停止します。再実行の前に、スクリプトが起動した Jenkins とエージェントのウィンドウを閉じます。

次の表示だけではスクリプトは停止しません。

- `ファイアウォール規則を追加できませんでした: <規則名>`
- `crumb は取得しませんでした。そのまま Script Console を呼びます。`
- 更新サイトで見つからず、`INSTALLED:` に含まれないプラグイン

`crumb` を取得できなくても Groovy の呼び出しは続きます。その後の成否は、後続の表示と完了の有無で判断します。

初回の取得物は、同じパスにファイルがあると内容を確認せず再利用されます。ダウンロード失敗や破損が確認できたファイルだけを削除し、同じコマンドを再実行します。

---

<!-- _class: small -->

## 取得物を削除して再実行する場合

| 削除するもの | 判断条件 |
|---|---|
| `C:\git-setup.exe` | 取得失敗または破損が確認でき、Git 導入後も `git.exe` が見つからない |
| `C:\dotnet-install.ps1` | インストールスクリプトの取得失敗または破損が確認できた |
| `C:\dotnet` | .NET SDK の展開が不完全で、`C:\dotnet\dotnet.exe` がない |
| `C:\jdk21.zip` | ZIP の取得失敗または破損が確認できた |
| `C:\jenkins.war` | WAR の取得失敗または破損が確認できた |

JDK の再実行時に `java.exe` が見つからなければ、スクリプトは `C:\jdk21` を削除して ZIP を再展開します。

原因が通信、空き容量、ポート競合、アクセス権にある場合は、原因を解消してから再実行します。

---

<!-- _class: small -->

## 接続できないとき

1. サーバーで `http://localhost:8080/login` が開くか確認する
2. 設定用 PC から、実行時に指定した `-JenkinsUrl` を開く
3. ユーザー名と API Token を転記し直す
4. `C:\jenkins\cisetup-api-token.txt` と完了表示を突き合わせる

`Jenkins が 8 分以内に ... で応答しませんでした。` と表示された場合は、TCP 8080 の競合と Jenkins のウィンドウを確認します。プラグイン後の再起動でも、最大 8 分待ちます。

`Jenkins へのログインに失敗しました。` と表示された場合は、実行コマンドの `-AdminUser` と `-AdminPassword` を確認します。初回にパスワードファイルが作成済みなら、再実行時に `-AdminPassword` を省略すると `C:\jenkins\cisetup-admin-password.txt` の値が使われます。

---

## 再起動後に手動で起動する

Jenkins とエージェントは Windows サービスではありません。サーバー再起動後は、次の順で手動起動します。

1. 管理者 PowerShell で `C:\jenkins\start-jenkins.bat` を実行する
2. `http://localhost:8080/login` が開くことを確認する
3. 別のウィンドウで `C:\Jenkins\workspace\start-agent.bat` を実行する

`start-jenkins.bat` は Jenkins が終了するまで戻りません。同じウィンドウで続けてエージェントを起動しないでください。

ウィンドウを閉じると、そこで動く Jenkins またはエージェントは停止します。ログオフ時の動作は実機で未確認です。サーバー起動時に自動で起動する仕組みは作りません。

---

<!-- _class: lead -->

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

Jenkins の Plugins 画面で 6 個が有効であること、`windows-agent` がオンラインであることも確認します。エージェントラベルは空欄のままにします。
