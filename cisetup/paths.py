from __future__ import annotations

from pathlib import Path

CI_FOLDER = "cisetup"
CONFIG_FILE = "cisetup.config.json"
SECRETS_FILE = "cisetup.secrets.local.json"
LOCAL_FILE = "cisetup.local.json"
JENKINSFILE = "Jenkinsfile"


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


def ci_dir(repository_root: Path) -> Path:
    return repository_root / CI_FOLDER


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


def has_ci_layout(repository_root: Path) -> bool:
    return config_path(repository_root).is_file()


def has_saved_config(repository_root: Path) -> bool:
    """保存済み設定ファイルが存在するか（標準 layout + 旧 layout）。"""
    root = repository_root.resolve()
    return (
        config_path(root).is_file()
        or (root / CONFIG_FILE).is_file()
        or (root / "ci.settings.json").is_file()
    )


def normalize_project_root(selected: Path) -> Path:
    """「プロジェクトを開く / 配置する」用に選択パスを正規化する。

    cisetup フォルダ自体（設定入り）を選んだ場合のみ親へ繰り上げる。
    入れ子の cisetup/cisetup/ 生成を防ぐための保守的な正規化で、
    既存設定が無い新規フォルダはそのまま返す（親へは遡らない）。
    """
    directory = selected.resolve()
    if directory.name == CI_FOLDER and (directory / CONFIG_FILE).is_file():
        return directory.parent
    return directory


def resolve_repository_root(selected: Path) -> Path | None:
    """フォルダ選択で選んだパスをリポジトリルートに正規化する。

    - プロジェクトルート（cisetup/cisetup.config.json または直下の cisetup.config.json）
    - cisetup/ フォルダ自体を選んだ場合は親ディレクトリをルートとする
    - 子フォルダを選んだ場合は親を辿って設定を探す
    """
    directory = selected.resolve()

    if directory.name == CI_FOLDER and (directory / CONFIG_FILE).is_file():
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
