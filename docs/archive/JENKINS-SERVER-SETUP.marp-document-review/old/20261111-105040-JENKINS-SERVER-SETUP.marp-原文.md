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
    │  http://<Jenkinsサーバー>:<Port>/
    ▼
Jenkins サーバー（未導入の Windows）
    ├─ Jenkins LTS（WAR、組み込みノードの実行数 0）
    ├─ JDK 21
    ├─ Git for Windows
    ├─ .NET SDK 8
    └─ windows-agent（インバウンド接続、ラベルなし）
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
| 設定用 PC | CISetup を起動できる PC |
| Jenkins URL | 設定用 PC から開ける URL。例: `http://ci-server:8080/` |
| 管理者ユーザー名 | 既定値は `admin` |
| 管理者パスワード | `-AdminPassword` で指定する |

`-AdminPassword` を省略した場合は `cisetup-admin` になります。本番環境では明示的に指定してください。

パスワードは ASCII 文字だけで作り、先頭と末尾に空白を入れません。スクリプトは認証ヘッダーを ASCII で作り、前後の空白を取り除くためです。

コマンドでは値を単一引用符で囲むため、パスワードに `'` は使えません。`$`、`"`、`\` は、スクリプトが初期設定用 Groovy へ渡すときに退避します。

---

## 実行条件

コンソールまたは RDP でサーバーへログオンし、そのデスクトップで管理者 PowerShell を開きます。ウィンドウを起動するため、WinRM などのリモート PowerShell では実行しません。

- TCP 8080（`-Port` の値）と TCP 50000 がほかの用途で使われていない
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

.NET SDK 本体や各配布物は、別のホストへリダイレクトされる場合があります。許可リスト方式の環境では、検証環境で実際の通信先を確認してから申請してください。

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
| エージェント | 同一サーバーからのインバウンド接続 |

CISetup の画面は MSI 版 Jenkins と「Jenkins サーバー初回設定」を案内しますが、この手順ではどちらも使用しません。WAR の配置からエージェント登録までを PowerShell スクリプトが行うためです。

環境スキャンで「Jenkins サービス（この PC）」が未検出になるのは正常です。

---

<!-- _class: small -->

## 検証状況

この手順は、`tools/Setup-JenkinsServer.ps1`、CISetup の Jenkins 接続画面、環境スキャン、エージェントラベル設定、Jenkinsfile のエージェント指定と照合しています。

**Windows Sandbox での確認（2026-11-11）**

- Jenkins、JDK、.NET SDK、設定を消した状態から、1回の実行で `==> 完了` まで進んだ（約7分）
- 導入された版: Jenkins 2.580.2、Temurin 21.0.13+9、.NET SDK 8.0.428。Git は 2.47.1.windows.2（この確認では導入済み）
- パスワードに `$` を含めても初期化とログインに成功した
- 発行した API Token で Jenkins の API に接続でき、`windows-agent` はオンライン、組み込みノードの実行数は 0
- 受信規則 2 件が作られ、`agent any` のパイプラインが `windows-agent` で成功した

**未確認**

- CISetup の画面からの接続テスト（API Token での API 接続までは確認）
- Windows Server、プロキシ環境、配布元のリダイレクト先
- RDP 切断時の Jenkins とエージェントの継続動作
- パスワードの `\`、`"`（`$` のみ確認）

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
| プラグイン導入 | 最大3回（失敗時は30秒おき） |
| エージェントのオンライン待ち | 3分。超えたら1回だけ起動し直し、さらに3分 |

通信の一時的な失敗などは、スクリプトが自動でやり直します。それでも上限を超えると停止します。停止した場合は原因を解消し、同じコマンドを再実行します。`==> 完了` が出る前は、API Token が未発行の場合があります。

---

<!-- _class: small -->

## プラグイン反映時の再起動

プラグインを導入した直後は、反映のために再起動が必要です。スクリプトは Jenkins を停止し、古い Jenkins のウィンドウを閉じて、新しいウィンドウで起動します。

古いウィンドウが消え、新しい Jenkins ウィンドウが開いても正常です。PowerShell の処理が続いていることを確認してください。

処理中は、現在動いている Jenkins、エージェント、実行元 PowerShell のウィンドウを閉じません。

---

## 導入するプラグイン

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`

導入後、スクリプトは次の形式の行を出力します。先頭に `Result: ` が付きます。

```text
Result: OK: plugins active (workflow-aggregator, git, credentials-binding, plain-credentials, parameterized-trigger, naginator)
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

