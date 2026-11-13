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

エージェントは、このサーバー上の `windows-agent` です。.NET SDK 8 もこのサーバーへ入ります。

既に Jenkins、Git、JDK、.NET が入っているサーバー、別 PC のエージェント、`-SkipAgent`、`-ProjectPath`、`-FileShare`、`-CISetupExe` は対象外です。接続情報は、完了表示を CISetup へ手で転記します。

---

<!-- _class: small -->

## 検証状況

2026-11-10 に Windows Sandbox で手作業の手順を確認しました。確認時の Jenkins は 2.580.2 です。Java 17 では起動しませんでした。

2026-11-11 の Windows Sandbox で、この改訂のスクリプトを実行しました。Git 2.47.1、.NET SDK 8.0.428、JDK 21.0.13 の導入、Jenkins の起動、管理者でのログインまでは進みました。プラグイン導入は `pluginManager.updateCenter` が無いため失敗し、`Jenkins.updateCenter` を使うように直しました。プラグイン以降の通し実行は、この修正のあと再実行します。

CISetup の接続成功時の表示は「Jenkins への接続に成功しました。」です。接続テストが使う入力は Jenkins URL、ユーザー名、API Token です。

プロキシ環境、配布元のリダイレクト先、`C:\jenkins` の継承アクセス権、RDP を切断したあとにウィンドウが残るかは未確認です。

---

## この資料の範囲

| 行うこと | 行わないこと |
|---|---|
| Git、JDK 21、.NET SDK 8、Jenkins LTS の新規導入 | プロジェクトごとの CI ジョブ作成 |
| Jenkins 管理者、API トークン、プラグインの準備 | リポジトリ URL、Teams Webhook の設定 |
| 同一 PC エージェントの作成とオンライン確認 | テストビルド |
| CISetup からの接続テスト | Windows サービス化、別 PC エージェント |

---

## 完了条件

設定用 PC の CISetup で、次のメッセージが表示されれば接続確認は完了です。

> Jenkins への接続に成功しました。

スクリプトが `OK: plugins active (...)` に 6 個のプラグイン ID を出していること、`windows-agent` がオンラインであることも確認します。スクリプトは、オンラインになるまで最大 3 分待ち、ならなければ停止します。

CISetup のエージェントラベルは空欄にします。組み込みノードの実行数は 0 なので、ラベルなしのビルドは `windows-agent` に付きます。既存ガイドの例 `windows` は付けないでください。ノードにそのラベルは無く、ビルドが割り当てられません。

---

## 構成

```text
設定用 PC（CISetup）
    │  http://<Jenkins サーバー>:8080/
    ▼
Jenkins サーバー（未導入の Windows）
    ├─ Jenkins LTS（WAR、JDK 21、組み込みノードの実行数 0）
    ├─ Git 2.47.1.2
    └─ windows-agent（WebSocket、ラベルなし）
         └─ .NET SDK 8
```

エージェントは Jenkins の HTTP URL へ WebSocket で接続します。待受ポート TCP 50000 も設定します。CISetup は、このサーバーでも別 PC でも開けます。

---

<!-- _class: lead -->

# 1. 実行前に確認する

---

<!-- _class: small -->

## 実行前に決めること

| 項目 | 内容 |
|---|---|
| 管理者パスワード | `-AdminPassword` で指定する。省略すると `cisetup-admin` になる |
| Jenkins URL | 設定用 PC から開く URL。例の `ci-server` は、そのホスト名に置き換える |
| 入る版 | Git は 2.47.1.2。JDK 21 は実行時点の最新 GA。Jenkins は実行時点の最新 LTS。.NET SDK は 8.0 チャネルの取得時点の版 |

手作業で確認した Jenkins は 2.580.2 です。版を固定して入れる手順は、この資料にはありません。

パスワードに使える文字は ASCII です。`$` は初期設定用 Groovy の文字列展開になるため入れません。実行コマンドは単一引用符で囲むため、`'` も入れません。前後の空白は入れません。認証ヘッダーは空白を除きますが、アカウント作成時のパスワードはそのまま保存されます。

---

## 実行条件

コンソールまたは RDP でログオンし、そのデスクトップの管理者 PowerShell で実行します。WinRM などのリモート PowerShell では実行しないでください。

- リポジトリ一式が、このサーバー上にある
- TCP 8080 と TCP 50000 が空いている
- このサーバー自身から、指定する Jenkins URL を開ける
- 設定用 PC からも、その URL を開ける
- 配布元と Jenkins の更新サイトへ HTTPS で接続できる

プロキシが必要な環境では、PowerShell と Jenkins の通り道を先に決めてから実行します。スクリプトは Jenkins のプロキシを設定しません。

