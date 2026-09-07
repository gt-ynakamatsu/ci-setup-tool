"""CISetup の版情報。GUI・CLI・配布 zip・exe の正本。"""

from __future__ import annotations

import subprocess
from pathlib import Path

# これまでの main 履歴から逆算したセマンティックバージョン。
# 1.0 初期 → 1.1 Linux/cron → 1.2 ウィザード/保存先 → 1.3 配布 exe → 1.4 Jenkins 内蔵 CI
VERSION = "1.4.0"

# (version, date, notes) 新しい順。VERSION は先頭と一致させる。
RELEASES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "1.4.0",
        "2026-09-07",
        (
            "Teams 閲覧 URL を Git 非追跡の cisetup.local.json へ",
            "CI パイプラインを Jenkins ジョブに内蔵（アプリの Git へ定義を載せない）",
            "GUI の Git push と手順チェックを廃止",
            "ビルド＆テスト前に git fetch / fast-forward で最新を取り込む",
        ),
    ),
    (
        "1.3.0",
        "2026-08-04",
        (
            "Linux から Wine 経由で CISetup.exe をビルド可能に",
            "CI 成果物を framework-dependent 単一 .exe に",
            "静的解析（Roslyn / Coverity）の Marp 資料を追加",
        ),
    ),
    (
        "1.2.0",
        "2026-07-07",
        (
            "保存先カテゴリとセットアップウィザード GUI を整備",
            "Jenkinsfile の空 triggers による Groovy 失敗を修正",
            "ヘルプアイコン・経路プレビューなど操作まわりを調整",
        ),
    ),
    (
        "1.1.0",
        "2026-07-01",
        (
            "アプリと生成 CI を Linux でも動くようにする",
            "Jenkins の cron トリガー再試行と Checkout ステージを追加",
        ),
    ),
    (
        "1.0.0",
        "2026-06-30",
        (
            "CISetup 初版（設定 GUI・Jenkins 連携・ローカルビルド＆テスト）",
            "設計仕様と利用者ガイドを追加",
        ),
    ),
)

_ROOT = Path(__file__).resolve().parents[1]


def version_tuple() -> tuple[int, int, int, int]:
    """Windows ファイルバージョン用の 4 要素。"""
    major, minor, patch = (int(part) for part in VERSION.split("."))
    return (major, minor, patch, 0)


def _read_git_revision(*, short: bool = True) -> str:
    args = ["git", "rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")
    try:
        completed = subprocess.run(
            args,
            cwd=_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip()


def git_revision(*, short: bool = True) -> str:
    """作業コピーまたはビルド時に焼いた git リビジョン。取れなければ空文字。"""
    try:
        from . import _build_revision

        baked = getattr(_build_revision, "REVISION", "")
        if baked:
            return str(baked)
    except ImportError:
        pass
    return _read_git_revision(short=short)


def display_version() -> str:
    """画面・CLI 向け。例: '1.4.0 (9d93c8e)'。"""
    revision = git_revision()
    if revision:
        return f"{VERSION} ({revision})"
    return VERSION


def write_build_revision(path: Path | None = None) -> Path:
    """PyInstaller 前にリビジョンを焼き込む（ソース実行時は git を直接見る）。"""
    target = path or (Path(__file__).resolve().parent / "_build_revision.py")
    revision = _read_git_revision()
    target.write_text(
        '"""rebuild_exe.py が生成する。コミットしない。"""\n'
        f"REVISION = {revision!r}\n",
        encoding="utf-8",
    )
    return target


def write_pyinstaller_version_file(path: Path) -> Path:
    """Windows exe のファイルバージョン資源。"""
    major, minor, patch, build = version_tuple()
    revision = git_revision()
    comments = f"rev {revision}" if revision else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# UTF-8",
                "#",
                "VSVersionInfo(",
                "  ffi=FixedFileInfo(",
                f"    filevers=({major}, {minor}, {patch}, {build}),",
                f"    prodvers=({major}, {minor}, {patch}, {build}),",
                "    mask=0x3F,",
                "    flags=0x0,",
                "    OS=0x40004,",
                "    fileType=0x1,",
                "    subtype=0x0,",
                "    date=(0, 0)",
                "  ),",
                "  kids=[",
                "    StringFileInfo([",
                "      StringTable(",
                "        '041104B0',",
                "        [",
                "          StringStruct('CompanyName', ''),",
                "          StringStruct('FileDescription', 'CISetup'),",
                f"          StringStruct('FileVersion', '{VERSION}'),",
                "          StringStruct('InternalName', 'CISetup'),",
                "          StringStruct('LegalCopyright', ''),",
                "          StringStruct('OriginalFilename', 'CISetup.exe'),",
                "          StringStruct('ProductName', 'CISetup'),",
                f"          StringStruct('ProductVersion', '{VERSION}'),",
                f"          StringStruct('Comments', '{comments}'),",
                "        ],",
                "      )",
                "    ]),",
                "    VarFileInfo([VarStruct('Translation', [1041, 1200])]),",
                "  ],",
                ")",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path