| パス | 内容 | 含む秘密情報 |
|---|---|---|
| `C:\jenkins\start-jenkins.bat` | Jenkins 起動 | なし |
| `C:\jenkins\init.groovy.d\01-cisetup-bootstrap.groovy` | 管理者と基本設定 | 管理者パスワード |
| `C:\jenkins\cisetup-admin-password.txt` | 管理者パスワード | 管理者パスワード |
| `C:\jenkins\cisetup-api-token.txt` | API Token | API Token |
| `C:\jenkins\workspace\agent.jar` | エージェント本体 | なし |
| `C:\jenkins\workspace\start-agent.bat` | エージェント起動 | エージェント secret |

エージェントの作業フォルダは `C:\jenkins` の配下です。フォルダ全体を運用方針に従ってアクセス制限してください。

---

## 秘密情報の扱い

次の場所に秘密情報が残ります。

- 完了表示: 管理者パスワード、API Token
- 実行途中のコンソール出力: `SECRET=<エージェント secret>`
- PowerShell のコマンド履歴: 管理者パスワード
- エージェントのプロセスのコマンドライン: エージェント secret（`start-agent.bat` が `agent.jar` へ渡す）
- 初期設定用 Groovy とパスワードファイル: 管理者パスワード
- `start-agent.bat`: エージェント secret

実行中は画面共有を避け、ログを保存する場合は秘密情報を除いてください。

---

## 管理者設定の注意

管理者アカウントは、Jenkins のセキュリティ設定が未作成のときだけ作られます。

- パスワードを変えて再実行しても、既存アカウントのパスワードは変わらない
- `-AdminPassword` を省略し、パスワードファイルがあれば、その保存値を使用する
- 初期設定用 Groovy は残り、起動時に Jenkins URL、エージェント待受ポート 50000、組み込みノードの実行数 0 を設定する

Jenkins の画面でこれらを変更しても、次回起動時に Groovy の値へ戻ります。

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

入力した URL、ユーザー名、API Token で Jenkins の API に認証できたことを示します。

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

スクリプトはエージェントがオンラインになるまで最大3分待ちます。ならなければ、エージェントを1回起動し直して、さらに3分待ちます。それでもならなければ、処理は完了表示の前に停止します。

エージェントは同じサーバー上の `http://localhost:<Port>/` を指定して起動し、Jenkins のエージェント用ポート（TCP 50000）へ接続します。

---

<!-- _class: lead -->

# 4. 初回実行が止まったとき

---

## 再実行の原則

スクリプトが停止したら、表示されたエラーと Jenkins、エージェントのウィンドウを確認します。

1. エラーの原因を解消する
2. 最初に使用したものと同じコマンドを再実行する
3. `==> 完了` が表示されるまで続ける

スクリプトは起動中の Jenkins を検出して再利用します。エージェントが起動中でもオンラインでなければ、スクリプトが終了させて起動し直します。再実行の前に、Jenkins やエージェントのウィンドウを閉じる必要はありません。

---

## 停止しない警告

次の表示だけでは、スクリプトは停止しません。

```text
ファイアウォール規則を追加できませんでした: <規則名>
crumb は取得しませんでした。そのまま Script Console を呼びます。
プラグインの導入を 30 秒後にやり直します（1 回目に失敗）。
エージェントがオンラインになりません。起動し直します。
```

後続処理が成功したかどうかは、`==> 完了` とプラグインの確認結果で判断します。

---

<!-- _class: small -->

## 主なエラーと対処（導入）

| 表示 | 対処 |
|---|---|
| `管理者として実行してください。` | 管理者 PowerShell で再実行 |
| ダウンロード処理の例外 | 外部通信を確認して再実行。途中の壊れた取得物はスクリプトが削除する |
| `ダウンロードしたファイルを確認できませんでした` | 配布元と通信経路を確認して再実行 |
| `Git のインストーラーが終了コード ...` | 終了コードの原因を解消し、再実行 |
| `Git のインストール後も ... が見つかりません` | `C:\git-setup.exe` を削除して再実行 |
| `.NET SDK のインストーラーが終了コード ...` | `C:\dotnet-install.ps1` を削除して再実行 |
| `.NET SDK の展開後も ...` | `C:\dotnet-install.ps1` と `C:\dotnet` を削除して再実行 |
| `.NET SDK 8 が見つかりません` | `C:\dotnet` を削除して再実行 |

---

<!-- _class: small -->

## 主なエラーと対処（JDK・Jenkins）

