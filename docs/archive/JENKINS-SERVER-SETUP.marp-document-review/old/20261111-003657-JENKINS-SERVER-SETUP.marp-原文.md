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

CISetup から接続できる状態まで

対象: Jenkins を動かす Windows サーバー  
スクリプト: `tools/Setup-JenkinsServer.ps1`  
検証日: 2026-11-10（Windows Sandbox）

---

## この資料の範囲

Jenkins の導入から、CISetup の **接続テスト成功** まで。

| 含む | 含まない |
|------|----------|
| Git、JDK 21、.NET SDK 8、Jenkins LTS | プロジェクトごとの Git URL 入力 |
| 管理者、API トークン、待受ポート | Teams Webhook の作成 |
| 同一 PC のビルドエージェント | 「セットアップを実行」とテストビルド |

サンドボックスは、この手順の確認に使った検証環境です。実行場所は Jenkins サーバーです。

---

## 完了条件

設定用 PC の CISetup で、次の 2 点が取れれば完了です。

1. **接続テスト** が「Jenkins への接続に成功しました。」になる
2. 同一 PC をエージェントにする場合、`windows-agent` がオンラインになる

環境スキャンでは Git、.NET SDK 8、Java 21 を検出します。war を直接起動するため、Jenkins の Windows サービスは未検出のままで問題ありません。

---

## 構成

```
設定 PC（CISetup）
    │  http://<サーバー>:8080/
    ▼
Jenkins サーバー
    ├─ Jenkins LTS（ポート 8080）
    └─ windows-agent（同一 PC の場合）
         ├─ Git
         ├─ .NET SDK 8
         └─ JDK 21
```

ビルドエージェントを別 PC にする場合、サーバー側は `-SkipAgent` で Jenkins だけを入れます。

---

<!-- _class: lead -->

# 1. サーバーで実行する

---

## 実行コマンド

Jenkins サーバーに管理者でログオンし、リポジトリのスクリプトを実行します。`-JenkinsUrl` は、CISetup を開く PC から届く URL です。

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl http://ci-server:8080/
```

ウィザードで作成済みの Jenkins がある場合は、その管理者パスワードを渡します。

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl http://ci-server:8080/ `
  -AdminPassword "<既存の管理者パスワード>"
```

---

<!-- _class: small -->

## パラメーター

| パラメーター | 既定 | 意味 |
|--------------|------|------|
| `-JenkinsUrl` | `http://localhost:8080/` | CISetup に入れる URL |
| `-AdminUser` | `admin` | 管理者 |
| `-AdminPassword` | `cisetup-admin` | 新規時のパスワード |
| `-JenkinsHome` | `C:\jenkins` | `JENKINS_HOME` |
| `-Port` | `8080` | HTTP ポート |
| `-AgentName` | `windows-agent` | エージェント名 |
| `-AgentWorkDir` | `C:\Jenkins\workspace` | 作業ディレクトリ |
| `-SkipAgent` | オフ | Jenkins だけ入れる |
| `-ProjectPath` | 空 | 接続情報の保存先プロジェクト |
| `-FileShare` | 空 | 共有フォルダルート |
| `-CISetupExe` | 空 | 完了後に起動する exe |

2 回目以降、パスワード未指定なら `C:\jenkins\cisetup-admin-password.txt` を読みます。

---

## スクリプトが行うこと

1. Git for Windows 2.47.1 を入れる
2. エージェント兼用のとき、.NET SDK 8 を `C:\dotnet` に入れ、マシンの PATH へ追加する
3. Temurin JDK 21 を `C:\jdk21` に入れ、PATH の先頭にする
4. `jenkins.war` を `C:\jenkins.war` に置く
5. ウィザードを出さずに Jenkins を起動する
6. 管理者、Jenkins URL、待受ポート 50000 を設定する
7. TCP 8080 を許可する。エージェントを入れる場合は TCP 50000 も許可する
8. CISetup 用プラグインを入れる
9. エージェントを登録し、Java 21 で起動する
10. API トークンを発行し、`C:\jenkins\cisetup-api-token.txt` に保存する

