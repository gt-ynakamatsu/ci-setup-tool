# CISetup 設定 GUI

## 起動

| 項目 | 内容 |
|------|------|
| **配布（推奨）** | `CISetup.exe` をダブルクリック（Python 不要） |
| 開発 | `python configure.py` または `start_configure.bat` |
| 初回セットアップ | `Setup-Project.bat [プロジェクトフォルダ]` |
| ビルド | Windows: `python tools/rebuild_exe.py` / `tools\Build-Exe.bat` → `dist\CISetup.exe`。Linux から `.exe` を作る場合は `python tools/setup_wine_python.py` の後 `python tools/rebuild_exe.py --windows` |
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
3. **セットアップを実行** — 保存 → ローカルビルド＆テスト → Jenkins 反映 → テストビルド を順番に実行

各項目の意味・保存先はラベル横の **「?」ヘルプアイコン**（ホバーで吹き出し）に表示されます。文言は「【何を】【なぜ】【どこで使う】…」形式です。

### 開発者向け（ソース構成）

GUI は `cisetup/gui/app.py` が薄いシェルで、`ConfigureApp` は Mixin を多重継承しています。
画面フローは `steps/workflow.py`、副作用のある操作は `actions/ops.py`、外部 API 呼び出しは `deps.py` に集約されています。
詳細は [DESIGN.md の 5.2 / 8 章](DESIGN.md) を参照。

### ⑥ セットアップを実行

「セットアップを実行」は次を**いつも同じ順**で実行します（処理を選ぶチェックはありません）。

| 順 | 内容 |
|----|------|
| 1. 設定を保存 | `cisetup.config.json` / 作業用 `Jenkinsfile` / `scripts` を再生成して保存 |
| 2. ローカルでビルド＆テスト | 配置済み `CISetup\scripts\ci-build.ps1` → `ci-test.ps1` を**この PC でそのまま実行**。fetch / pull / push といった **git 操作は一切なし**（ログは「ローカルビルド＆テストの実行ログ」欄） |
| 3. Jenkins に反映 | `apply_settings` でジョブ定義（パイプライン一式）を Jenkins に登録 |
| 4. テストビルドを実行 | Jenkins が**顧客 Git のアプリソース**を checkout してビルド |
| （任意）テストビルドで成果物 zip も作成・保存する | テストビルド時に `dotnet publish` で **framework-dependent 単一 `.exe`**（+ zip）も作成・保存（既定 ON。ランタイムは同梱しない） |

個別に行いたいときは「設定だけ保存」「ローカルでビルド＆テスト」、または詳細設定の手動操作を使います。

> **「テストビルド」と「ローカルでビルド＆テスト」の違い**
> 「テストビルド」は Jenkins が顧客 Git からアプリソースを取得してビルドするため、未コミットのローカル変更は反映されません。
> 「ローカルでビルド＆テスト」は **この PC の作業コピー**を、配置済み CI スクリプトで検証します（git 操作なし）。先に「設定を保存」しておくと最新スクリプトで検証できます。

ローカルはビルドが失敗するとテストを実行しません。

CI の手順は Jenkins ジョブに内蔵されるため、顧客 Git へ CI 定義を push する必要はありません。Git URL / ブランチ / 認証は、Jenkins がアプリソースを checkout するためだけに使います。

> **⑤ Jenkins URL は「どの画面の URL?」** … Jenkins にログインした直後の **ホーム画面（ダッシュボード）** を開いたときの、**ブラウザのアドレスバーの URL**（`http://ホスト:ポート/`）です。
> 左上の「Jenkins」ロゴをクリックするとホーム画面に戻れます。`/job/...` は含めず、`Manage Jenkins → System` の「Jenkins URL」と同じ値。別 PC からは `localhost` ではなくホスト名/IP を使います。詳細は [CI-GUIDE.md の 6.9](CI-GUIDE.md)。

詳細は [CI-GUIDE.md](CI-GUIDE.md) と [CISetup-CI-Guide.marp.md](CISetup-CI-Guide.marp.md) を参照。どのファイルに何が書いてあるかは [README.md の「ドキュメント索引」](../README.md) を参照。
