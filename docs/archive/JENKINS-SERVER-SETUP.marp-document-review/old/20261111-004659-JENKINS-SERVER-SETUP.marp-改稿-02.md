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

2026-11-10 に Windows Sandbox で確認したのは手作業の手順です。

`Setup-JenkinsServer.ps1` 自体は、検証環境でも本番環境でも未実行です。
スクリプトが Groovy で行う管理者作成、Jenkins URL 設定、ノード作成も未確認です。

本番で初めて実行する前に、検証環境での試行とサーバーのスナップショット取得の要否を決めてください。

---

## この資料の範囲

| この資料で行うこと | この資料では行わないこと |
|---|---|
| Git、JDK 21、.NET SDK 8、Jenkins LTS の配置 | プロジェクトごとの Git URL 設定 |
| Jenkins 管理者、API トークン、プラグインの準備 | Teams Webhook の作成 |
| Jenkins URL、HTTP ポート、同一 PC エージェントの設定 | CI ジョブの作成とテストビルド |
| CISetup からの接続テスト | Jenkins とエージェントのサービス化 |

---

## 完了条件

設定用 PC の CISetup で、次のメッセージが表示されれば接続確認は完了です。

> Jenkins への接続に成功しました。

同一 PC をエージェントにする場合は、`windows-agent` がオンラインであることも確認します。

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
    └─ windows-agent（同一 PC 構成のみ）
         └─ .NET SDK 8
```

同一 PC エージェントは Jenkins の待受ポート TCP 50000 へ接続します。
別 PC 構成は手順が確立していないため、この資料では接続テストまでを扱います。

---

<!-- _class: lead -->

# 1. 実行前に確認する

---

<!-- _class: small -->

## 本番実行の前に決めること

| 判断事項 | スクリプトの動作 |
|---|---|
| 常時起動の方法 | Windows サービスには登録しない |
| Jenkins 管理者パスワード | 未指定時の既定値は `cisetup-admin` |
| Git、JDK、Jenkins の版 | 既存物を版の検証なしで再利用する |
| 同一 PC／別 PC エージェント | 別 PC 構成の構築手順は未確定 |
| PATH 変更の影響 | JDK 21 と、必要時は .NET SDK 8 をマシン PATH の先頭へ追加する |

ほかのアプリが Java または .NET を PATH 経由で使っている場合は、影響を事前に確認します。

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

スクリプト実行後は、CISetup の「Jenkins サーバーを初期設定」を実行しません。
2026-11-10 の手作業確認では、同機能の `computer/doCreateItem` が HTTP 400 になりました。

---

<!-- _class: small -->

## 実行条件

- コンソールまたは RDP で対話ログオンし、そのデスクトップで管理者 PowerShell を開ける
- リポジトリ一式が Jenkins サーバー上にある
- 使用する HTTP ポートと TCP 50000 が、ほかのプロセスと競合していない
- CISetup を実行する PC から、指定する Jenkins URL に到達できる
- 配布元と Jenkins 更新サイトへ HTTPS で接続できる
- プロキシが必要な場合、PowerShell と Jenkins の通信方法を事前に確認している

WinRM などの非対話セッションでの動作は未確認です。

---

## 外部通信

スクリプトに記載された取得元:

- Git for Windows: `github.com`
- .NET インストールスクリプト: `dot.net`
- JDK 21: `api.adoptium.net`
- Jenkins LTS: `get.jenkins.io`
- Jenkins プラグイン: Jenkins の更新サイト

配布元のリダイレクト先と、更新サイトが使用するホスト名は未確認です。
許可リスト方式の環境では、検証環境で実通信先を確認してから本番へ適用します。

---

## URL とポートを決める

| 項目 | 例 | 用途 |
|---|---|---|
| `-JenkinsUrl` | `http://ci-server:8080/` | CISetup、Jenkins の設定、エージェント接続 |
| `-Port` | `8080` | Jenkins のローカル待受、ファイアウォール規則 |

`-JenkinsUrl` を省略すると、実効値は `http://localhost:<Port>/` です。
設定用 PC が別 PC の場合は、ホスト名または IP アドレスを指定します。

リバースプロキシなどを使う場合の外部 URL とローカル待受ポートの対応は、スクリプトでは確認しません。

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

PowerShell での展開を避けるため、URLとパスワードは単一引用符で囲みます。
パスワードは ASCII 文字だけを使い、`$` を含めないでください。この制約での実行結果は未確認です。

---

## エージェントを別 PC にする場合

Jenkins サーバーでは `-SkipAgent` を指定します。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminPassword '<本番用の管理者パスワード>' `
  -SkipAgent
```

この構成では、.NET SDK 8、ノード登録、agent.jar、TCP 50000 の受信規則を用意しません。

---

<!-- _class: small -->

