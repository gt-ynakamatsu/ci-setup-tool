# CISetup 設定 GUI

## 起動

| 項目 | 内容 |
|------|------|
| **配布（推奨）** | `CISetup.exe` をダブルクリック（Python 不要） |
| 開発 | `python configure.py` または `start_configure.bat` |
| 初回セットアップ | `Setup-Project.bat [プロジェクトフォルダ]` |
| ビルド | 配布正本は `dist\CISetup.exe`。Windows: `python tools/rebuild_exe.py` / `tools\Build-Exe.bat`。Linux から `.exe` を作る場合は `python tools/setup_wine_python.py` の後 `python tools/rebuild_exe.py --windows`（`--native` は `dist/CISetup` になり社内配布用ではない） |
| 配布 zip | `tools\Package-Distribution.ps1` |

**開発ルール:** GUI・`configure.py`・`bundled_templates` を直したら、作業完了前に **`CISetup.exe` を再ビルド**する（`test_exe_freshness.py` で古い成果物を検出）。Linux では `--native` ではなく `--windows`（Wine）を使う。

### コマンドライン

```
python configure.py                  # GUI
python configure.py --open <folder>  # フォルダを開いて GUI
python configure.py --bootstrap <folder>  # CI ファイルのみ配置
python configure.py --version
python configure.py --help
```

## 操作の流れ

1. プロジェクトフォルダを指定
2. ①〜⑤ を入力（Git → **保存先** → Teams → Jenkins）
3. **セットアップを実行** — 最新を取り込む（git pull）→ 保存 → ローカルビルド＆テスト → Jenkins 反映 → テストビルド を順番に実行

ウィンドウタイトルと画面右上に **バージョン（と git リビジョン）** が出ます。正本は `cisetup/version.py` の `VERSION` です。

各項目の意味・保存先はラベル横の **「?」ヘルプアイコン**（ホバーで吹き出し）に表示されます。文言は「【何を】【なぜ】【どこで使う】…」形式です。

### 開発者向け（ソース構成）

GUI は `cisetup/gui/app.py` が薄いシェルで、`ConfigureApp` は Mixin を多重継承しています。
画面フローは `steps/workflow.py`、副作用のある操作は `actions/ops.py`、外部 API 呼び出しは `deps.py` に集約されています。
詳細は [DESIGN.md の 5.2 / 8 章](DESIGN.md) を参照。

### ⑥ セットアップを実行

「セットアップを実行」は次を**いつも同じ順**で実行します（処理を選ぶチェックはありません）。

| 順 | 内容 |
|----|------|
| 1. 最新のコードを取り込む | `git fetch` → `git merge --ff-only` で ② のブランチの最新を取り込む。**push はしない** |
| 2. 設定を保存 | `cisetup.config.json` / 作業用 `Jenkinsfile` / `scripts` を再生成して保存 |
| 3. ローカルでビルド＆テスト | 配置済み `CISetup\scripts\ci-build.ps1` → `ci-test.ps1` を**この PC でそのまま実行**（ログは「ローカルビルド＆テストの実行ログ」欄） |
| 4. Jenkins に反映 | `apply_settings` でジョブ定義（パイプライン一式）を Jenkins に登録 |
| 5. テストビルドを実行 | Jenkins がアプリの Git からソースを checkout してビルド |
| （任意）テストビルドで成果物 zip も作成・保存する | テストビルド時に `dotnet publish` で **framework-dependent 単一 `.exe`**（+ zip）も作成・保存（既定 ON。ランタイムは同梱しない） |

個別に行いたいときは「設定だけ保存」「ローカルでビルド＆テスト」（こちらも取り込んでから実行）、または詳細設定の手動操作を使います。

> **なぜ先に取り込むか** … 古いコードをテストしても意味がないためです。Jenkins のテストビルドはアプリの Git の最新を checkout するので、手元も同じ状態に揃えてから検証します。
> 取り込みは **fast-forward のみ**で、履歴は書き換えません。リモートと分岐している場合はエラーにして手動解決を促します（`git status` の確認 → commit / stash か `git pull --rebase`）。

> **「テストビルド」と「ローカルでビルド＆テスト」の違い**
> 「テストビルド」は Jenkins エージェント上で、「ローカルでビルド＆テスト」はこの PC で、同じ CI スクリプトを実行します。
> ローカル側は取り込み後の作業コピーが対象なので、未コミットの手元の変更も含めて検証できます。

ローカルはビルドが失敗するとテストを実行しません。

CI の手順は Jenkins ジョブに内蔵されます。Git URL / ブランチ / 認証は、最新の取り込みと、Jenkins がアプリソースを checkout するために使います。

> **⑤ Jenkins URL は「どの画面の URL?」** … Jenkins にログインした直後の **ホーム画面（ダッシュボード）** を開いたときの、**ブラウザのアドレスバーの URL**（`http://ホスト:ポート/`）です。
> 左上の「Jenkins」ロゴをクリックするとホーム画面に戻れます。`/job/...` は含めず、`Manage Jenkins → System` の「Jenkins URL」と同じ値。別 PC からは `localhost` ではなくホスト名/IP を使います。詳細は [CI-GUIDE.md の 6.9](CI-GUIDE.md)。

詳細は [CI-GUIDE.md](CI-GUIDE.md) と [CISetup-CI-Guide.marp.md](CISetup-CI-Guide.marp.md) を参照。どのファイルに何が書いてあるかは [README.md の「ドキュメント索引」](../README.md) を参照。
