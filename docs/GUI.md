# CISetup 設定 GUI

## 起動

| 項目 | 内容 |
|------|------|
| **配布（推奨）** | `CISetup.exe` をダブルクリック（Python 不要） |
| 開発 | `python configure.py` または `start_configure.bat` |
| 初回セットアップ | `Setup-Project.bat [プロジェクトフォルダ]` |
| ビルド | `python tools/rebuild_exe.py` または `tools\Build-Exe.bat` → `dist\CISetup.exe` |
| 配布 zip | `tools\Package-Distribution.ps1` |

**開発ルール:** GUI・`configure.py`・`bundled_templates` を直したら、作業完了前に必ず exe を再ビルドする（`test_exe_freshness.py` で古い exe を検出）。

### コマンドライン

```
python configure.py                  # GUI
python configure.py --open <folder>  # フォルダを開いて GUI
python configure.py --bootstrap <folder>  # CI ファイルのみ配置
python configure.py --help
```

## 操作の流れ

1. プロジェクトフォルダを指定
2. ①〜⑤ を入力（Git → **保存先** → Teams → Jenkins）
3. **セットアップを実行** — チェックした処理だけを上から順に実行

各項目の意味・保存先はラベル横の **「?」ヘルプアイコン**（ホバーで吹き出し）に表示されます。文言は「【何を】【なぜ】【どこで使う】…」形式です。

### 開発者向け（ソース構成）

GUI は `cisetup/gui/app.py` が薄いシェルで、`ConfigureApp` は Mixin を多重継承しています。
画面フローは `steps/workflow.py`、副作用のある操作は `actions/ops.py`、外部 API 呼び出しは `deps.py` に集約されています。
詳細は [DESIGN.md の 5.2 / 8 章](DESIGN.md) を参照。

### ⑥ セットアップを実行のチェックボックス

| チェック | 内容 |
|----------|------|
| 1. 設定を保存 | `cisetup.config.json` / `Jenkinsfile` / `scripts` を再生成して保存（既定 ON） |
| ローカルでビルド＆テスト（push せず現在のコードを検証） | 配置済み `CISetup\scripts\ci-build.ps1` → `ci-test.ps1` を**この PC でそのまま実行**。fetch / pull / push といった **git 操作は一切なし**。push 前に手元のコードを検証する用途（既定 ON・ログは「ローカルビルド＆テストの実行ログ」欄に表示） |
| 2. Jenkins に反映 | `apply_settings` でジョブ定義を Jenkins に登録（既定 ON） |
| 3. Git push | CI 関連ファイルのみ commit / push（secrets/local は除外。既定 ON） |
| 4. テストビルドを実行 | Jenkins が**リモート Git のコード**をビルド（既定 ON） |
| テストビルドで成果物 zip も作成・保存する | テストビルド時に `dotnet publish` で **framework-dependent 単一 `.exe`**（+ zip）も作成・保存（既定 ON。ランタイムは同梱しない） |

> **「テストビルド」と「ローカルでビルド＆テスト」の違い**
> 「テストビルド」は Jenkins がリモート Git から取得したコードをビルドするため、push していないローカルの変更は反映されません。
> 「ローカルでビルド＆テスト」は **push せずに現在のローカルコード**を、配置済み CI スクリプトで検証します（git 操作なし）。先に「設定を保存」しておくと最新スクリプトで検証できます。

内部の実行順は常に **保存 → ローカル → Jenkins 反映 → Git push → テストビルド**（チェックしたものだけ）。ローカルはビルドが失敗するとテストを実行しません。

> **⑤ Jenkins URL は「どの画面の URL?」** … Jenkins にログインした直後の **ホーム画面（ダッシュボード）** を開いたときの、**ブラウザのアドレスバーの URL**（`http://ホスト:ポート/`）です。
> 左上の「Jenkins」ロゴをクリックするとホーム画面に戻れます。`/job/...` は含めず、`Manage Jenkins → System` の「Jenkins URL」と同じ値。別 PC からは `localhost` ではなくホスト名/IP を使います。詳細は [CI-GUIDE.md の 6.9](CI-GUIDE.md)。

詳細は [CI-GUIDE.md](CI-GUIDE.md) と [CISetup-CI-Guide.marp.md](CISetup-CI-Guide.marp.md) を参照。どのファイルに何が書いてあるかは [README.md の「ドキュメント索引」](../README.md) を参照。
