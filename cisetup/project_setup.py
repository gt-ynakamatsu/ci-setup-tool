from __future__ import annotations

import os
import re
from pathlib import Path

from .models import CISetupConfig
from .template_store import extract_to_repository

# FPGA プロジェクトの探索で無視するフォルダ（ci-fpga.ps1 の Test-IgnoredSearchPath と同じ）。
_FPGA_SKIP_DIRS = frozenset(
    {
        ".git",
        ".vs",
        ".idea",
        "bin",
        "obj",
        "artifacts",
        "dist",
        "node_modules",
        "__pycache__",
        "testresults",
        "packages",
        "db",
        "incremental_db",
        "output_files",
    }
)

# ツールごとのプロジェクトファイル（ci-fpga.ps1 が探すものと同じ）。
_FPGA_PATTERNS: dict[str, tuple[str, ...]] = {
    "vivado": ("build.tcl", "*.xpr"),
    "quartus": ("*.qpf",),
}

# .sln の Project(...) 行から csproj パス（sln からの相対）を取り出す。
# ソリューションフォルダはパスが .csproj でないため自然に除外される。
_SLN_PROJECT_RE = re.compile(
    r'Project\("\{[0-9A-Fa-f-]+\}"\)\s*=\s*"[^"]*"\s*,\s*"([^"]+?\.csproj)"'
)


def looks_like_test_project(name: str) -> bool:
    """xUnit 等のテスト csproj 命名規則（Contest 等の誤検出を避ける）。"""
    lowered = name.lower()
    return lowered.endswith("tests") or lowered.endswith(".test")


def parse_solution_projects(sln_path: Path) -> list[str]:
    """`.sln` に含まれる csproj パス（sln からの相対表記）を列挙する。"""
    try:
        text = sln_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    return [m.group(1).strip() for m in _SLN_PROJECT_RE.finditer(text)]


