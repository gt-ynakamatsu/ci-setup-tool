from __future__ import annotations

from pathlib import Path

import pytest

import cisetup.local_ci as local_ci


def _make_scripts(root: Path, *, build: bool = True, test: bool = True) -> None:
    scripts = root / "cisetup" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    if build:
        (scripts / "ci-build.ps1").write_text("# build", encoding="utf-8")
    if test:
        (scripts / "ci-test.ps1").write_text("# test", encoding="utf-8")


def _fake_popen(returncodes: dict[str, int], calls: list[list[str]]):
    class FakePopen:
        def __init__(self, cmd, **kwargs):
            calls.append(cmd)
            self._cmd = cmd
            self.kwargs = kwargs
            self.stdout = iter(["==> line1\n", "==> line2\n"])
            self.returncode = 0

        def wait(self):
            joined = " ".join(self._cmd)
            if "ci-build.ps1" in joined:
                self.returncode = returncodes.get("build", 0)
            elif "ci-test.ps1" in joined:
                self.returncode = returncodes.get("test", 0)

    return FakePopen


def test_run_local_ci_runs_build_then_test(tmp_path, monkeypatch):
    _make_scripts(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(local_ci.subprocess, "Popen", _fake_popen({}, calls))
    output: list[str] = []

    local_ci.run_local_ci(tmp_path, configuration="Debug", on_output=output.append)

    joined = [" ".join(c) for c in calls]
    assert len(calls) == 2
    assert "ci-build.ps1" in joined[0]
    assert "ci-test.ps1" in joined[1]
    # 両方に -Configuration Debug が渡る
    for cmd in calls:
        assert "-Configuration" in cmd
        assert "Debug" in cmd
    # ビルドがテストより前
    assert joined[0].index("ci-build.ps1") >= 0 and joined[1].index("ci-test.ps1") >= 0
    # ストリームされた出力が届く
    assert any("line1" in line for line in output)


def test_run_local_ci_stops_on_build_failure(tmp_path, monkeypatch):
    _make_scripts(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(local_ci.subprocess, "Popen", _fake_popen({"build": 1}, calls))

    with pytest.raises(local_ci.LocalCIError):
        local_ci.run_local_ci(tmp_path)

    # ビルド失敗時はテストを実行しない
    assert len(calls) == 1
    assert "ci-build.ps1" in " ".join(calls[0])


def test_run_local_ci_test_failure_raises(tmp_path, monkeypatch):
    _make_scripts(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(local_ci.subprocess, "Popen", _fake_popen({"test": 2}, calls))

    with pytest.raises(local_ci.LocalCIError):
        local_ci.run_local_ci(tmp_path)

    assert len(calls) == 2


def test_run_local_ci_missing_build_script_raises(tmp_path, monkeypatch):
    _make_scripts(tmp_path, build=False)
    calls: list[list[str]] = []
    monkeypatch.setattr(local_ci.subprocess, "Popen", _fake_popen({}, calls))

    with pytest.raises(local_ci.LocalCIError) as exc:
        local_ci.run_local_ci(tmp_path)

    assert "設定を保存" in str(exc.value)
    # スクリプトが無いので subprocess は起動されない
    assert calls == []


def test_run_local_ci_default_configuration(tmp_path, monkeypatch):
    _make_scripts(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(local_ci.subprocess, "Popen", _fake_popen({}, calls))

    local_ci.run_local_ci(tmp_path)

    for cmd in calls:
        idx = cmd.index("-Configuration")
        assert cmd[idx + 1] == "Release"