---

## 入れるプラグイン

CISetup が使う 6 つです。

- `workflow-aggregator`
- `git`
- `credentials-binding`
- `plain-credentials`
- `parameterized-trigger`
- `naginator`

インストール後に再起動が必要なら、スクリプトが Jenkins を再起動します。

---

<!-- _class: lead -->

# 2. CISetup に入力する

---

## 画面の値

| 項目 | 値 |
|------|-----|
| Jenkins URL | `-JenkinsUrl` の値 |
| ユーザー名 | `admin` |
| API Token | 完了メッセージ、または `cisetup-api-token.txt` |
| リポジトリ URL | 対象プロジェクトの Git URL |
| ブランチ | 対象ブランチ（例: `main`） |
| 共有フォルダルート | ローカルパス、または `\\fileserver\ci` |

Git の資格情報と Teams Webhook は、使うときだけ入力します。空でも接続テストは成功します。

---

## 再起動したあと

Jenkins とエージェントは、開いたコマンドウィンドウで動きます。ウィンドウを閉じると停止します。サーバー再起動後は、次を実行します。

```text
C:\jenkins\start-jenkins.bat
C:\Jenkins\workspace\start-agent.bat
```

`-SkipAgent` のときは、上の Jenkins だけを起動します。

---

## エージェントを別 PC にする

サーバー:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl http://ci-server:8080/ -SkipAgent
```

エージェント PC には JDK 21、.NET SDK 8、Git を入れます。CISetup の「Jenkins サーバーを初期設定」が表示する起動コマンドを、`cmd` から Java 21 で実行します。

```bat
java -jar agent.jar -url http://ci-server:8080/ -secret <secret> -name windows-agent -workDir C:\Jenkins\workspace
```

PowerShell から同じ引数を渡すと、`-url` と `-secret` が落ちます。

---

<!-- _class: lead -->

# 3. 検証とレビュー

---

## サンドボックスで確認できたこと

検証環境は Windows Sandbox、Jenkins は 2.580.2 です。確認したのは手作業の手順で、このスクリプトそのものは未実行です。

| 事実 | スクリプトへの反映 |
|------|-------------------|
| Java 17 では起動しない。Java 21 または 25 が必要 | JDK 21 を入れる |
| winget は使えない環境がある | 公式の配布物を直接取得する |
| `dotnet-install.ps1` の PATH はそのプロセスだけ | マシンの PATH に `C:\dotnet` を追加する |
| エージェント待受ポートは初期状態で無効 | 50000 に設定する |
| エージェントは Java 21 で `cmd` から起動する | `start-agent.bat` を `cmd` で起動する |
| 接続テストは管理者と API トークンで成功する | トークンをファイルに保存する |

---

## レビューで残っている点

本番のサーバーで実行する前に、次を別途決めてください。

1. **スクリプト未実行。** ノード作成は Groovy で行う実装です。画面の「Jenkins サーバーを初期設定」は `computer/doCreateItem` が HTTP 400 になることを確認済みで、Groovy 経路は未確認です。
2. **Windows サービスではない。** ログオフや再起動で止まります。常時起動にする場合は、起動スクリプトのサービス化が必要です。
3. **初期パスワードが `cisetup-admin`。** パスワードは `init.groovy` と `cisetup-admin-password.txt`、API トークンは `cisetup-api-token.txt`、エージェント secret は `start-agent.bat` に平文で残ります。
4. **版の固定が揃っていない。** Git は 2.47.1、JDK と Jenkins は取得時点の最新です。
5. **既存の導入資料と差分がある。** `docs/CISetup-CI-Guide.marp.md` は Java 17 と Jenkins MSI です。現行 LTS の実測とは一致しません。

---

<!-- _class: lead -->

# 完了

接続テストが成功すれば、CISetup からこの Jenkins を使えます。

次は、対象プロジェクトの Git URL を入れて「セットアップを実行」です。
