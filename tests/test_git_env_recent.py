from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cisetup import environment_scan, git_service
from cisetup.recent_project import RecentProjectStore


# ------------------------------------------------------------- git pull (mock)

class FakeGit:
    """subprocess.run を差し替えて git の挙動を再現する。"""

    def __init__(self, revs=None, branch="main", fail_on=None, timeout_on=None):
        # rev-parse HEAD の戻り値（呼ばれた順に消費し、尽きたら最後の値を返す）
        self.revs = list(revs or ["aaaaaaaaaaaa", "aaaaaaaaaaaa"])
        self.branch = branch
        self.fail_on = fail_on
        self.timeout_on = timeout_on
        self.commands: list[list[str]] = []

    def run(self, cmd, **kwargs):
        args = cmd[1:]  # drop 'git'
        self.commands.append(args)
        sub = args[0]
        if self.timeout_on == sub:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1))
        if self.fail_on == sub:
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        stdout = ""
        if args[:2] == ["rev-parse", "--abbrev-ref"]:
            stdout = self.branch
        elif args[:2] == ["rev-parse", "HEAD"]:
            stdout = self.revs.pop(0) if len(self.revs) > 1 else self.revs[0]
        return subprocess.CompletedProcess(cmd, 0, stdout, "")


def test_pull_latest_fast_forwards(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = FakeGit(revs=["aaaaaaaaaaaa", "bbbbbbbbbbbb"])
    monkeypatch.setattr(subprocess, "run", fake.run)
    summary = git_service.pull_latest(tmp_path, "main")
    assert "取り込みました" in summary
    assert ["fetch", "origin", "main"] in fake.commands
    assert ["merge", "--ff-only", "FETCH_HEAD"] in fake.commands


def test_pull_latest_already_up_to_date(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(subprocess, "run", FakeGit(revs=["aaaaaaaaaaaa"]).run)
    assert "既に最新" in git_service.pull_latest(tmp_path, "main")


def test_pull_latest_uses_current_branch_when_unset(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = FakeGit(branch="develop")
    monkeypatch.setattr(subprocess, "run", fake.run)
    git_service.pull_latest(tmp_path)
    assert ["fetch", "origin", "develop"] in fake.commands


def test_pull_latest_detached_head(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(subprocess, "run", FakeGit(branch="HEAD").run)
    with pytest.raises(git_service.GitError, match="detached HEAD"):
        git_service.pull_latest(tmp_path)


def test_pull_latest_not_a_repo(tmp_path: Path):
    with pytest.raises(git_service.GitError, match="Git リポジトリ"):
        git_service.pull_latest(tmp_path, "main")


def test_pull_latest_diverged_reports_manual_fix(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(subprocess, "run", FakeGit(fail_on="merge").run)
    with pytest.raises(git_service.GitError, match="fast-forward"):
        git_service.pull_latest(tmp_path, "main")


def test_pull_latest_never_pushes(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = FakeGit()
    monkeypatch.setattr(subprocess, "run", fake.run)
    git_service.pull_latest(tmp_path, "main")
    assert "push" not in [c[0] for c in fake.commands]


def test_pull_latest_fetch_timeout(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(subprocess, "run", FakeGit(timeout_on="fetch").run)
    with pytest.raises(git_service.GitTimeout):
        git_service.pull_latest(tmp_path, "main")


def test_pull_latest_git_not_found(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()

    def boom(cmd, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(git_service.GitError, match="git コマンドを起動"):
        git_service.pull_latest(tmp_path, "main")


# ----------------------------------------------------------- environment scan

def _fake_run_factory(table):
    def fake_run(cmd, **kwargs):
        key = cmd[0]
        rc, out, err = table.get(key, (1, "", ""))
        return subprocess.CompletedProcess(cmd, rc, out, err)

    return fake_run


def test_scan_all_found(monkeypatch):
    table = {
        "git": (0, "git version 2.43.0", ""),
        "dotnet": (0, "8.0.100 [C:\\sdk]", ""),
        "java": (0, "", 'openjdk version "17.0.1"'),
        "sc": (0, "STATE : 4 RUNNING", ""),
    }
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(table))
    results = environment_scan.scan()
    assert all(r.found for r in results)
    assert results[0].detail.startswith("git version")


def test_scan_dotnet_wrong_version(monkeypatch):
    table = {
        "git": (1, "", ""),
        "dotnet": (0, "6.0.400 [C:\\sdk]", ""),
        "java": (1, "", ""),
        "sc": (0, "STOPPED", ""),
    }
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(table))
    results = environment_scan.scan()
    by_name = {r.name: r for r in results}
    assert not by_name[".NET SDK 8"].found
    assert "6.0.400" in by_name[".NET SDK 8"].detail
    assert by_name["Jenkins サービス（この PC）"].found  # STOPPED でも検出扱い


def test_scan_dotnet_no_sdk(monkeypatch):
    table = {"dotnet": (0, "", "")}
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(table))
    results = environment_scan.scan()
    dotnet = next(r for r in results if r.name == ".NET SDK 8")
    assert "SDK が見つかりません" in dotnet.detail


def test_scan_handles_missing_commands(monkeypatch):
    def boom(cmd, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", boom)
    results = environment_scan.scan()
    assert all(not r.found for r in results)


def test_check_jenkins_service_linux_active(monkeypatch):
    # Linux では sc の代わりに systemctl is-active で検出する。
    monkeypatch.setattr(environment_scan.sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "run", _fake_run_factory({"systemctl": (0, "active", "")}))
    result = environment_scan._check_jenkins_service()
    assert result.found
    assert "active" in result.detail


def test_check_jenkins_service_linux_inactive(monkeypatch):
    monkeypatch.setattr(environment_scan.sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "run", _fake_run_factory({"systemctl": (3, "inactive", "")}))
    result = environment_scan._check_jenkins_service()
    assert result.found  # インストール済みだが停止中、として検出扱い
    assert "停止中" in result.detail


def test_check_jenkins_service_linux_not_found(monkeypatch):
    monkeypatch.setattr(environment_scan.sys, "platform", "linux")

    def boom(cmd, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", boom)
    result = environment_scan._check_jenkins_service()
    assert not result.found


def test_check_git_name_and_url_linux(monkeypatch):
    monkeypatch.setattr(environment_scan.sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "run", _fake_run_factory({"git": (0, "git version 2.43.0", "")}))
    result = environment_scan._check_git()
    assert result.name == "Git"
    assert "download/win" not in result.download_url


def test_check_git_name_and_url_windows(monkeypatch):
    monkeypatch.setattr(environment_scan.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", _fake_run_factory({"git": (0, "git version 2.43.0", "")}))
    result = environment_scan._check_git()
    assert result.name == "Git for Windows"
    assert result.download_url.endswith("/win")


# ----------------------------------------------------------- recent project

def test_recent_project_save_and_get(tmp_path: Path):
    store = RecentProjectStore(tmp_path / "recent.txt")
    store.save(tmp_path)
    assert store.get_last_project_root() == tmp_path


def test_recent_project_missing_file(tmp_path: Path):
    store = RecentProjectStore(tmp_path / "nope.txt")
    assert store.get_last_project_root() is None


def test_recent_project_nonexistent_dir(tmp_path: Path):
    f = tmp_path / "recent.txt"
    f.write_text(str(tmp_path / "gone"), encoding="utf-8")
    store = RecentProjectStore(f)
    assert store.get_last_project_root() is None


def test_recent_project_default_path(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = RecentProjectStore()
    store.save(tmp_path)
    assert store.get_last_project_root() == tmp_path