## 別 PC エージェントの扱い

別 PC にエージェントを構築する手順は未確定です。

- ノードの作成方法は未確定
- TCP 50000 で接続する方式かは未確認
- TCP 50000 を使う場合、Jenkins サーバー側の受信規則は手動で必要
- エージェント PC には JDK、.NET SDK、Git が必要
- 既存ガイドの PowerShell 起動例では、`-url` と `-secret` が渡らない事象を手作業で確認済み

接続方式とノード作成手順が決まるまでは、同一 PC 構成を使用します。

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
| `-SkipAgent` | オフ | .NET SDK 8 とエージェント設定を省略 |

既定パスワードは検証用です。本番では明示指定します。

---

<!-- _class: small -->

## 保存を伴うパラメーター

| パラメーター | 動作 |
|---|---|
| `-ProjectPath` | `<ProjectPath>\CISetup\cisetup.secrets.local.json` を上書き |
| `-FileShare` | `-ProjectPath` もある場合、`CISetup\cisetup.local.json` を上書き |
| `-CISetupExe` | 最後に指定した exe を起動 |

既存ファイルがある場合も全体を書き直します。Git 資格情報、Teams Webhook、格納パスなどは空になります。
設定済みのプロジェクトには `-ProjectPath` を指定しません。

存在しないパスを指定した場合、Jenkins の設定後にエラーになります。

---

<!-- _class: small -->

## スクリプトが行うこと（起動前）

1. Git を確認し、無ければ 2.47.1.2 をインストール
2. 同一 PC 構成では .NET SDK 8 を確認し、`C:\dotnet` をマシン PATH の先頭へ追加
3. JDK 21 を確認し、その `bin` をマシン PATH の先頭へ追加
4. Jenkins LTS WAR を `C:\jenkins.war` に配置
5. 初期設定用 Groovy と起動バッチを作成
6. HTTP ポートと、同一 PC 構成では TCP 50000 の受信規則を追加

既存の実行ファイルやダウンロード済みファイルは、版と内容を検証せず再利用します。

---

<!-- _class: small -->

## スクリプトが行うこと（起動後）

1. Jenkins が動いていなければ WAR を起動
2. 起動時の Groovy で管理者、Jenkins URL、TCP 50000 を設定
3. CISetup 用プラグインを導入し、必要なら Jenkins を再起動
4. 同一 PC 構成ではノードを登録し、エージェントを起動
5. API トークンファイルが空ならトークンを発行
6. 指定があれば CISetup 設定ファイルを書き、CISetup を起動

既に Jenkins が動いている場合、新しく書いた Groovy はその場では適用されません。

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`

実行中に `OK: all plugins already installed (...)` または `INSTALLED: ...` が表示されます。
`INSTALLED:` に6個すべてが並ぶとは限らないため、不足が疑われる場合は Jenkins の Plugins 画面で確認します。

---

<!-- _class: small -->

## 完了表示を確認する

`==> 完了` の後に、Jenkins URL、ユーザー、パスワード、API Token、起動スクリプトが表示されます。
同一 PC 構成では、エージェント名と作業フォルダも表示されます。

最後の行まで確認します。`-CISetupExe` の指定に誤りがある場合は、完了表示の後にエラーになります。

次の表示があった場合は、接続テスト前に受信規則を確認します。

```text
ファイアウォール規則を追加できませんでした: <規則名>
```

---

<!-- _class: small -->

## 平文で残る秘密情報

| 保存先 | 内容 |
|---|---|
| `<JenkinsHome>\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者パスワード |
| `<JenkinsHome>\cisetup-admin-password.txt` | 新規作成時の管理者パスワード |
| `<JenkinsHome>\cisetup-api-token.txt` | API トークン |
| `<AgentWorkDir>\start-agent.bat` | エージェント secret |
| `<ProjectPath>\CISetup\cisetup.secrets.local.json` | Jenkins 接続情報 |

完了表示にもパスワードと API トークンが出ます。画面共有中は表示せず、PowerShell の履歴も保護します。
各フォルダの継承アクセス権で一般ユーザーが読めるかは未確認です。

---

## 作成される主なファイル

| パス | 内容 |
|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動スクリプト |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 初期設定と管理者パスワード |
| `C:\jenkins\cisetup-api-token.txt` | API トークン |
| `C:\jenkins\cisetup-admin-password.txt` | 新規管理者のパスワード |
| `C:\Jenkins\workspace\agent.jar` | 同一 PC 用エージェント |
| `C:\Jenkins\workspace\start-agent.bat` | 起動コマンドと secret |

パスは `-JenkinsHome` と `-AgentWorkDir` の指定で変わります。

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

API トークンは `<JenkinsHome>\cisetup-api-token.txt` でも確認できます。

