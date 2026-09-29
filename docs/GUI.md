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

1. **CI の種類を選ぶ**（起動直後の選択画面。.NET / FPGA — Vivado / FPGA — Quartus / C・C++ / Python / カスタム）
2. プロジェクトフォルダを指定
3. ①〜⑤ を入力（Git → **保存先** → Teams → Jenkins）
4. **セットアップを実行** — 最新を取り込む（git pull）→ 保存 → ローカルビルド＆テスト → Jenkins 反映 → テストビルド を順番に実行

保存済みの設定があるプロジェクトを開いたときは、選択画面を飛ばして保存された種類のフォームが出ます。

### CI の種類で画面が変わる

選んだ種類は画面上部の「CI の種類（プリセット）」に出ており、選び直すとその場で切り替わります（「種類の選択に戻る」で選択画面にも戻れます）。種類によって変わるのは次の点です。

| | .NET | FPGA（Vivado / Quartus） |
|---|---|---|
| ① で選ぶフォルダ | `.sln` があるリポジトリルート | FPGA プロジェクトのリポジトリルート（`.xpr` / `.qpf` / `build.tcl` はサブフォルダ可） |
| ビルド対象の指定 | 詳細設定の `.sln` / Publish csproj / テスト csproj / RID | **FPGA ビルドの設定**カード（合成するプロジェクト・ビルド Tcl・合成タイムアウト。詳細設定には同じタイムアウト欄を出さない） |
| 環境チェック | Git / .NET SDK 8 / Java / Jenkins | Git / **Vivado または Quartus** / Java / Jenkins |
| ビルド手順 | `dotnet restore` → `build` → `test` → `publish` | `ci-fpga.ps1`（ツールと合成対象を自動検出） |

**FPGA** はビルドコマンドを手で書く必要はありません。合成対象は空欄なら自動検出（候補が 1 つのとき）で、複数ある場合だけ「合成するプロジェクト」で選びます（「候補を再検出」でリポジトリ内を探し直します）。合成は時間がかかるため、種類を選んだ時点でビルドタイムアウトを 180 分に上げます。詳細は [CI-GUIDE.md の 1-1](CI-GUIDE.md) です。

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
| 3. ローカルでビルド＆テスト | 配置済み `CISetup\scripts\ci-build.ps1` → `ci-test.ps1`（成果物 ON なら `ci-publish.ps1` も）を**この PC でそのまま実行**（ログは「ローカルビルド＆テストの実行ログ」欄。スクロールバー・ホイール・矢印キーで遡れる） |
| 4. Jenkins に反映 | `apply_settings` でジョブ定義（パイプライン一式）を Jenkins に登録 |
| 5. テストビルドを実行 | Jenkins がアプリの Git からソースを checkout してビルド |
| （任意）成果物（exe / zip）も作成する | `dotnet publish` で **framework-dependent 単一 `.exe`**（+ zip）も作成（既定 ON。ランタイムは同梱しない）。**ローカルのビルド＆テストとテストビルドの両方**に効くため、publish 固有の失敗を Jenkins に投げる前に検出できる |

個別に行いたいときは「設定だけ保存」「ローカルでビルド＆テスト」（こちらも取り込んでから実行）を使います。Jenkins への反映だけ、または今すぐビルドは詳細設定にあります。

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