---

## 外部通信

初回実行で取得する先です。リダイレクト先のホスト名は、この資料では特定していません。

- Git for Windows: `github.com`
- .NET のインストールスクリプト: `dot.net`（SDK 本体は、そのスクリプトが別ホストから取得する）
- JDK 21: `api.adoptium.net`
- Jenkins LTS: `get.jenkins.io`
- プラグイン: Jenkins の更新サイト

許可リスト方式の環境では、検証環境で実通信先を確認してから本番へ適用します。

---

<!-- _class: small -->

## 既存ガイドとの違い

`docs/CISetup-CI-Guide.marp.md` と、CISetup の「アプリで自動化できない準備」は、この手順では使いません。画面は MSI の導入と「詳細設定 → Jenkins サーバー初回設定」を案内します。そのボタンは押さないでください。検証環境では、そのノード作成（`computer/doCreateItem`）が HTTP 400 になりました。ノードはスクリプトが作ります。

| 項目 | 既存ガイド | この手順 |
|---|---|---|
| Java | Java 17 | JDK 21（現行 LTS は Java 21 または 25。検証時、Java 17 では起動しなかった） |
| Jenkins | MSI と Windows サービス | WAR を直接起動。サービスは作らない |
| 初回設定 | Web のセットアップウィザード | スクリプト（ウィザードは出さない） |
| エージェント | CISetup の初回設定 | スクリプトが同一 PC に作る |
| エージェントラベル | 例は `windows` | ラベルなし。CISetup の欄は空欄 |

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

`ci-server` は、設定用 PC から開くホスト名に置き換えます。ポートは `-Port` と同じにします。

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl 'http://ci-server:8080/' `
  -Port 8080 `
  -AdminUser 'admin' `
  -AdminPassword '<本番用の管理者パスワード>'
```

Jenkins の応答待ちは最大 8 分です。プラグイン反映で再起動すると、さらに最大 8 分待ちます。プラグイン導入とノード登録の呼び出しは、1 回あたり最大 10 分です。エージェントのオンライン待ちは最大 3 分です。

---

<!-- _class: small -->

## スクリプトが行うこと

1. Git for Windows 2.47.1.2 をインストールする
2. .NET SDK 8 を `C:\dotnet` に入れる。`dotnet.exe` があっても 8.x が無ければ入れ直す
3. `C:\jdk21` に `java.exe` が無ければ、JDK 21 の ZIP を取得して展開する。見つからない時点では停止しない
4. JDK 21 と .NET SDK 8 を、マシンの PATH の先頭へ追加する
5. Jenkins LTS の WAR を `C:\jenkins.war` に置く
6. 初期設定用 Groovy と `start-jenkins.bat` を作る
7. TCP 8080 と TCP 50000 の受信規則を追加する。失敗しても、この時点では停止しない
8. ウィザードを出さずに Jenkins を起動する
9. 管理者を作る。組み込みノードの実行数を 0 にし、Jenkins URL と待受ポート 50000 を設定する
10. プラグインを導入する。6 個が有効でなければ停止する
11. ラベルなしの `windows-agent` を WebSocket で登録し、起動する
12. オンラインになるまで最大 3 分待つ。ならなければ停止する
13. 名前 `cisetup` の API トークンを発行する

