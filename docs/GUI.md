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
2. ①〜⑤ を入力（Git / Teams / 保存先 / Jenkins）
3. **セットアップを実行** — 保存・Jenkins 反映・Git push

各項目の意味・保存先は入力欄の **ヘルプ（吹き出し）** に表示されます。

> **⑤ Jenkins URL は「どの画面の URL?」** … Jenkins にログインした直後の **ホーム画面（ダッシュボード）** を開いたときの、**ブラウザのアドレスバーの URL**（`http://ホスト:ポート/`）です。
> 左上の「Jenkins」ロゴをクリックするとホーム画面に戻れます。`/job/...` は含めず、`Manage Jenkins → System` の「Jenkins URL」と同じ値。別 PC からは `localhost` ではなくホスト名/IP を使います。詳細は [CI-GUIDE.md の 6.9](CI-GUIDE.md)。

詳細は [CI-GUIDE.md](CI-GUIDE.md) と [CISetup-CI-Guide.marp.md](CISetup-CI-Guide.marp.md) を参照。どのファイルに何が書いてあるかは [README.md の「ドキュメント索引」](../README.md) を参照。
