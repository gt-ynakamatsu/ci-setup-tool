# CISetup Configure（開発者向け）

社内 CI（Jenkins / Git / Teams / ファイルサーバー）の設定を GUI で行うツール。
Python 製で、配布は **単一 exe**（利用者は Python 不要）。

> 配布された exe を使うだけの方は、zip 内の `README.md`（= [docs/README-dist.md](docs/README-dist.md)）を参照してください。

---

## 1. 必要なもの

- Windows または Linux
- Python 3.10 以上（GUI は標準の `tkinter` を使用）

```powershell
cd C:\workspace\tools\WindowsApp\cisetup
python -m pip install -r requirements-dev.txt   # テスト/ビルド用
```

`requirements.txt` は実行時依存（標準ライブラリのみのため通常は空〜最小）、
`requirements-dev.txt` は pytest / pytest-cov / PyInstaller などの開発用です。

### Linux での実行

CISetup 本体は標準ライブラリ + `tkinter` のみで実装されており、ソースから起動する分には
Windows 専用の依存はありません（Windows 固有 API 呼び出しは `sys.platform` でガード済み）。

```bash
sudo apt install python3-tk   # tkinter が同梱されていないディストリビューションの場合
python3 configure.py
```

配布用バイナリ（PyInstaller）も同じ `cisetup.spec` から Linux 上でビルドできますが、
PyInstaller は実行環境向けのバイナリしか生成できない（クロスコンパイル不可）ため、
Linux 用バイナイルが必要な場合は **Linux 上で** `python tools/rebuild_exe.py` を実行してください
（`dist/CISetup`（拡張子なし）が生成されます）。

**生成される CI パイプライン（`ci-*.ps1` + `Jenkinsfile`）も Windows / Linux 両対応です。**
`Jenkinsfile` はエージェントが Windows か Linux/Unix かを実行時に `isUnix()` で判定し、
Windows では `powershell`（Windows PowerShell 5.1）、Linux では `pwsh`（PowerShell 7+）で
同じ `ci-*.ps1` を実行します。Linux エージェントには以下が必要です。

- PowerShell 7 以降（`pwsh`）… [公式手順](https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-linux) でインストール
- `dotnet` SDK（dotnet プロファイルの場合。custom プロファイルなら `build.buildCommand` 等が
  必要とするツールチェイン）

Windows Forms / WPF など Windows 専用フレームワークを使う .NET プロジェクトは、そもそも
Linux 上でビルド・実行できないため対象外です（対象プロジェクトが cross-platform であることが前提）。

---

## 2. ディレクトリ構成

ルートには「エントリ・起動・ビルド設定の正本」だけを置き、補助スクリプトは `tools/`、
ドキュメントは `docs/` に集約しています。生成物（exe・zip・キャッシュ）は `dist/` ほかに出力され、`.gitignore` 対象です。

