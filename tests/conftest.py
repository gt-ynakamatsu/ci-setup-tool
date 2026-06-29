from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sln_repo(tmp_path: Path) -> Path:
    """`.sln` と publish/test csproj を持つ最小リポジトリ。"""
    (tmp_path / "MyApp.sln").write_text("dummy", encoding="utf-8")
    pub = tmp_path / "src" / "MyApp"
    pub.mkdir(parents=True)
    (pub / "MyApp.csproj").write_text("<Project/>", encoding="utf-8")
    test = tmp_path / "tests" / "MyApp.Tests"
    test.mkdir(parents=True)
    (test / "MyApp.Tests.csproj").write_text("<Project/>", encoding="utf-8")
    return tmp_path
