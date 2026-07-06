from __future__ import annotations

import os
import subprocess
import warnings
from pathlib import Path

from .process_util import no_window_kwargs

CI_FOLDER = "CISetup"
LEGACY_CI_FOLDER = "cisetup"
CONFIG_FILE = "cisetup.config.json"
SECRETS_FILE = "cisetup.secrets.local.json"
LOCAL_FILE = "cisetup.local.json"
JENKINSFILE = "Jenkinsfile"

# ケース差のみのリネーム（cisetup→CISetup）を確実に反映するための一時名。
_MIGRATE_TMP = "cisetup__migrate_tmp"


def is_url(value: str) -> bool:
    """格納先が http(s) URL（OneDrive/SharePoint 等）かどうか。"""
    v = (value or "").strip().lower()
    return v.startswith("http://") or v.startswith("https://")


def join_location(base: str, *parts: str) -> str:
    """格納先（UNC/ローカルパス または URL）にサブパスを連結する。

    URL なら "/"、パスなら "\\" で連結する。base が空なら最初の非空 part を起点にする。
    """
    base = (base or "").strip()
    rest = [p.strip() for p in parts if p and p.strip()]

    if not base:
        if not rest:
            return ""
        base, rest = rest[0], rest[1:]

    if is_url(base):
        result = base.rstrip("/")
        for part in rest:
            result += "/" + part.strip("/\\")
        return result

    result = base.rstrip("\\/")
    for part in rest:
        result += "\\" + part.strip("\\/")
    return result


def is_ci_folder_name(name: str) -> bool:
    """フォルダ名が CI フォルダ（新 CISetup / 旧 cisetup）に該当するか（大文字小文字非区別）。"""
    return name.lower() in (CI_FOLDER.lower(), LEGACY_CI_FOLDER.lower())


def ci_dir(repository_root: Path) -> Path:
    """新規書き込み用の CI ディレクトリ（常に CISetup/）。"""
    return repository_root / CI_FOLDER


def _existing_ci_entry(repository_root: Path) -> Path | None:
    """実体として存在する CI ディレクトリを実際の名前（ケース込み）で返す。

    新 CISetup を優先し、無ければ旧 cisetup を返す。Linux/git はケースを区別するため、
    実ディレクトリ名を走査して判定する。
    """
    try:
        entries = list(repository_root.iterdir())
    except OSError:
        return None
    new_dir: Path | None = None
    legacy_dir: Path | None = None
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
        except OSError:
            continue
        if entry.name == CI_FOLDER:
            new_dir = entry
        elif is_ci_folder_name(entry.name):
            legacy_dir = entry
    return new_dir or legacy_dir


def find_ci_dir(repository_root: Path) -> Path | None:
    """既存の CI ディレクトリを返す（CISetup 優先、無ければ旧 cisetup）。

    後方互換の読み込み用。新規書き込み先が欲しい場合は ci_dir() を使う。
    """
    return _existing_ci_entry(repository_root)


def _read_ci_dir(repository_root: Path) -> Path:
    """読み込み用 CI ディレクトリ。既存が無ければ新 CISetup を指す。"""
    found = find_ci_dir(repository_root)
    return found if found is not None else ci_dir(repository_root)


def config_path(repository_root: Path) -> Path:
    return ci_dir(repository_root) / CONFIG_FILE


def secrets_path(repository_root: Path) -> Path:
    return ci_dir(repository_root) / SECRETS_FILE


def local_path(repository_root: Path) -> Path:
    return ci_dir(repository_root) / LOCAL_FILE


def jenkinsfile_path(repository_root: Path) -> Path:
    return ci_dir(repository_root) / JENKINSFILE


def scripts_dir(repository_root: Path) -> Path:
    return ci_dir(repository_root) / "scripts"


def read_config_path(repository_root: Path) -> Path:
    return _read_ci_dir(repository_root) / CONFIG_FILE


def read_secrets_path(repository_root: Path) -> Path:
    return _read_ci_dir(repository_root) / SECRETS_FILE


def read_local_path(repository_root: Path) -> Path:
    return _read_ci_dir(repository_root) / LOCAL_FILE


def read_scripts_dir(repository_root: Path) -> Path:
    """既存スクリプトの読み込み用ディレクトリ（CISetup 優先、無ければ旧 cisetup）。"""
    return _read_ci_dir(repository_root) / "scripts"