```
cisetup/
├── configure.py             … エントリポイント（GUI / --open / --bootstrap / --help）
├── cisetup.spec          … PyInstaller 設定（exe に bundled_templates を同梱）
├── start_configure.bat      … 開発用ランチャ(bat)。python 優先・無ければ exe
├── Configure.ps1            … 開発用ランチャ(PowerShell)。configure.py を起動
├── Setup-Project.bat        … 初回セットアップ（CI 配置＋GUI）。配布 zip にも同梱
├── requirements.txt         … 実行時依存（標準ライブラリ中心）
├── requirements-dev.txt     … 開発時依存（pytest / coverage / pyflakes / pyinstaller）
├── .gitignore               … 生成物（dist/ build/ htmlcov/ __pycache__ 等）を除外
├── .coveragerc              … カバレッジ計測設定（source=cisetup, branch）
│
├── cisetup/           … アプリ本体（package）
│   ├── gui/                 … Tkinter GUI（Mixin 分割）
│   │   ├── app.py           … シェル（ConfigureApp 合成・UI 配線）
│   │   ├── deps.py          … 外部依存集約（Jenkins/Git/Teams 等・テスト patch 用）
│   │   ├── fields.py / form_sync.py / repository.py / presets.py / file_picks.py / dialogs.py
│   │   ├── steps/           … intro.py（冒頭）/ workflow.py（①〜⑥）
│   │   ├── details/panels.py … 詳細設定 Expander
│   │   ├── actions/ops.py   … 保存・Jenkins・Git・セットアップ実行
│   │   ├── layout.py        … 配色・共通ウィジェット
│   │   ├── multi_value_field.py … ＋/− 複数入力欄
│   │   ├── commit_dialog.py … コミットメッセージ入力
│   │   └── tooltip.py       … 「?」ヘルプアイコンと吹き出し
│   ├── models.py            … 設定/シークレットのデータモデル + JSON 変換（camelCase）
│   ├── config_repository.py … 設定の保存・読込（標準/旧レイアウト対応）
│   ├── paths.py             … リポジトリルート探索・レイアウト判定
│   ├── project_setup.py     … .sln 自動検出・CI ファイル配置
│   ├── template_store.py    … bundled_templates の展開（exe では _MEIPASS から）
│   ├── jenkinsfile_generator.py … Jenkinsfile 生成
│   ├── ci_preset_catalog.py … ビルドプリセット定義（.NET / Python など）
│   ├── jenkins_client.py    … Jenkins API（接続/認証情報/ジョブ/エージェント/ビルド）
│   ├── teams_service.py     … Teams 通知カードの生成・送信
│   ├── git_service.py       … Git push・secrets ステージ検出
│   ├── local_ci.py          … ローカルでビルド＆テスト（ci-build/ci-test を実行・git 操作なし）
│   ├── environment_scan.py  … 開発環境スキャン（git/java 等）
│   ├── recent_project.py    … 直近プロジェクトの記憶
│   ├── help_texts.py        … GUI ヘルプ文言
│   ├── app_paths.py         … 設定保存先などのアプリパス
│   └── process_util.py      … サブプロセス実行ユーティリティ
│
├── bundled_templates/       … CI テンプレート正本（exe に同梱）
│   ├── Jenkinsfile.template
│   ├── JenkinsJob.config.template.xml
│   ├── cisetup.config.example.json / cisetup.secrets.local.example.json
│   └── scripts/             … Jenkins 各ステージの PowerShell（ci-*.ps1）+ TEAMS-WORKFLOW.md
│
├── assets/                  … アプリアイコン（exe・ウィンドウ用）
│   ├── icon.ico             … exe / ウィンドウアイコン（マルチサイズ）
│   ├── icon.png             … 透過 PNG（フォールバック用）
│   └── icon_source.png      … 生成元画像（差し替え時はこれを置換）
│
├── tools/                   … ビルド・配布・保守スクリプト（開発者専用）
│   ├── Build-Exe.bat        … exe ビルド（rebuild_exe.py を実行）
│   ├── rebuild_exe.py       … PyInstaller で dist\CISetup.exe を生成
│   ├── Package-Distribution.ps1 … exe ビルド + 社内配布 zip 作成
│   ├── make_icon.py         … icon_source.png から icon.png / icon.ico を生成
│   ├── verify_icon.py       … アイコン整合チェック（任意）
│   └── smoke_test.py        … JSON 互換などの高速スモークテスト
│
├── tests/                   … pytest 一式（conftest.py + test_*.py）
├── docs/                    … ドキュメント
│   ├── README-dist.md       … 配布 zip に同梱する利用者向け README
│   ├── CI-GUIDE.md          … CI 構築手順書
│   ├── CI-USERS-GUIDE.md    … リポジトリ利用者向け（push すると何が起きるか）
│   ├── DESIGN.md            … 設計仕様書（アーキテクチャ・Mermaid 図）
│   ├── GUI.md               … GUI 操作
│   └── CISetup-CI-Guide.marp.md … Marp プレゼン資料
└── dist/                    … 【生成物】CISetup.exe + 配布 zip
```

### ルート直下ファイルの役割

