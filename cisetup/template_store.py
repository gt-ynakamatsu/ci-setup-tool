from __future__ import annotations

from pathlib import Path

from . import paths
from .app_paths import get_package_root

PACKAGE_ROOT = get_package_root()
BUNDLED_TEMPLATES = PACKAGE_ROOT / "bundled_templates"

# CI テンプレートの正本一覧（C# EmbeddedCiTemplateStore と同一）
BUNDLED_FILES: tuple[str, ...] = (
    "Jenkinsfile.template",
    "JenkinsJob.config.template.xml",
    "cisetup.config.example.json",
    "cisetup.secrets.local.example.json",
    "scripts/ci-analyze.ps1",
    "scripts/ci-build.ps1",
    "scripts/ci-config.ps1",
    "scripts/ci-deploy-fileserver.ps1",
    "scripts/ci-lint.ps1",
    "scripts/ci-notify-teams.ps1",
    "scripts/ci-publish.ps1",
    "scripts/ci-test.ps1",
    "scripts/TEAMS-WORKFLOW.md",
)

# Windows PowerShell 5.1 は BOM なし UTF-8 を Shift-JIS 扱いするため .ps1 は BOM 付き
PS1_SUFFIX = ".ps1"


def bundled_template_dir() -> Path:
    if not BUNDLED_TEMPLATES.is_dir():
        raise FileNotFoundError(f"CI テンプレートが見つかりません: {BUNDLED_TEMPLATES}")
    return BUNDLED_TEMPLATES


def read_template(relative_path: str) -> str:
    path = bundled_template_dir() / relative_path.replace("/", "\\")
    if not path.is_file():
        raise FileNotFoundError(f"テンプレートが見つかりません: {relative_path}")
    return path.read_text(encoding="utf-8-sig")


def extract_to_repository(repository_root: Path, overwrite: bool = True) -> list[str]:
    source = bundled_template_dir()
    written: list[str] = []

    for rel in BUNDLED_FILES:
        src = source / rel.replace("/", "\\")
        if not src.is_file():
            raise FileNotFoundError(f"同梱テンプレートが見つかりません: {rel}")

        target = paths.ci_dir(repository_root) / rel.replace("/", "\\")
        if target.is_file() and not overwrite:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == PS1_SUFFIX:
            data = src.read_bytes()
            if not data.startswith(b"\xef\xbb\xbf"):
                data = b"\xef\xbb\xbf" + data
            target.write_bytes(data)
        else:
            text = src.read_text(encoding="utf-8-sig").lstrip("\ufeff")
            target.write_text(text, encoding="utf-8", newline="\n")
        written.append(f"{paths.CI_FOLDER}/{rel.replace(chr(92), '/')}")

    _ensure_secrets_gitignore(repository_root)
    return written


def _ensure_secrets_gitignore(repository_root: Path) -> None:
    legacy_entry = paths.SECRETS_FILE
    entry = f"{paths.CI_FOLDER}/{paths.SECRETS_FILE}"
    gitignore = repository_root / ".gitignore"

    if gitignore.is_file():
        content = gitignore.read_text(encoding="utf-8")
        if entry in content and legacy_entry in content:
            return

        suffix = "" if content.endswith("\n") else "\n"
        if entry not in content:
            with gitignore.open("a", encoding="utf-8", newline="\n") as fh:
                if suffix:
                    fh.write(suffix)
                fh.write(f"{entry}\n")
            suffix = "\n"
        if legacy_entry not in content:
            with gitignore.open("a", encoding="utf-8", newline="\n") as fh:
                if suffix:
                    fh.write(suffix)
                fh.write(f"{legacy_entry}\n")
        return

    gitignore.write_text(f"{entry}\n{legacy_entry}\n", encoding="utf-8", newline="\n")
