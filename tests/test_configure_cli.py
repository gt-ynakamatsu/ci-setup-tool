from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from cisetup import template_store


def test_bundled_files_exist_on_disk():
    root = template_store.bundled_template_dir()
    for rel in template_store.BUNDLED_FILES:
        assert (root / rel.replace("/", "\\")).is_file(), rel


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
