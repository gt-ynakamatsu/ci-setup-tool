---
marp: true
theme: default
paginate: true
size: 16:9
title: CISetup CI 導入・運用ガイド
description: Jenkins 導入から configure.py、Teams Webhook まで
style: |
  section { font-size: 28px; }
  section.lead h1 { font-size: 52px; }
  section.lead h2 { font-size: 32px; color: #555; }
  h2 { color: #0078D4; }
  table { font-size: 22px; }
  code { font-size: 20px; }
  blockquote { font-size: 24px; border-left: 4px solid #0078D4; }
---

<!-- _class: lead -->

# CISetup CI
## 導入・運用ガイド

Jenkins 導入 → Teams 通知 → アプリ設定まで

`configure.py` / Jenkins 2.555.x LTS

---

## この資料で学べること

| 章 | 内容 |
|----|------|
| 1 | CI の全体像と自動化内容 |
| 2 | 事前準備（ファイルサーバー・Teams） |
| 3 | **Jenkins Windows インストール**（MSI） |
| 4 | Jenkins Web 初回セットアップ |
| 5 | **CISetup アプリ** の使い方（①〜⑨） |
| 6 | Windows ビルドエージェント |
| 7 | 動作確認・日常運用 |
| 8 | トラブルシューティング |

---

<!-- _class: lead -->

# 1. CI の全体像

---

## 何が自動化されるか

| タイミング | 処理 |
|-----------|------|
| 毎日 0:00（cron 変更可） | 社内 Git から最新ソースを pull |
| ビルド **成功** | zip をファイルサーバーへ保存 → Teams 通知 |
| ビルド **失敗** | ログをファイルサーバーへ保存 → Teams 通知 |

対象: **.NET デスクトップアプリ**（WPF / WinForms 等）

---

## システム構成

```
開発 PC (Visual Studio)
    │ git push
    ▼
社内 Git ──pull──► Jenkins サーバー
                        │
                        ▼
                 Windows エージェント（ビルド実行）
                   ├─ 成功 → ファイルサーバー releases + Teams
                   └─ 失敗 → ファイルサーバー logs   + Teams

設定 PC: configure.py → Jenkins / Git へ反映
```

---

## 必要なマシンとソフト

| マシン | 役割 | 必要なもの |
|--------|------|-----------|
| Jenkins サーバー | CI 司令塔 | Java 17+, Jenkins LTS |
| Windows エージェント | ビルド実行 | Java 11+, .NET SDK 8, Git |
| ファイルサーバー | 成果物保存 | UNC 共有 |
| 設定 PC | 初回設定 | `configure.py` のみ |
| 開発 PC | コーディング | Visual Studio（CI には不要） |

---

## 3 種類のアカウント（混同注意）

| 種類 | いつ作る | 用途 |
|------|---------|------|
| **Windows サービスユーザー** | MSI インストール時 | Jenkins プロセスを OS で動かす |
| **Jenkins 管理者** | Web 初回セットアップ | Jenkins 画面ログイン |
| **API Token** | ログイン後 | CISetup 設定アプリ が API 呼び出し |

MSI の **Service Logon Credentials** ≠ Jenkins の admin パスワード

---

## 初回構築の流れ（7 Phase）

| Phase | 内容 | 頻度 |
|-------|------|------|
| 1 | ファイルサーバー | 初回のみ |
| 2 | Teams Webhook | 初回のみ |
| 3 | Jenkins MSI + Web セットアップ | 初回のみ |
| 4 | 設定アプリで Jenkins 自動設定 | 初回のみ |
| 5 | エージェント PC セットアップ | 初回のみ |
| 6 | **プロジェクト CI 設定（設定アプリ）** | **PJ ごと** |
| 7 | LDAP / AD（将来） | 必要時 |

---

<!-- _class: lead -->

# 2. 事前準備

---

## Phase 1 — ファイルサーバー

1. 共有フォルダを作成  
   例: `\\fileserver\ci`
2. **エージェント実行アカウント** に変更権限を付与
3. パスをメモ（後で exe ⑤⑧ に入力）

```
\\fileserver\ci\
└── MyApp\
    ├── releases\20260615\MyApp-42-win-x64.exe
    ├── releases\20260615\MyApp-42-win-x64.zip
    └── logs\20260615\build-42.log
```

---

<!-- _class: lead -->

# Teams Webhook 設定

---

## Teams — ワークフローの選び方

1. 通知先 **Teams チャンネル** を開く
2. チャンネル名横 **「…」** → **ワークフロー**
3. テンプレートから選択:

### ✅ 選ぶもの

**「Webhook アラートをチャネルに送信する」**

### ❌ 選ばないもの

特定ユーザーから / チャットに送信 等（CI 通知向きではない）

---

## Teams — Webhook URL の取得

1. ワークフロー名を付ける（例: `CISetup CI`）
2. 作成完了後、**Webhook URL** をコピー
3. 安全な場所に保管

> URL 自体が **秘密情報**（パスワード相当）  
> Git リポジトリやチャットに **載せない**

保存先: 設定アプリが `cisetup.secrets.local.json` に保存（Git 除外）

---

## Teams — 動作確認（PowerShell）

```powershell
$url = "ここに Webhook URL"
$body = '{"title":"CI テスト","text":"Webhook 動作確認です"}'
Invoke-RestMethod -Uri $url -Method Post `
  -Body $body -ContentType "application/json; charset=utf-8"
```

チャンネルにメッセージが届けば OK

設定アプリの **⑦ Teams テスト通知** ボタンでも同様に確認可能

---

## Teams — 通知の形式（CI ビルド時）

Power Automate ワークフロー向け JSON:

```json
{
  "title": "MyApp - complete",
  "text": "**結果:** complete\n**ビルド番号:** 42\n..."
}
```

- 成功: `complete`
- 失敗: `error` + ログ保存先の案内

---

<!-- _class: lead -->

# 3. Jenkins インストール（Windows）

Jenkins 2.555.x LTS / MSI

---

## Step 1 — Java 17 のインストール

Jenkins LTS は **Java 17 以上** が必要

1. [Adoptium Temurin 17](https://adoptium.net/) をインストール
2. 確認:

```powershell
java -version
# openjdk version "17.x.x"
```

`JAVA_HOME` と Path への追加を推奨

---

## Step 2 — Jenkins MSI インストール

1. [jenkins.io/download](https://www.jenkins.io/download/) → **Windows (LTS)** MSI
2. インストーラを **管理者として実行**
3. デフォルト設定で Next 進行
4. **Service Logon Credentials** 画面で停止 → 次スライド

または:

```powershell
winget install Jenkins.Jenkins
```

---

## Service Logon Credentials とは

| 入力項目 | 意味 |
|---------|------|
| Logon Type | Jenkins **Windows サービス** の実行ユーザー |
| Account | Windows ユーザー名（例: `.\jenkins`） |
| Password | その Windows ユーザーの **パスワード** |
| Test Credentials | サービスとして起動できるか検証 |

### ここでは入力しない

- Jenkins Web の admin パスワード
- LDAP アカウント
- API Token

---

## 推奨 — Jenkins 専用ローカルユーザー

管理者 PowerShell:

```powershell
$password = Read-Host "パスワード" -AsSecureString
New-LocalUser -Name "jenkins" -Password $password `
  -FullName "Jenkins Service User" -PasswordNeverExpires
Add-LocalGroupMember -Group "Users" -Member "jenkins"
```

MSI 入力:

| 項目 | 値 |
|------|-----|
| Logon Type | Run service as **local or domain user** |
| Account | `.\jenkins` |
| Password | 上で設定したパスワード |

→ **Test Credentials** が成功してから Next

---

## Test Credentials エラー対処

### 0x8007052e — Error logging on

- ユーザー名 / パスワードが間違い
- **Windows Hello PIN ではなく** アカウントパスワードを使用
- ローカルユーザーは `.\jenkins` 形式

### logon as a service 権限不足

1. `Win + R` → `secpol.msc`
2. ローカル ポリシー → ユーザー権利の割り当て
3. **サービスとしてログオン** → ユーザーを追加
4. Test Credentials を再実行

---

## 検証環境のみ — LocalSystem

| | |
|--|--|
| 選択 | Run service as **LocalSystem** |
| メリット | 権限エラーで詰まりにくい |
| デメリット | 権限が強すぎる / UNC アクセスで問題 |
| 用途 | **ローカル検証のみ**（本番非推奨） |

---

## ポート変更（例: 8086）

8080 が競合する場合:

1. `Stop-Service Jenkins`
2. `C:\Program Files\Jenkins\jenkins.xml` を編集
3. `--httpPort=8080` → `--httpPort=8086`
4. `Start-Service Jenkins`
5. **すべての URL を 8086 に統一**
   - Jenkins System 設定
   - CISetup 設定アプリ
   - エージェント起動コマンド

---

<!-- _class: lead -->

# 4. Jenkins Web 初回セットアップ

---

## Unlock Jenkins（初回のみ）

1. ブラウザ: `http://localhost:8086/`（ポートに合わせる）
2. **Unlock Jenkins** 画面
3. 初期パスワード:

```powershell
Get-Content "C:\ProgramData\Jenkins\.jenkins\secrets\initialAdminPassword"
```

4. **Install suggested plugins**
5. **Create First Admin User**（admin 等 — メモ）
6. **Jenkins URL** 設定
7. **Start using Jenkins**

---

## API Token の発行（exe 用）

1. Jenkins に admin でログイン
2. 右上 **ユーザー名** → **Configure**
3. **API Token** → **Add new Token**
4. 生成 → **コピー**（再表示不可）

設定アプリ **① Jenkins 接続** に入力:

| 項目 | 例 |
|------|-----|
| Jenkins URL | `http://localhost:8086` |
| ユーザー名 | `admin` |
| API Token | 発行した Token |

---

## タイムゾーン設定

**Manage Jenkins** → **System** → タイムゾーン

```
Asia/Tokyo
```

cron `0 0 * * *`（毎日 0:00）はこの TZ に従う

---

## 「サインイン」しか出ない場合

**Unlock Jenkins** が出ず **Sign in** のみ:

| 原因 | 対処 |
|------|------|
| 初回セットアップ済み | 既存 admin でログイン |
| JENKINS_HOME 残存 | 再インストールでデータ引き継ぎ |
| パスワード不明 | Security 一時無効化で再設定 |

JENKINS_HOME: `C:\ProgramData\Jenkins\.jenkins\`

検証環境のみ: フォルダ退避で Unlock に戻せる（本番禁止）

---

## Jenkins 起動エラー — config.xml

```
CannotResolveClassException: GlobalMatrixAuthorizationStrategy
```

**対処:** config.xml の authorizationStrategy を一時差し替え → 起動 → Matrix プラグイン導入

詳細は README「6.11」を参照

---

<!-- _class: lead -->

# 5. CISetup アプリの使い方

`configure.py`

---

## 配布物

```
dist\
└── CISetup-1.0.0.zip
    ├── start_configure.bat
    ├── configure.py
    └── bundled_templates\
```

- **Python 3.10+** が必要（pip 追加不要）
- `start_configure.bat` で GUI 起動
- **1 画面ウィザード** — 上から順に進める
- bat ファイル不要

---

## ウィザード全体像（①〜⑨）

| # | 内容 |
|---|------|
| ① | Jenkins 接続（URL / ユーザー / Token） |
| ② | Jenkins サーバー初期設定（**初回のみ**） |
| ③ | プロジェクトフォルダ選択 |
| ④ | プロジェクト設定（sln / csproj） |
| ⑤ | 格納パス（ファイルサーバー） |
| ⑥ | Git（URL / 認証） |
| ⑦ | Teams Webhook |
| ⑧ | CI ジョブ設定（cron 等） |
| ⑨ | **保存 → Jenkins 反映 → Git push** |

---

## ① Jenkins 接続

| 項目 | 入力例 |
|------|--------|
| Jenkins URL | `http://jenkins-server:8086` |
| ユーザー名 | `admin` |
| API Token | Jenkins で発行した Token |

→ **接続テスト** をクリック

**Jenkins URL** = ログイン直後の **ホーム画面（ダッシュボード）** を開いたときの **アドレスバーの URL**。
左上の「Jenkins」ロゴでホームに戻れる。`/job/...` は含めない。別 PC からは `localhost` でなくホスト名/IP。

401 エラー時: Token 再発行 / URL・ポート確認

---

## ② Jenkins サーバー初期設定（初回のみ）

Jenkins LTS インストール **後** に 1 回だけ実行

| 項目 | 例 |
|------|-----|
| エージェント名 | `windows-agent` |
| 作業フォルダ | `C:\Jenkins\workspace`（参照... で選択可） |

**Jenkins サーバーを初期設定** をクリック

---

## ② で 設定アプリが自動実行すること

| 処理 | 内容 |
|------|------|
| プラグイン | Pipeline, Git, Credentials Binding |
| Jenkins URL | システム設定を更新 |
| エージェント | Windows JNLP ノード登録 |
| 起動コマンド | エージェント PC 用コマンドを表示 |

`RESTART required` → Jenkins 再起動 → ② を再実行

**ファイルサーバー書き込みテスト** ボタンも利用可

---

## ③ プロジェクトフォルダ

1. **参照...** で `.sln` があるリポジトリルートを選択  
   またはパス入力 → **読み込み**
2. CI ファイルが **自動配置**
   - `Jenkinsfile`, `scripts/`, 設定例 等
3. プロジェクト名・sln・csproj が **自動検出**

---

## ④ プロジェクト設定

| 項目 | 説明 |
|------|------|
| プロジェクト名 | Teams 通知・保存フォルダ名 |
| ソリューション (.sln) | 参照... で選択可 |
| Publish 対象 (.csproj) | 参照... で選択可 |
| 成果物プレフィックス | 例: `MyApp` → `MyApp-42-win-x64.exe`（+ zip） |

多くは ③ の自動検出で入力済み

---

## ⑤ 格納パス

| 項目 | 説明 |
|------|------|
| 格納ベース (UNC) | 参照... で共有フォルダ選択可 |
| ログ / 成果物フォルダ名 | デフォルト `logs` / `releases` |
| 日付サブフォルダ | ON で `YYYYMMDD` フォルダ作成 |

**保存先プレビュー** で実際のパスを確認

---

## ⑥ Git

| 項目 | 例 |
|------|-----|
| リポジトリ URL | `https://git.example.com/team/MyApp.git` |
| ブランチ | `main` |
| Git Credential ID | `internal-git` |
| ユーザー名 / PAT | Jenkins Credentials に登録 |

---

## ⑦ Teams 通知

1. Phase 2 で取得した **Webhook URL** を貼り付け
2. **Teams テスト通知** をクリック
3. チャンネルに届くことを確認

→ ⑨ の「Jenkins に設定を反映」で Credential として Jenkins に登録

---

## ⑧ CI ジョブ設定

| 項目 | デフォルト例 |
|------|-------------|
| ジョブ名 | `CISetup-CI` |
| エージェントラベル | `windows` |
| cron | `0 0 * * *`（毎日 0:00） |
| CI_FILE_SERVER | `\\fileserver\ci`（参照... 可） |
| タイムゾーン | `Asia/Tokyo` |

---

## ⑨ 完了 — 3 ボタンを順に

```
① すべて保存
    ↓
② Jenkins に設定を反映
    ↓
③ Git push（CI ファイル）
```

| 保存先 | Git commit |
|--------|-----------|
| `cisetup.config.json` | ✅ する |
| `Jenkinsfile`, `scripts/` | ✅ する |
| `cisetup.secrets.local.json` | ❌ **しない** |

---

## Jenkins に設定を反映 — 自動登録内容

| 項目 | 内容 |
|------|------|
| Teams Credential | Webhook URL |
| Git Credential | ユーザー / PAT |
| Pipeline ジョブ | Git SCM + Jenkinsfile |

Jenkins 画面で **手動ジョブ作成は不要**

---

<!-- _class: lead -->

# 6. Windows ビルドエージェント

---

## エージェント PC — 必要ソフト

| ソフト | 確認コマンド |
|--------|-------------|
| Java 11+ | `java -version` |
| .NET SDK 8 | `dotnet --version` |
| Git | `git --version` |

作業フォルダ作成:

```powershell
New-Item -ItemType Directory -Force -Path "C:\Jenkins\workspace"
```

---

## エージェントの起動

1. exe ② 完了後、**起動コマンド** をコピー
2. **エージェント PC** の PowerShell で実行
3. Jenkins → **Manage Jenkins → Nodes**
4. `windows-agent` が **Online**（緑）を確認
5. ラベル **`windows`** が付いていること

---

## エージェント起動コマンド（例）

```powershell
Invoke-WebRequest -Uri "http://jenkins:8086/jnlpJars/agent.jar" -OutFile agent.jar
java -jar agent.jar -url "http://jenkins:8086/" `
  -secret <自動取得> -name "windows-agent" `
  -workDir "C:\Jenkins\workspace"
```

`<secret>` は 設定アプリが Jenkins から取得 — 手入力不要

---

<!-- _class: lead -->

# 7. 動作確認・日常運用

---

## 動作確認チェックリスト

- [ ] exe ① 接続テスト成功
- [ ] exe ⑦ Teams テスト通知成功
- [ ] エージェント Online（ラベル `windows`）
- [ ] Jenkins → **Build Now** 成功
- [ ] ファイルサーバーに zip / ログ
- [ ] Teams にビルド結果通知
- [ ] 翌日 0:00 定期ビルド（任意）

---

## 日常運用

| やりたいこと | 操作 |
|-------------|------|
| 設定変更 | 設定アプリ 編集 → ⑨ 保存 → 反映 → Git push |
| 手動ビルド | Jenkins → Build Now |
| 別 PJ 追加 | 設定アプリ ③〜⑨ を新 PJ で繰り返す |
| Webhook 変更 | 設定アプリ ⑦ 更新 → ⑨ 反映 |

---

## 別プロジェクトで使うとき

Jenkins 基盤（Phase 1〜5）は **共通**

**Phase 6（exe ③〜⑨）だけ** 繰り返す

- ジョブ名を PJ ごとに変更
- 1 Jenkins に複数 Pipeline ジョブが並ぶ

---

<!-- _class: lead -->

# 8. トラブルシューティング

---

## よくある問題 — Jenkins

| 症状 | 確認 |
|------|------|
| Test Credentials 失敗 | サービスとしてログオン権限 / パスワード |
| サインインのみ | 初回セットアップ済み — admin でログイン |
| 起動しない | config.xml / Matrix プラグイン |
| 設定アプリ 401 | API Token 再発行（パスワードではない） |
| 設定アプリ 403 | ユーザーに Admin / Credentials 権限 |

---

## よくある問題 — ビルド

| 症状 | 確認 |
|------|------|
| `windows` で待ったまま | エージェント Offline / ラベル不一致 |
| Git checkout 失敗 | Credential / ネットワーク |
| Teams 届かない | Webhook URL / ワークフロー ON |
| UNC 書き込み失敗 | エージェントアカウントの共有権限 |

---

## 将来 — LDAP / AD 認証

初回は Jenkins 内蔵ユーザー（admin）で OK

LDAP 導入時:

1. **LDAP Plugin** インストール
2. Security Realm → LDAP
3. **LDAP グループに Admin 権限を先に付与**
4. CISetup 設定アプリ は **API Token** で継続利用可能

Windows サービスユーザー `.\jenkins` とは無関係

---

<!-- _class: lead -->

# まとめ

---

## 初回構築 — 最短ルート

```
1. ファイルサーバー + Teams Webhook
2. Java 17 + Jenkins MSI（サービスユーザー設定）
3. Web 初回セットアップ + API Token
4. CISetup.exe ①②（Jenkins 基盤）
5. エージェント起動
6. CISetup.exe ③〜⑨（PJ 設定）
7. Build Now で確認
```

---

## 配布・参照

| リソース | 場所 |
|---------|------|
| 設定アプリ | `start_configure.bat` |
| 詳細手順書 | `README.md` |
| この資料 | `docs\CISetup-CI-Guide.marp.md` |

### 資料の PDF / HTML 出力

VS Code + **Marp for VS Code** 拡張機能  
または CLI: `marp docs/CISetup-CI-Guide.marp.md --pdf`

---

<!-- _class: lead -->

# ご清聴ありがとうございました

質問・不明点は README またはインフラ担当へ

**CISetup CI** — exe 1 つで CI 設定完結
