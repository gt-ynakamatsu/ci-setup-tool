#!/usr/bin/env python3
"""CI-GUIDE / Marp を Python 正式版向けに書き換える（C# 手順書からの同期用）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CHAPTER_16 = """## 16. CISetup Configure の開発・配布

> **この章の対象:** Python 版 `configure.py`（tkinter GUI）の **開発・テスト・社内配布** です。  
> Jenkins / CI の導入（0〜11章）とは別作業です。

### 16.1 CI 導入との違い

| | CI 導入（0〜11章） | アプリ開発（本章） |
|--|-------------------|-------------------|
| 目的 | ユーザープロジェクトの自動ビルド | CISetup Configure ツール自体の開発 |
| 必要なもの | Jenkins / Git / Teams / エージェント | **Python 3.10+** + Windows |
| 成果物 | ジョブ・Teams 通知・zip | 配布 zip（`dist\\CISetup-*.zip`） |

### 16.2 必要なソフトウェア

| ソフト | バージョン | 用途 | 必須 |
|--------|-----------|------|------|
| **Python** | 3.10 以上（tkinter 付き） | GUI 実行・開発 | **必須** |
| **Windows 10/11** | — | GUI 実行 | **必須** |
| **Git** | 最新 | ソース取得・テスト | 推奨 |
| **PowerShell 5.1+** | 同梱 | 配布 zip 作成 | 推奨 |

```powershell
python --version
# 3.10 以上

python configure.py --help
```

### 16.3 リポジトリ構成

```
cisetup/
├── configure.py              … エントリ（GUI / --bootstrap / --open）
├── start_configure.bat
├── Setup-Project.bat
├── Package-Distribution.ps1  … 社内配布 zip 生成
├── bundled_templates/        … CI テンプレート正本
├── cisetup/            … アプリ本体
├── tests/                    … pytest
└── docs/                     … 手順書（本書・Marp・GUI）
```

### 16.4 初回セットアップ（取得後）

```powershell
cd C:\\workspace\\tools\\WindowsApp\\cisetup

python -m pytest tests -q
python smoke_test.py
python configure.py
```

### 16.5 開発中の GUI 起動

```powershell
python configure.py
python configure.py --open C:\\work\\MyApp
.\\Configure.ps1
```

### 16.6 社内配布 zip の作成

```powershell
.\\Package-Distribution.ps1
# => dist\\CISetup-1.0.0.zip
```

受け取り側は Python 3.10+ で zip を展開し `start_configure.bat` を実行します。

### 16.7 ビルド後の使い方

| 起動方法 | コマンド |
|---------|---------|
| GUI | `start_configure.bat` または `python configure.py` |
| 指定フォルダで GUI | `python configure.py --open C:\\work\\MyApp` |
| CI ファイル配置のみ | `python configure.py --bootstrap C:\\work\\MyApp` |
| 初回セットアップ | `Setup-Project.bat [folder]` |
| ヘルプ | `python configure.py --help` |

### 16.8 ソース変更時の注意

| 変更したファイル | 再配布が必要？ | 理由 |
|----------------|--------------|------|
| `cisetup/**` | zip 再作成 | アプリ本体 |
| `bundled_templates/**` | zip 再作成 | 配布先プロジェクトの CI テンプレート正本 |
| `docs/**` | zip 再作成（同梱） | 手順書 |

**テンプレート変更後の確認**

1. `python -m pytest tests -q`
2. `python configure.py --bootstrap` をテストプロジェクトで実行
3. 配置された `cisetup/scripts/` の内容を確認

### 16.9 テスト

```powershell
python -m pytest tests -q
python -m pytest tests --cov=cisetup --cov-report=html
```

### 16.10 トラブルシューティング（開発）

| 症状 | 対処 |
|------|------|
| `python` が見つからない | Python 3.10+ をインストールし PATH を確認 |
| tkinter が無い | Python 再インストール時に tcl/tk を有効化 |
| テンプレートが古い | `bundled_templates/` を編集後、再 bootstrap |

### 16.11 開発環境チェックリスト

```
□ Windows PC
□ Python 3.10+（python --version）
□ python -m pytest tests -q 成功
□ python configure.py で GUI 起動確認
□ .\\Package-Distribution.ps1 で dist\\*.zip 生成
```

---

"""

HEADER = """# CISetup CI テンプレート

**設定 GUI:** `configure.py`（Python 3.10+）— `start_configure.bat` で起動

**.NET デスクトップアプリ（WPF / WinForms 等）向け CI キット**

Jenkins が社内 Git から pull → ビルド → Teams 通知 → ファイルサーバー格納まで自動実行します。  
Visual Studio は **開発 PC にだけ** 必要で、CI サーバー・エージェントには **不要** です。

設定作業は **CISetup Configure（Python GUI）** で完結します（かんたん入力、上から順に進めて最後にボタン 1 つ）。