リポジトリ URL、Git 資格情報、Teams Webhook は、接続テストでは空のままでよいと原文に記載されています。CISetup の現行実装では未確認です。

---

## 環境スキャンの扱い

原文では、環境スキャンで Git、.NET SDK 8、Java 21 を検出し、Jenkins の Windows サービスは未検出のままで問題ないとされています。

この手順では WAR を直接起動し、Windows サービスを作成しません。
設定用 PC が Jenkins サーバーと別の場合の検出結果を含め、CISetup の現行実装では未確認です。

環境スキャンの表示だけで MSI の追加導入へ進まず、接続テストの結果を確認します。

---

## 接続テスト

1. Jenkins URL、ユーザー名、API Token を入力する
2. 「接続テスト」を実行する
3. 次のメッセージを確認する

> Jenkins への接続に成功しました。

CISetup の画面名とメッセージは、原文の記載に基づいています。現行実装では未確認です。

---

<!-- _class: small -->

## 接続テストが成功しない場合

1. Jenkins サーバーで `http://localhost:<Port>/login` の応答を確認する
2. 設定用 PC から `-JenkinsUrl` をブラウザで開く
3. URL のホスト名、ポート、パスを確認する
4. ユーザー名と API トークンを転記し直す
5. 無効なトークンを再利用していないか確認する

トークンを作り直す場合は、`<JenkinsHome>\cisetup-api-token.txt` を削除してからスクリプトを再実行します。
再実行前に Jenkins とエージェントのウィンドウを閉じます。

---

## 同一 PC のエージェントを確認する

`-SkipAgent` を指定しなかった場合だけ確認します。

1. Jenkins を開く
2. `Manage Jenkins → Nodes` を開く
3. `windows-agent` がオンラインであることを確認する

スクリプトはラベルを設定しません。CISetup が作成するジョブに `windows` ラベルが必要かは未確認です。

---

## エージェントがオフラインの場合

- エージェントのコマンドウィンドウが開いているか確認する
- Jenkins サーバーから `-JenkinsUrl` へ到達できるか確認する
- TCP 50000 の受信規則を確認する
- Jenkins の応答後、別のウィンドウで `<AgentWorkDir>\start-agent.bat` を実行する

スクリプトは、エージェントがオンラインになるのを待たずに完了します。

---

<!-- _class: small -->

## Jenkins が応答しない場合

| 表示または症状 | 確認すること |
|---|---|
| `Jenkins が 8 分以内に http://localhost:<Port>/login で応答しませんでした。` | HTTP ポート競合、Jenkins のウィンドウ |
| `Jenkins へのログインに失敗しました。` | `-AdminUser` と `-AdminPassword` |
| 既存 Jenkins でログイン失敗 | 既存管理者のパスワードを明示して再実行 |
| 設定用 PC からだけ接続不可 | 名前解決、受信規則、`-JenkinsUrl` |
| API Token がトークンに見えない | トークンファイルを削除して再実行 |

Groovy の例外時に `scriptText` が返す HTTP ステータスと本文は未確認です。

---

<!-- _class: small -->

## URL またはポートを変えて再実行する

1. Jenkins とエージェントのウィンドウを閉じる
2. パラメーターを変更してスクリプトを再実行する
3. ポートを変えた場合は既存の受信規則を確認する
4. Jenkins の応答後に接続テストをやり直す

受信規則は表示名だけで既存判定するため、同じ表示名の規則があると新しいポートの規則を作りません。
初期設定用 Groovy は残るため、Jenkins 起動時にファイル内の URL が再設定されます。

---

## 再起動・ログオフ後

Jenkins とエージェントは Windows サービスではありません。
実行中のウィンドウを閉じた場合、ログオフした場合、サーバーを再起動した場合は停止します。

1. 管理者 PowerShell で `<JenkinsHome>\start-jenkins.bat` を実行する
2. `http://localhost:<Port>/login` の応答を確認する
3. 同一 PC 構成では、別のウィンドウで `<AgentWorkDir>\start-agent.bat` を実行する

常時稼働に必要なサービス化や自動起動は、別途設計します。

---

<!-- _class: small -->

## 版と再利用条件

- Git が無い場合は 2.47.1.2 を取得する
- `C:\Program Files\Git\cmd\git.exe` があれば、その版を使う
- `C:\jdk21` 配下に `java.exe` があれば、その版を使う
- `C:\jdk21.zip` があれば再ダウンロードしない
- `C:\jenkins.war` があれば再ダウンロードしない
- API トークンファイルが空でなければ、その内容を再利用する

既存ファイルの版、内容、ハッシュ、有効性は検証しません。

---

<!-- _class: lead -->

# 完了

CISetup の接続テストで
「Jenkins への接続に成功しました。」
と表示されたことを確認します。

同一 PC 構成では、`windows-agent` のオンライン状態も確認します。