取得物は、空でなく、ZIP と EXE は先頭の形式が合うときだけ再利用します。壊れている場合は削除して取り直します。通信が途中で切れたファイルは、残っていても形式が合わなければ使いません。

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`

`OK: all plugins already installed (...)` は、6 個が既に入っているときの表示です。`INSTALLED:` は、今回導入を試みた ID です。その後、スクリプトは `OK: plugins active (workflow-aggregator, git, credentials-binding, plain-credentials, parameterized-trigger, naginator)` を確認します。この行が無い場合は完了していません。

更新サイトに無いプラグイン、導入の失敗、無効のまま残ったプラグインでは停止します。再実行で入れ直すのは、未導入の ID だけです。無効のまま残ったものは、Plugins 画面で有効にしてください。

Plugins 画面の表示名は版と言語で変わります。有効かどうかは、上の `OK: plugins active` の ID で判断します。

---

<!-- _class: small -->

## ファイアウォールと完了表示

| 表示名 | ポート |
|---|---:|
| `CISetup Jenkins HTTP` | `-Port`（この手順では 8080） |
| `CISetup Jenkins Agent` | 50000 |

`ファイアウォール規則を追加できませんでした: <規則名>` と出ても、その場では止まりません。同じ表示が完了時にも出ます。設定用 PC から URL を開けないときは、`CISetup Jenkins HTTP` とホスト名の名前解決を確認します。

`==> 完了` の後に、Jenkins URL、ユーザー、パスワード、API Token、プラグインの確認行、エージェント名、作業フォルダが出ます。エージェント登録の途中では、`SECRET=` に続けて secret が出ます。

ウィンドウは閉じないでください。ログオフすると停止します。Jenkins またはエージェントが終了したときは、ウィンドウに「終了しました」と残り、キー入力を待ちます。起動に失敗してウィンドウが残っていない場合は、管理者 PowerShell で `C:\jenkins\start-jenkins.bat` を実行し、終了時の表示を確認します。

---

<!-- _class: small -->

## 作成されるファイル

| パス | 内容 | 秘密情報 |
|---|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動。終了後に表示を残す | なし |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者、実行数 0、URL、待受ポート。パスワードを平文で含む | あり |
| `C:\jenkins\cisetup-admin-password.txt` | ログインに使ったパスワード。Groovy のエスケープは含まない | あり |
| `C:\jenkins\cisetup-api-token.txt` | API トークン。形式が違う場合は発行し直す | あり |
| `C:\Jenkins\workspace\agent.jar` | エージェント本体 | なし |
| `C:\Jenkins\workspace\start-agent.bat` | 起動コマンド。secret を含む | あり |

初期設定用 Groovy は残ります。Jenkins の画面で URL や組み込みノードの実行数を変えても、次回起動時にファイルの値へ戻ります。

管理者は初回起動時に一度だけ作られます。パスワードを変えて再実行しても、Jenkins 上のパスワードは変わりません。`-AdminPassword` を省略し、パスワードファイルがあるときは、そのファイルを使います。

完了表示、`SECRET=`、コマンドラインにも秘密情報が出ます。画面共有を避け、PowerShell の履歴を残さないようにします。`C:\jenkins` のアクセス権は、サーバーの運用に合わせて管理者と実行ユーザーに限ってください。

作業フォルダは `C:\jenkins` の配下です。secret を含む `start-agent.bat` もそこにあります。

---

<!-- _class: lead -->

# 3. CISetup で接続を確認する

---

## CISetup に入力する

設定用 PC で CISetup を開きます。入力欄は「⑤ Jenkins への接続」です。

| CISetup の項目 | 入力値 |
|---|---|
| Jenkins URL | 完了表示の `Jenkins URL` |
| ユーザー名 | 完了表示の `ユーザー` |
| API Token | 完了表示の `API Token` |

API トークンは `C:\jenkins\cisetup-api-token.txt` でも確認できます。

接続テストにリポジトリ URL は要りません。Git の資格情報と Teams Webhook も空のまま実行できます。これらは、接続確認の後に入れます。

---

<!-- _class: small -->

## 環境スキャンの扱い

スキャンは起動時には走りません。「環境をスキャン」を押すと、その PC の PATH 上の `git`、`dotnet`、`java` と、.NET の 8.x SDK を検査します。

このサーバーで押した場合、Git、.NET SDK 8、Java 21 が検出されます。「Jenkins サービス（この PC）」は未検出です。MSI は入れないでください。スキャンの Java の案内が JDK 17 以降でも、この手順の JDK は 21 です。

CISetup を別 PC で開いた場合、その PC で Git や JDK が未検出でも、接続テストの成否には影響しません。接続テストが成功すれば、この資料の作業は先へ進めます。後続でその PC からビルドする場合は、その PC にも Git と .NET SDK 8 が必要です。

---

## 接続テスト

1. スクリプトの `OK: plugins active` に 6 個の ID があることを確認する
2. 「⑤ Jenkins への接続」に Jenkins URL、ユーザー名、API Token を入力する
3. 「接続テスト」を実行する
4. 次のメッセージを確認する

> Jenkins への接続に成功しました。

---

<!-- _class: small -->

## エージェントを確認する

1. Jenkins を開く
2. `Manage Jenkins → Nodes`（日本語表示ではノード管理）を開く
3. `windows-agent` がオンラインであることを確認する

スクリプトは最大 3 分待ち、オンラインでなければ停止します。ノードにラベルは付きません。

オフラインのときは、先に起動したエージェントのウィンドウを閉じてから、別のウィンドウで `C:\Jenkins\workspace\start-agent.bat` を実行します。サーバーから Jenkins URL へ届くこと、受信規則 `CISetup Jenkins Agent` も確認します。

---

<!-- _class: lead -->

# 4. 初回実行が途中で止まったとき

---

<!-- _class: small -->

## 再実行の前に

多くの処理は最初のエラーで止まります。再実行の前に、起動した Jenkins とエージェントのウィンドウを閉じます。

次の場合は、その場では止まりません。

- `ファイアウォール規則を追加できませんでした: <規則名>`
- `crumb は取得しませんでした。そのまま Script Console を呼びます。`

スクリプトは crumb と一緒にセッション Cookie を送ります。それでもプラグイン導入やノード登録が HTTP 403 で止まった場合は、本番へ進まず、同じ前提の検証環境で原因を確認します。原因がスクリプト側にある場合、この手順では先へ進めません。

未導入の状態へ戻すときは、ウィンドウを閉じたあと次を削除して、同じコマンドを再実行します。

- `C:\jenkins`（管理者とトークンを作り直すとき）
- `C:\jenkins.war`（WAR が壊れて起動しないとき）
- `C:\jdk21.zip`（展開エラーのとき。スクリプトが削除している場合は不要）
- `C:\git-setup.exe`（インストール後も `git.exe` が無いとき）
- `C:\dotnet-install.ps1` と `C:\dotnet`（`dotnet.exe` が無い、または 8.x SDK が無いとき）
- `C:\Jenkins\workspace\agent.jar`（形式が合わず、スクリプトが削除していないとき）

受信規則を消す場合は `Remove-NetFirewallRule -DisplayName 'CISetup Jenkins HTTP'` と `CISetup Jenkins Agent` です。Git 自体のアンインストールは、この資料では行いません。

---

<!-- _class: small -->

## 表示と対処

| 表示 | 対処 |
|---|---|
| `管理者として実行してください。` | 管理者 PowerShell で再実行 |
| `Git のインストール後も ... が見つかりません。` | `C:\git-setup.exe` を削除して再実行 |
| `Git のインストーラーが終了コード` | 同じ。インストーラーの表示を確認する |
| `.NET SDK の展開後も` または `.NET SDK 8 が見つかりません` | `C:\dotnet-install.ps1` と `C:\dotnet` を削除して再実行 |
| `JDK 21 の展開に失敗しました` または `展開後も java.exe が見つかりません` | `C:\jdk21.zip` を削除して再実行。未導入のサーバーでは、取得前にはこの表示で止まらない |
| `Jenkins が 8 分以内に ... で応答しませんでした。` | ウィンドウの表示を確認する。残っていなければ `start-jenkins.bat` を実行する。WAR の形式が違う場合は `C:\jenkins.war` を削除する |
| `Jenkins へのログインに失敗しました。` | 初回のパスワードを使う。入れなければ `C:\jenkins` を削除して最初から実行する |
| `プラグインの導入に失敗しました` または `必要なプラグインが有効ではありません` | 更新サイトへの通信を確認する。無効のままなら Plugins 画面で有効にする |
| `エージェントの secret を取得できませんでした` | 結果の表示を確認し、`C:\jenkins` を削除して最初から実行する |
| `エージェント ... が 3 分以内にオンラインになりませんでした` | エージェントのウィンドウを閉じて `start-agent.bat` を実行する |
| `API Token を発行できませんでした` | 結果の表示を確認する。トークンファイルは残していない |

Groovy の呼び出しは 1 回あたり最大 10 分で時間切れになります。プラグイン後の再起動では、応答待ちがさらに最大 8 分あります。

---

## 接続テストが失敗したとき

1. サーバーで `http://localhost:8080/login` が開くか確認する
2. 設定用 PC のブラウザで、完了表示の Jenkins URL を開く。開けない場合は、受信規則 `CISetup Jenkins HTTP` とホスト名の名前解決を確認する
3. 「⑤ Jenkins への接続」のユーザー名と API Token を転記し直す
4. それでも失敗する場合は、`C:\jenkins\cisetup-api-token.txt` を削除してスクリプトを再実行する。再実行は名前 `cisetup` のトークンを追加する。古いトークンは、ユーザー名 → Configure → API Token で失効させる

接続テストの失敗表示は CISetup のダイアログです。スクリプト実行中の「8 分以内に応答しませんでした」「ログインに失敗しました」は、前の表で対処します。

---

## 再起動・ログオフ後

Jenkins とエージェントは Windows サービスではありません。ウィンドウを閉じたとき、ログオフしたとき、サーバーを再起動したときは停止します。

1. 管理者 PowerShell で `C:\jenkins\start-jenkins.bat` を実行する。このウィンドウは Jenkins が終わるまで戻らない
2. 別の操作で `http://localhost:8080/login` が開くのを確認する
3. 別のウィンドウで `C:\Jenkins\workspace\start-agent.bat` を実行する

サーバー起動のたびに自動で上げる仕組みは、この手順では作りません。

---

<!-- _class: lead -->

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

`OK: plugins active` に 6 個の ID があること、`windows-agent` がオンラインであることも確認します。エージェントラベルは空欄のままにします。

次は、対象プロジェクトの Git URL を入れて CI ジョブを作成します。