> **初めてセットアップする人は [0-6 完全再現手順](#0-6-完全再現手順ゲート付き--この順番で進めれば再現できます) を上から順に実行してください。**  
> 各ステップに「成功の見え方（ゲート）」があります。**ゲートを通過するまで次に進まない** と、どこで詰まったか特定しやすくなります。

📊 **プレゼン資料（Marp）:** [`docs/CISetup-CI-Guide.marp.md`](CISetup-CI-Guide.marp.md)  
Jenkins 導入・Teams Webhook・アプリ操作をスライド形式で網羅しています。

📖 **GUI 操作:** [`docs/GUI.md`](GUI.md)

"""


def adapt_text(text: str, *, is_ci_guide: bool = False) -> str:
    text = text.replace("dist\\framework-dependent\\configure.py", "start_configure.bat")
    text = text.replace("dist\\self-contained\\configure.py", "start_configure.bat")
    text = text.replace("dist\\configure.py", "start_configure.bat")
    text = text.replace("dist\\configure.py", "start_configure.bat")
    text = text.replace("CISetup.exe", "configure.py")
    text = text.replace("C:\\workspace\\tools\\CISetup", "C:\\workspace\\tools\\WindowsApp\\cisetup")
    text = text.replace("Build-Exe.bat", "Package-Distribution.ps1")

    # 設定アプリ（旧「exe」= Configure ツールの略称）
    subs = [
        ("cisetup-exe-用", "cisetup-gui-用"),
        ("7-phase-4--exe-で-jenkins-を自動設定", "7-phase-4--設定アプリで-jenkins-を自動設定"),
        ("Phase 4 — exe で", "Phase 4 — 設定アプリで"),
        ("## 7. Phase 4 — exe で", "## 7. Phase 4 — 設定アプリで"),
        ("### 7.1 exe の起動", "### 7.1 設定アプリの起動"),
        ("### exe が自動で行うこと", "### 設定アプリが自動で行うこと"),
        ("**B-6 / B-7 の exe 操作", "**B-6 / B-7 の設定アプリ操作"),
        ("CISetup exe", "CISetup 設定アプリ"),
        ("| **CISetup アプリを改造", "| **CISetup 設定アプリを改造"),
        ("API Token の発行（cisetup exe 用）", "API Token の発行（CISetup GUI 用）"),
        ("cisetup exe", "CISetup 設定アプリ"),
        ("（exe）", "（設定アプリ）"),
        ("| exe |", "| 設定アプリ |"),
        ("| exe（", "| 設定アプリ（"),
        ("- exe ", "- 設定アプリ "),
        ("exe **", "設定アプリ **"),
        ("exe で", "設定アプリで"),
        ("exe が", "設定アプリが"),
        ("exe の", "設定アプリの"),
        ("exe を", "設定アプリを"),
        ("exe に", "設定アプリに"),
        ("| exe ", "| 設定アプリ "),
        ("`exe`", "`設定アプリ`"),
    ]
    for old, new in subs:
        text = text.replace(old, new)

    text = text.replace(
        "設定アプリ ③ Teams",
        "設定アプリ③ Teams",
    )

    if is_ci_guide:
        idx_toc = text.find("## 目次")
        if idx_toc != -1:
            text = HEADER.rstrip() + "\n\n---\n\n" + text[idx_toc:]

        start = text.find("## 16. CISetup")
        end = text.find("## 17.", start)
        if start != -1 and end != -1:
            text = text[:start] + CHAPTER_16 + text[end:]
        text = text.replace(
            "| **CISetup 設定アプリを改造・ビルドする** | **[16章](#16-cisetup-本体の開発ビルド環境)**",
            "| **CISetup 設定アプリを改造・配布する** | **[16章](#16-cisetup-configure-の開発配布)**",
        )
        text = text.replace(
            "16-cisetup-本体の開発ビルド環境",
            "16-cisetup-configure-の開発配布",
        )
        text = text.replace(
            "**CISetup ツール自体をソースからビルドする場合**",
            "**CISetup Configure を開発・配布する場合**",
        )
        text = text.replace(
            "| **CISetup exe をソースからビルドしたい** | [16章](#16-cisetup-本体の開発ビルド環境) |",
            "| **CISetup Configure を開発・配布したい** | [16章](#16-cisetup-configure-の開発配布) |",
        )

    return text


def main() -> None:
    ci = DOCS / "CI-GUIDE.md"
    ci.write_text(adapt_text(ci.read_text(encoding="utf-8"), is_ci_guide=True), encoding="utf-8")

    marp = DOCS / "CISetup-CI-Guide.marp.md"
    marp.write_text(adapt_text(marp.read_text(encoding="utf-8")), encoding="utf-8")

    gui = DOCS / "GUI.md"
    gui.write_text(
        """# CISetup 設定 GUI

## 起動

| 項目 | 内容 |
|------|------|
| 場所 | このフォルダ（`cisetup`） |
| 起動 | `start_configure.bat` または `python configure.py` |
| 初回セットアップ | `Setup-Project.bat [プロジェクトフォルダ]` |
| 配布 | `Package-Distribution.ps1` → `dist\\CISetup-*.zip` |
| 必要環境 | Python 3.10+（tkinter）、追加 pip 不要 |

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

詳細は [CI-GUIDE.md](CI-GUIDE.md) と [CISetup-CI-Guide.marp.md](CISetup-CI-Guide.marp.md) を参照。
""",
        encoding="utf-8",
    )

    print("adapted:", ci, marp, gui)


if __name__ == "__main__":
    main()