def _enumerate_projects(repository_root: Path) -> list[tuple[str, str, Path]]:
    """(リポジトリルート相対 posix パス, csproj の stem, 絶対パス) を列挙する。

    まず `.sln` を解析して実プロジェクト一覧を取得する（csproj が sln と別階層にあっても
    正しいパスが分かる）。解析できなければ rglob にフォールバック。実在する csproj のみ返す。
    プロジェクト名・ソリューション名には依存しない。
    """
    root = repository_root.resolve()
    results: list[tuple[str, str, Path]] = []
    seen: set[str] = set()

    for sln in sorted(repository_root.glob("*.sln")):
        sln_dir = sln.parent
        for raw in parse_solution_projects(sln):
            abs_path = (sln_dir / raw.replace("\\", "/")).resolve()
            if not abs_path.is_file():
                continue
            try:
                # 別ドライブ（Windows）だと relpath は ValueError を投げるため除外する。
                rel = os.path.relpath(abs_path, root).replace("\\", "/")
            except ValueError:
                continue
            if rel in seen:
                continue
            seen.add(rel)
            results.append((rel, abs_path.stem, abs_path))

    if results:
        return results

    for p in repository_root.rglob("*.csproj"):
        if "obj" in p.parts or "bin" in p.parts:
            continue
        rel = p.relative_to(repository_root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        results.append((rel, p.stem, p.resolve()))
    return results


def _is_executable_project(csproj: Path) -> bool:
    """csproj が実行アプリ（OutputType が Exe / WinExe）かどうか。

    SDK スタイルで OutputType 未指定の場合は既定が Library のため False。
    読み取れない場合も False（ライブラリ扱い）。
    """
    try:
        text = csproj.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False
    m = re.search(r"<OutputType>\s*([^<\s]+)\s*</OutputType>", text, re.IGNORECASE)
    return bool(m) and m.group(1).strip().lower() in ("exe", "winexe")


def deploy_ci_files(repository_root: Path, overwrite: bool = True) -> list[str]:
    """埋め込み CI テンプレートを CISetup/ へ展開する。"""
    return extract_to_repository(repository_root, overwrite=overwrite)


def has_solution_file(repository_root: Path) -> bool:
    return any(repository_root.glob("*.sln"))


def find_fpga_projects(repository_root: Path, tool: str = "") -> list[str]:
    """FPGA プロジェクトファイルをリポジトリ内から列挙する（ルート相対 posix パス）。

    エージェント上の `ci-fpga.ps1` と同じ規則（サブフォルダも対象・ビルド生成物の
    フォルダは除外）で探すため、GUI に出す候補と CI が実際に選ぶものが一致する。

    :param tool: ``Vivado`` / ``Quartus``。空ならどちらのファイルも返す。
    """
    patterns = _FPGA_PATTERNS.get(tool.strip().lower())
    if patterns is None:
        patterns = tuple(p for group in _FPGA_PATTERNS.values() for p in group)

    found: set[str] = set()
    for pattern in patterns:
        for path in repository_root.rglob(pattern):
            if not path.is_file():
                continue
            rel = path.relative_to(repository_root)
            if any(part.lower() in _FPGA_SKIP_DIRS for part in rel.parts[:-1]):
                continue
            found.add(rel.as_posix())
    return sorted(found)


def apply_fpga_auto_detection(
    repository_root: Path, config: CISetupConfig, tool: str = ""
) -> CISetupConfig:
    """FPGA リポジトリ向けの自動入力（.sln が無くても名前を埋める）。

    プロジェクト名は `.xpr` / `.qpf` の名前、無ければフォルダ名から決める。
    `.NET` 専用のパス（.sln / csproj）はプレースホルダや実在しない値なら空にする
    （FPGA では使わないうえ、画面から隠れた項目に古い値が残ると分かりにくいため）。
    """
    projects = find_fpga_projects(repository_root, tool)
    named = [p for p in projects if p.lower().endswith((".xpr", ".qpf"))]

    if not config.project.name.strip() or config.project.name.lower() == "yourproject":
        config.project.name = Path(named[0]).stem if named else repository_root.name
    if not config.project.artifact_prefix.strip() or config.project.artifact_prefix.lower() == "yourproject":
        config.project.artifact_prefix = config.project.name
    if not config.jenkins.job_name.strip() or config.jenkins.job_name.lower() == "cisetup-ci":
        config.jenkins.job_name = f"{config.project.name}-CI"

    for attr in ("solution_file", "publish_project", "test_project"):
        value = getattr(config.project, attr)
        if value.strip() and _needs_redetect(value, repository_root):
            setattr(config.project, attr, "")
    return config


def _needs_redetect(value: str, repository_root: Path) -> bool:
    """再検出で上書きすべきか。空欄・プレースホルダ・実在しないパスなら True。"""
    v = value.strip()
    if not v:
        return True
    if "yourproject" in v.lower():
        return True
    # 保存値は "/" 区切り（_normalize_rel）。pathlib は Windows でも "/" を解釈できるため
    # 置換不要（置換すると Linux では単一ファイル名として誤解釈されてしまう）。
    target = repository_root / v
    return not target.is_file()


def apply_auto_detection(repository_root: Path, config: CISetupConfig) -> CISetupConfig:
    sln_files = list(repository_root.glob("*.sln"))
    if not sln_files:
        return config

    sln_path = sln_files[0]
    sln_name = sln_path.stem
    relative_sln = sln_path.relative_to(repository_root).as_posix()

    if _needs_redetect(config.project.solution_file, repository_root):
        config.project.solution_file = relative_sln

    if not config.project.name.strip() or config.project.name.lower() == "yourproject":
        config.project.name = sln_name

    if (
        not config.jenkins.job_name.strip()
        or config.jenkins.job_name.lower() == "cisetup-ci"
    ):
        config.jenkins.job_name = f"{config.project.name}-CI"

    if not config.project.artifact_prefix.strip() or config.project.artifact_prefix.lower() == "yourproject":
        config.project.artifact_prefix = config.project.name

    # 実在しない／プレースホルダの publish 対象は再検出して差し替える。
    # 実在するパスは OutputType がライブラリでも維持する（別リポジトリの GUI を
    # このジョブで公開しない／既存の Core 指定を勝手に変えない）。
    if _needs_redetect(config.project.publish_project, repository_root):
        publish = _find_publish_project(repository_root, config.project.name)
        if publish:
            config.project.publish_project = publish

    # テスト対象は未設定（空＝スキップ）でも正当だが、実在しない値が残っている場合や
    # 未設定の場合はリポジトリ内のテスト csproj を探して補完する。
    if _needs_redetect(config.project.test_project, repository_root):
        test = _find_test_project(repository_root, config.project.name)
        if test:
            config.project.test_project = test

    return config


def _find_publish_project(repository_root: Path, project_name: str) -> str | None:
    """publish 対象 csproj を推定する（名前依存ではなく実行アプリ優先）。

    優先順位:
      1. 実行アプリ（OutputType Exe/WinExe）— 複数あれば名前一致を優先、無ければ先頭
      2. テスト以外のプロジェクト — 名前一致を優先、無ければ先頭
      3. 何でも先頭
    名前一致はあくまでタイブレークのヒントで、一致しなくても候補は選ばれる。
    """
    projects = _enumerate_projects(repository_root)
    if not projects:
        return None
    non_test = [t for t in projects if not looks_like_test_project(t[1])]
    pool = non_test or projects
    exe = [t for t in pool if _is_executable_project(t[2])]
    return _pick_by_name(exe or pool, project_name)


def _pick_by_name(pool: list[tuple[str, str, Path]], project_name: str) -> str:
    for rel, stem, _ in pool:
        if stem.lower() == project_name.lower():
            return rel
    return pool[0][0]


def count_projects(repository_root: Path) -> int:
    """検出対象となる csproj の件数（.sln 解析優先、無ければ rglob）。"""
    return len(_enumerate_projects(repository_root))


def find_test_project(repository_root: Path, project_name: str = "") -> str | None:
    """リポジトリ内のテスト csproj（命名規則に合致）を1件返す。無ければ None。"""
    return _find_test_project(repository_root, project_name)


def _find_test_project(repository_root: Path, project_name: str) -> str | None:
    tests = [
        (rel, stem)
        for rel, stem, _ in _enumerate_projects(repository_root)
        if looks_like_test_project(stem)
    ]
    if not tests:
        return None
    preferred = [
        rel
        for rel, stem in tests
        if stem.lower() in {f"{project_name}tests", f"{project_name}.tests"}
    ]
    return preferred[0] if preferred else tests[0][0]