def has_ci_layout(repository_root: Path) -> bool:
    return read_config_path(repository_root).is_file()


def has_saved_config(repository_root: Path) -> bool:
    """保存済み設定ファイルが存在するか（標準 layout + 旧 layout）。"""
    root = repository_root.resolve()
    return (
        read_config_path(root).is_file()
        or (root / CONFIG_FILE).is_file()
        or (root / "ci.settings.json").is_file()
    )


def normalize_project_root(selected: Path) -> Path:
    """「プロジェクトを開く / 配置する」用に選択パスを正規化する。

    CI フォルダ自体（設定入り）を選んだ場合のみ親へ繰り上げる。
    入れ子の CISetup/CISetup/ 生成を防ぐための保守的な正規化で、
    既存設定が無い新規フォルダはそのまま返す（親へは遡らない）。
    """
    directory = selected.resolve()
    if is_ci_folder_name(directory.name) and (directory / CONFIG_FILE).is_file():
        return directory.parent
    return directory


def resolve_repository_root(selected: Path) -> Path | None:
    """フォルダ選択で選んだパスをリポジトリルートに正規化する。

    - プロジェクトルート（CISetup/cisetup.config.json または直下の cisetup.config.json）
    - CI フォルダ（CISetup/ または旧 cisetup/）自体を選んだ場合は親ディレクトリをルートとする
    - 子フォルダを選んだ場合は親を辿って設定を探す
    """
    directory = selected.resolve()

    if is_ci_folder_name(directory.name) and (directory / CONFIG_FILE).is_file():
        return directory.parent

    if has_saved_config(directory):
        return directory

    current = directory
    while True:
        parent = current.parent
        if parent == current:
            break
        if has_saved_config(parent):
            return parent
        current = parent

    return None


def has_legacy_layout(repository_root: Path) -> bool:
    root = repository_root
    return (
        (root / CONFIG_FILE).is_file()
        or (root / JENKINSFILE).is_file()
        or (root / "scripts").is_dir()
    )


def find_repository_root(start: Path | None = None) -> Path | None:
    directory = (start or Path.cwd()).resolve()
    while True:
        if (
            has_ci_layout(directory)
            or has_legacy_layout(directory)
            or (directory / "ci.settings.json").is_file()
            or any(directory.glob("*.sln"))
        ):
            return directory
        parent = directory.parent
        if parent == directory:
            return None
        directory = parent


def _run_git_mv(repository_root: Path, src: str, dst: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "mv", src, dst],
            cwd=str(repository_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            stdin=subprocess.DEVNULL,
            **no_window_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def migrate_ci_dir(repository_root: Path) -> bool:
    """旧 cisetup/ フォルダを新 CISetup/ へリネーム移行する。

    Windows はケース差のみのリネームになり単純 rename が no-op/失敗になりうるため、
    一時名を経由する。git 作業ツリー内なら git mv を優先し、Linux/git でも確実に
    ケース変更を反映する。既に CISetup（正しいケース）なら何もしない。
    移行を実施したら True。失敗は握りつぶさず warnings.warn して False を返す。
    """
    root = repository_root
    entry = _existing_ci_entry(root)
    if entry is None or entry.name == CI_FOLDER:
        return False

    tmp = root / _MIGRATE_TMP
    suffix = 0
    while tmp.exists():
        suffix += 1
        tmp = root / f"{_MIGRATE_TMP}{suffix}"

    target = root / CI_FOLDER
    in_git = (root / ".git").exists()

    try:
        if in_git and _run_git_mv(root, entry.name, tmp.name):
            if _run_git_mv(root, tmp.name, CI_FOLDER):
                return True
            # entry→tmp は成功、tmp→CISetup が失敗 → ファイルシステムで仕上げる。
            os.rename(tmp, target)
            return True

        # 非 git / git mv 不可の場合は一時名を経由してケース差リネームを確実にする。
        os.rename(entry, tmp)
        os.rename(tmp, target)
        return True
    except OSError as exc:
        warnings.warn(
            f"CI フォルダ（{entry.name}）の CISetup への移行に失敗しました: {exc}",
            stacklevel=2,
        )
        return False