| ファイル | 区分 | 役割 |
|----------|------|------|
| `configure.py` | エントリ | GUI / CLI の起点。`cisetup.spec` が exe 化する対象 |
| `cisetup.spec` | ビルド | PyInstaller 設定。`tools/rebuild_exe.py` が参照 |
| `start_configure.bat` | 開発ランチャ | python 優先で GUI 起動、無ければ同じ場所の exe |
| `Configure.ps1` | 開発ランチャ | PowerShell から `configure.py` を起動 |
| `Setup-Project.bat` | 配布＋開発 | 初回セットアップ。**配布 zip に同梱**され exe の隣でも動く |
| `requirements.txt` | 依存 | 実行時依存 |
| `requirements-dev.txt` | 依存 | 開発・テスト・ビルド用 |
| `.gitignore` / `.coveragerc` | 設定 | 除外設定 / カバレッジ設定 |

> 補足: 4 つのランチャ（`configure.py`・`Configure.ps1`・`start_configure.bat`・`Setup-Project.bat`）は
> いずれも「自分と同じフォルダの `configure.py` / exe」を探す設計のため、ルートに据え置いています（移動するとビルド・配布・起動が壊れます）。

---

## 3. 開発フロー

```powershell
# GUI を起動して動作確認
python configure.py
python configure.py --open C:\work\MyApp

# テスト
python -m pytest tests -q

# カバレッジ（ターミナル + htmlcov/index.html）
python -m pytest tests --cov=cisetup --cov-report=term-missing --cov-report=html

# 静的解析（GUI パッケージ）
python -m pyflakes cisetup/gui

# スモークテスト（C# 互換の素早い確認）
python tools/smoke_test.py
```

### exe の再ビルド（重要）

`cisetup/` ・ `configure.py` ・ `cisetup.spec` ・ `bundled_templates/` を変更したら、
**作業完了前に必ず exe を再ビルド** してください。古い exe は `tests/test_exe_freshness.py` が検出して失敗させます。

```powershell
python tools\rebuild_exe.py
# または
.\tools\Build-Exe.bat
```

---

## 4. 配布 zip の作成

```powershell
.\tools\Package-Distribution.ps1            # 既定バージョン 1.0.0
.\tools\Package-Distribution.ps1 -Version 1.1.0
# => dist\CISetup-<Version>.zip
```

zip の中身（利用者が受け取るもの）:

```
CISetup-<Version>/
├── CISetup.exe   ← これだけで GUI 起動（Python 不要）
├── Setup-Project.bat          ← CI 配置 + GUI 起動（任意）
├── README.md                  ← 利用者向け（docs/README-dist.md）
└── docs/                      ← 手順書
```

`bundled_templates/` は exe に埋め込まれるため、zip には個別同梱しません。

---

## 5. コマンドライン（exe / configure.py 共通）

```
configure.py                      # GUI
configure.py --open <folder>      # フォルダを開いて GUI
configure.py --bootstrap <folder> # CI ファイルのみ配置（GUI なし）
configure.py --help
```

---

## 6. ドキュメント索引（どのファイルに何が書いてあるか）

### 6.1 ファイル別の内容