| 表示 | 対処 |
|---|---|
| `JDK 21 の展開に失敗しました` | zip は削除済み。そのまま再実行 |
| `JDK 21 の展開後も java.exe が見つかりません` | `C:\jdk21.zip` と `C:\jdk21` を削除して再実行 |
| `PATH に追加する場所がありません` | 表示されたフォルダの作成状態を確認して再実行 |
| `Jenkins が 8 分以内に ... 応答しませんでした` | Jenkins ウィンドウで原因を確認。必要なら手動起動し、そのまま同じコマンドを再実行 |
| `Jenkins へのログインに失敗しました` | 初回指定のパスワードを確認。作り直す場合は「Jenkins の設定を作り直す場合」に従う |
| `プラグインの導入に 3 回失敗しました` | Jenkins 更新サイトへの通信を確認して再実行 |
| `必要なプラグインが有効ではありません` | Jenkins のウィンドウを閉じ、`start-jenkins.bat` で再起動してから、同じコマンドを再実行 |

---

<!-- _class: small -->

## 主なエラーと対処（エージェント・Token）

| 表示 | 対処 |
|---|---|
| `エージェントの secret を取得できませんでした` | 結果表示と Jenkins のノード状態を確認して再実行 |
| `agent.jar を確認できませんでした` | Jenkins への通信を確認して再実行 |
| `エージェント ... が起動し直しても 6 分以内にオンラインになりませんでした` | `start-agent.bat` のウィンドウの表示と、Jenkins の Nodes 画面の `windows-agent` のログで原因を確認し、同じコマンドを再実行 |
| `API Token を発行できませんでした` | 結果表示を確認して再実行。成功するまでトークンファイルは作成されない |

エージェント待ちで停止した時点では、API Token 発行と完了表示は未実行です。エージェントだけをオンラインにして作業を終えず、同じコマンドを再実行します。

---

## Jenkins の起動を確認する

Jenkins のウィンドウが残っていない場合は、管理者 PowerShell から起動します。

```powershell
& 'C:\jenkins\start-jenkins.bat'
```

この PowerShell は Jenkins が終了するまで戻りません。Jenkins の応答確認とスクリプトの再実行は、別の管理者 PowerShell で行います。

起動に失敗した理由は、Jenkins のウィンドウに残る表示で確認します。

---

<!-- _class: small -->

## 接続テストが失敗したとき

「Jenkins サーバーに接続できませんでした。」の場合:

1. サーバーで `http://localhost:8080/login` を開く
2. 開けなければ Jenkins の起動状態と `-Port` を確認する
3. 設定用 PC で完了表示の Jenkins URL を開く
4. 設定用 PC だけ開けなければ、HTTP の受信規則、ポート、名前解決を確認する

`-Port` を 8080 以外にした場合は、確認 URL のポートも置き換えます。

---

<!-- _class: small -->

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

再実行すると、`cisetup` という名前のトークンが追加されます。古いトークンは、Jenkins のユーザー設定にある API Token 画面で失効させます。

---

## Jenkins の設定を作り直す場合

管理者アカウントを含めて作り直す場合は、Jenkins とエージェントを終了してから `C:\jenkins` を削除し、同じコマンドを再実行します。

`C:\jenkins` を削除すると、配下のエージェント作業フォルダ、`agent.jar`、`start-agent.bat` も消えます。再実行で作り直されます。

Git for Windows、`C:\jdk21`、`C:\dotnet`、マシン PATH、ファイアウォール規則は残り、再実行時に再利用されます。

---

## 取得物を削除して再実行する場合

取得物が壊れている場合は、エラー表示と対象ファイルを照合してから削除します。

- Jenkins WAR: `C:\jenkins.war`
- JDK: `C:\jdk21.zip`
- Git: `C:\git-setup.exe`
- .NET: `C:\dotnet-install.ps1` と `C:\dotnet`
- エージェント: `C:\jenkins\workspace\agent.jar`

ダウンロード中にエラーになったファイルと、ファイルの種類を確認できなかったファイルは、スクリプトが削除します。確認するのはファイル先頭の2バイトです（ZIP は `PK`、EXE は `MZ`）。電子署名やハッシュは検証しません。

---

## 再起動・ログオフ後

Jenkins とエージェントは Windows サービスではありません。ウィンドウを閉じたとき、ログオフしたとき、サーバーを再起動したときは停止します。

1. 管理者 PowerShell で `C:\jenkins\start-jenkins.bat` を実行する
2. 別のウィンドウで `http://localhost:8080/login` が開くことを確認する（`-Port` が 8080 以外なら、そのポート）
3. 別のウィンドウで `C:\jenkins\workspace\start-agent.bat` を実行する
4. Jenkins の Nodes 画面で `windows-agent` のオンラインを確認する

Jenkins を起動した PowerShell は、Jenkins が終了するまで戻りません。

---

<!-- _class: lead -->

# 完了

CISetup の接続テストで  
「Jenkins への接続に成功しました。」  
と表示されたことを確認します。

`OK: plugins active` に6個の ID があり、  
`windows-agent` がオンラインであれば、  
初回セットアップは完了です。

次は、対象プロジェクトの Git URL などを入力し、CI ジョブを作成します。
