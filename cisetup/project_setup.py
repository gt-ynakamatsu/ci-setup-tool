from __future__ import annotations

from pathlib import Path

from .models import CISetupConfig
from .template_store import extract_to_repository


def looks_like_test_project(name: str) -> bool:
    """xUnit 等のテスト csproj 命名規則（Contest 等の誤検出を避ける）。"""
    lowered = name.lower()
    return lowered.endswith("tests") or lowered.endswith(".test")


def deploy_ci_files(repository_root: Path, overwrite: bool = True) -> list[str]:
    """埋め込み CI テンプレートを cisetup/ へ展開する。"""
    return extract_to_repository(repository_root, overwrite=overwrite)


def has_solution_file(repository_root: Path) -> bool:
    return any(repository_root.glob("*.sln"))


def apply_auto_detection(repository_root: Path, config: CISetupConfig) -> CISetupConfig:
    sln_files = list(repository_root.glob("*.sln"))
    if not sln_files:
        return config

    sln_path = sln_files[0]
    sln_name = sln_path.stem
    relative_sln = sln_path.relative_to(repository_root).as_posix()

    if not config.project.solution_file.strip() or "yourproject" in config.project.solution_file.lower():
        config.project.solution_file = relative_sln

    if not config.project.name.strip() or config.project.name.lower() == "yourproject":
        config.project.name = sln_name

    if (
        not config.jenkins.job_name.strip()
        or config.jenkins.job_name.lower() == "cisetup-ci"
    ):
        config.jenkins.job_name = f"{config.project.name}-CI"

    if not config.project.artifact_prefix.strip() or config.project.artifact_prefix.lower() == "yourproject":
        config.project.artifact_prefix = sln_name

    publish = _find_publish_project(repository_root, sln_name)
    if publish and (
        not config.project.publish_project.strip()
        or "yourproject" in config.project.publish_project.lower()
    ):
        config.project.publish_project = publish

    if not config.project.test_project.strip():
        test = _find_test_project(repository_root, sln_name)
        if test:
            config.project.test_project = test

    return config


def _find_publish_project(repository_root: Path, project_name: str) -> str | None:
    candidates = [
        p
        for p in repository_root.rglob("*.csproj")
        if "obj" not in p.parts and "bin" not in p.parts
    ]
    if not candidates:
        return None
    for path in candidates:
        if path.stem.lower() == project_name.lower():
            return path.relative_to(repository_root).as_posix()
    return candidates[0].relative_to(repository_root).as_posix()


def _find_test_project(repository_root: Path, project_name: str) -> str | None:
    candidates = [
        p.relative_to(repository_root).as_posix()
        for p in repository_root.rglob("*.csproj")
        if "obj" not in p.parts
        and "bin" not in p.parts
        and looks_like_test_project(p.stem)
    ]
    if not candidates:
        return None
    preferred = [
        c
        for c in candidates
        if Path(c).stem.lower() in {f"{project_name}tests", f"{project_name}.tests"}
    ]
    return preferred[0] if preferred else candidates[0]