| ファイル | 対象読者 | 主な内容 | こんなときに見る |
|----------|----------|----------|------------------|
| [README.md](README.md)（本ファイル） | 開発者 | リポジトリ構成・開発フロー・exe ビルド・配布手順・このドキュメント索引 | コードを直す/exe を作る/zip を配る |
| [docs/DESIGN.md](docs/DESIGN.md) | 開発者 | **設計仕様書**。全体像・データモデル・各処理フロー（Mermaid）・CI パイプライン挙動・ビルド/配布を網羅 | 設計を把握する/同等品を再実装する |
| [docs/README-dist.md](docs/README-dist.md) | 利用者（exe を使う人） | exe の起動方法・同梱物・初回セットアップ・困ったとき | 配布された exe をとりあえず動かしたい |
| [docs/GUI.md](docs/GUI.md) | 利用者・開発者 | 設定 GUI の起動方法・操作の流れ・CLI 引数 | GUI の使い方をざっと知りたい |
| [docs/CI-GUIDE.md](docs/CI-GUIDE.md) | 構築担当者 | **CI 構築の完全手順書**。ファイルサーバー/Teams/Jenkins/エージェント/プロジェクト設定、GATE A〜D、トラブルシューティング、設定値↔JSON 対応 | CI を一から構築する/エラーで詰まった |
| [docs/CI-USERS-GUIDE.md](docs/CI-USERS-GUIDE.md) | リポジトリ利用者 | push すると何が起きるか・Teams 通知・成果物の見方（CISetup 開発者向けではない） | CI が入ったリポジトリで開発するだけの人 |
| [docs/CISetup-CI-Guide.marp.md](docs/CISetup-CI-Guide.marp.md) | 構築担当者・説明者 | CI-GUIDE.md をスライド化した Marp プレゼン資料（全体像の説明・勉強会向け） | 全体像を俯瞰したい/人に説明する |
| [bundled_templates/scripts/TEAMS-WORKFLOW.md](bundled_templates/scripts/TEAMS-WORKFLOW.md) | 構築担当者 | Teams 通知（Power Automate ワークフロー）の設定とカードの形式 | Teams 通知を設定/カスタムしたい |

> exe 本体や各設定項目の意味は、GUI 内の各項目「?」ヘルプ（吹き出し）にも記載しています。

### 6.2 目的別の参照先（知りたいこと → どのファイル）

| 知りたいこと | 参照先 |
|--------------|--------|
| CI 全体の仕組み・構成図 | CI-GUIDE.md「1. 全体像」/ marp「1. CI の全体像」 |
| 構築の最短手順（チェックリスト） | CI-GUIDE.md の GATE A〜D |
| ファイルサーバー（共有フォルダ）の準備 | CI-GUIDE.md「4. Phase 1」 |
| Teams Webhook の取得・通知設定 | CI-GUIDE.md「5. Phase 2」/ TEAMS-WORKFLOW.md |
| Jenkins のインストール・初回セットアップ | CI-GUIDE.md「6.」 |
| **Jenkins URL がどの画面の URL か** | CI-GUIDE.md「6.9」の注記 / GUI の ⑤ ヘルプ |
| API Token の発行方法 | CI-GUIDE.md「6.9」 |
| ポート番号の変更（8086 など） | CI-GUIDE.md「6.10」 |
| ビルドエージェントの起動・サービス化 | CI-GUIDE.md「8.」 |
| 設定 GUI の各項目の意味・保存先 | GUI 内ヘルプ / CI-GUIDE.md「9. 設定値↔JSON 対応」 |
| 保存先・閲覧 URL を「複数」設定する（＋/− 行追加） | CI-GUIDE.md「③ 保存先」の注記 / GUI の ③・④ の各「＋」ボタン |
| 個人 ID（OneDrive/Git ユーザー名）を Git に push しない運用 | CI-GUIDE.md「9.」の該当注記（書き込み先は `cisetup.local.json`、CI 側は `CI_FILE_SERVER`） |
| 書き込み先設定がワークスペースのワイプで消える対策（同一 PC でエージェント運用時） | GUI ③「Jenkins エージェントのワークスペースパス」を設定 → 保存時に兄弟パスへ自動配置（CI-GUIDE.md「③ 保存先」の注記） |
| 別 PC・共有アクセス不可のエージェントへ書き込み先を届ける | GUI ④「書き込み先を Jenkins のグローバル環境変数 (CI_FILE_SERVER) として登録する」を ON →「Jenkinsに反映」で Jenkins 本体に自動登録（単一値・管理者権限要） |
| エラー・トラブルの対処 | CI-GUIDE.md「15. トラブルシューティング」 |
| 配布された exe の使い方（利用者向け） | docs/README-dist.md |
| コードを直してから exe を再ビルド | README.md「3. 開発フロー」 |
