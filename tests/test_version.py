from __future__ import annotations

import re
from pathlib import Path

from cisetup import __version__
from cisetup.version import RELEASES, VERSION, display_version, version_tuple


def test_package_version_matches_canonical():
    assert __version__ == VERSION
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)
    assert version_tuple()[:3] == tuple(int(p) for p in VERSION.split("."))


def test_releases_newest_first_and_covers_current():
    assert RELEASES[0][0] == VERSION
    versions = [row[0] for row in RELEASES]
    assert versions == sorted(versions, key=lambda v: tuple(int(p) for p in v.split(".")), reverse=True)
    assert len(set(versions)) == len(versions)
    for _ver, date, notes in RELEASES:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
        assert notes


def test_display_version_includes_semver():
    assert display_version().startswith(VERSION)


def test_user_facing_copy_omits_customer_wording():
    root = Path(__file__).resolve().parents[1]
    files = [
        root / "cisetup" / "help_texts.py",
        root / "cisetup" / "gui" / "steps" / "intro.py",
        root / "cisetup" / "gui" / "actions" / "ops.py",
    ]
    blob = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "顧客" not in blob
