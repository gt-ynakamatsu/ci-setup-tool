from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from cisetup import template_store


def test_bundled_files_exist_on_disk():
    root = template_store.bundled_template_dir()
    for rel in template_store.BUNDLED_FILES:
        # BUNDLED_FILES は "/" 区切り。pathlib は Windows でも "/" を解釈できるため
        # 置換不要（Linux では置換すると単一ファイル名として誤解釈されてしまう）。
        assert (root / rel).is_file(), rel


def test_ps1_scripts_have_no_hardcoded_backslash_paths():
    # ci-*.ps1 は Windows PowerShell 5.1 / PowerShell 7 (pwsh, Linux 含む) の両方で
    # 動く前提。"\" 決め打ちのパス連結（"$PSScriptRoot\xxx" や 'artifacts\test' のような
    # リテラル）が復活していないかを回帰的にチェックする（Linux では "\" は区切り文字として
    # 扱われないため、混入すると即壊れる）。
    root = template_store.bundled_template_dir() / "scripts"
    ps1_files = sorted(root.glob("*.ps1"))
    assert ps1_files, "ci-*.ps1 が見つかりません"

    forbidden = [
        re.compile(r"PSScriptRoot\\"),
        re.compile(r"'[a-zA-Z][a-zA-Z0-9_.]*\\[a-zA-Z]"),
        re.compile(r'"artifacts\\'),
    ]
    for script in ps1_files:
        text = script.read_text(encoding="utf-8-sig")
        for pattern in forbidden:
            assert not pattern.search(text), f"{script.name} に '\\' 決め打ちパスが残っています: {pattern.pattern}"


def test_jenkinsfile_template_is_cross_platform():
    # Jenkinsfile は isUnix() でエージェント OS を判定し、Windows は powershell、
    # Linux は pwsh を自動選択する runPs() ヘルパーを経由してスクリプトを呼ぶ。
    text = (template_store.bundled_template_dir() / "Jenkinsfile.template").read_text(encoding="utf-8-sig")
    assert "isUnix()" in text
    assert "pwsh" in text
    assert "def runPs(" in text
    # ステージ内のスクリプト呼び出しは runPs 経由（powershell を直接呼ばない）。
    assert "powershell '''" not in text
    assert "powershell '." not in text


def test_configure_help():
    proc = subprocess.run(
        [sys.executable, "configure.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert proc.returncode == 0
    assert "--bootstrap" in proc.stdout
    assert "--open" in proc.stdout


def test_configure_bootstrap(tmp_path: Path):
    (tmp_path / "App.sln").write_text("x", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "configure.py", "--bootstrap", str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.returncode == 0
    assert (tmp_path / "cisetup" / "scripts" / "ci-build.ps1").is_file()


def test_configure_bootstrap_missing_folder():
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "configure.py", "--bootstrap", r"C:\no\such\folder_bb_test"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.returncode == 1
