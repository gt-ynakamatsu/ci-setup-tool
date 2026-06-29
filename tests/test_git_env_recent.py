from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cisetup import environment_scan, git_service
from cisetup.recent_project import RecentProjectStore


# ----------------------------------------------------------- git secrets guard

def test_contains_staged_secrets_root():
    assert git_service.contains_staged_secrets("cisetup.secrets.local.json")


def test_contains_staged_secrets_in_folder():
    assert git_service.contains_staged_secrets("cisetup/cisetup.secrets.local.json")


def test_contains_staged_secrets_backslash():
    assert git_service.contains_staged_secrets("cisetup\\cisetup.secrets.local.json")


def test_contains_staged_secrets_negative():
    assert not git_service.contains_staged_secrets("cisetup/cisetup.config.json")


def test_contains_staged_secrets_empty():
    assert not git_service.contains_staged_secrets("")


def test_contains_staged_local_variants():
    assert git_service.contains_staged_local("cisetup.local.json")
    assert git_service.contains_staged_local("cisetup/cisetup.local.json")
    assert git_service.contains_staged_local("cisetup\\cisetup.local.json")
    assert not git_service.contains_staged_local("cisetup/cisetup.config.json")
    assert not git_service.contains_staged_local("cisetup/cisetup.secrets.local.json")
    assert not git_service.contains_staged_local("")


# ----------------------------------------------------------- git push (mock)

class FakeGit:
    """subprocess.run を差し替えて git の挙動を再現する。"""

    def __init__(self, staged="cisetup/cisetup.config.json", fail_on=None, timeout_on=None):
        self.staged = staged
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
        stdout = self.staged if args[:3] == ["diff", "--cached", "--name-only"] else ""
        return subprocess.CompletedProcess(cmd, 0, stdout, "")


def test_push_ci_files_success(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = FakeGit()
    monkeypatch.setattr(subprocess, "run", fake.run)
    staged = git_service.push_ci_files(tmp_path, "msg")
    assert "cisetup.config.json" in staged
    subcommands = [c[0] for c in fake.commands]
    assert "add" in subcommands and "commit" in subcommands and "push" in subcommands


def test_push_ci_files_not_a_repo(tmp_path: Path):
    with pytest.raises(git_service.GitError, match="Git リポジトリ"):
        git_service.push_ci_files(tmp_path)


def test_push_ci_files_blocks_secrets(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = FakeGit(staged="cisetup/cisetup.secrets.local.json")
    monkeypatch.setattr(subprocess, "run", fake.run)
    with pytest.raises(git_service.GitError, match="secrets"):
        git_service.push_ci_files(tmp_path)


def test_push_ci_files_excludes_local(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = FakeGit(staged="cisetup/cisetup.local.json")
    monkeypatch.setattr(subprocess, "run", fake.run)
    git_service.push_ci_files(tmp_path, "msg")
    reset_cmds = [c for c in fake.commands if c[0] == "reset"]
    assert reset_cmds, "ローカルファイルの reset が実行されていない"
    assert any("cisetup.local.json" in " ".join(c) for c in reset_cmds)


def test_push_ci_files_nothing_staged(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = FakeGit(staged="")
    monkeypatch.setattr(subprocess, "run", fake.run)
    with pytest.raises(git_service.GitError, match="変更がありません"):
        git_service.push_ci_files(tmp_path)


def test_push_ci_files_timeout(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = FakeGit(timeout_on="push")
    monkeypatch.setattr(subprocess, "run", fake.run)
    with pytest.raises(git_service.GitTimeout):
        git_service.push_ci_files(tmp_path, "msg")


def test_push_ci_files_includes_gitignore(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("x", encoding="utf-8")
    fake = FakeGit()
    monkeypatch.setattr(subprocess, "run", fake.run)
    git_service.push_ci_files(tmp_path, "msg")
    add_cmd = next(c for c in fake.commands if c[0] == "add")
    assert ".gitignore" in add_cmd


def test_run_git_not_found(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()

    def boom(cmd, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(git_service.GitError, match="git コマンドを起動"):
        git_service.push_ci_files(tmp_path)


# ----------------------------------------------------------- push 自動取り込み

REJECT_STDERR = (
    " ! [rejected]        master -> master (fetch first)\n"
    "error: failed to push some refs to 'http://example/repo'\n"
    "hint: Updates were rejected because the remote contains work that you do\n"
    "hint: not have locally."
)


class ScriptedGit:
    """サブコマンドごとに結果を指定できる git ダブル。push の挙動を回数で変える。"""

    def __init__(self, staged="cisetup/cisetup.config.json", outcomes=None):
        self.staged = staged
        self.outcomes = outcomes or {}
        self.commands: list[list[str]] = []
        self._counts: dict[str, int] = {}

    def run(self, cmd, **kwargs):
        args = cmd[1:]
        self.commands.append(args)
        sub = args[0]
        key = "pull_rebase" if sub == "pull" else sub
        idx = self._counts.get(key, 0)
        self._counts[key] = idx + 1
        seq = self.outcomes.get(key)
        if seq is not None:
            rc, err = seq[min(idx, len(seq) - 1)]
            if rc != 0:
                return subprocess.CompletedProcess(cmd, rc, "", err)
        stdout = self.staged if args[:3] == ["diff", "--cached", "--name-only"] else ""
        return subprocess.CompletedProcess(cmd, 0, stdout, "")


def test_push_recovers_from_non_fast_forward(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = ScriptedGit(outcomes={"push": [(1, REJECT_STDERR), (0, "")]})
    monkeypatch.setattr(subprocess, "run", fake.run)
    git_service.push_ci_files(tmp_path, "msg")
    subs = [c[0] for c in fake.commands]
    assert subs.count("push") == 2
    assert "pull" in subs
    pull_cmd = next(c for c in fake.commands if c[0] == "pull")
    assert "--rebase" in pull_cmd


def test_push_rebase_conflict_aborts_and_raises(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = ScriptedGit(
        outcomes={
            "push": [(1, REJECT_STDERR)],
            "pull_rebase": [(1, "CONFLICT (content): Merge conflict in cisetup/x")],
        }
    )
    monkeypatch.setattr(subprocess, "run", fake.run)
    with pytest.raises(git_service.GitError, match="pull --rebase"):
        git_service.push_ci_files(tmp_path, "msg")
    assert any(c[:2] == ["rebase", "--abort"] for c in fake.commands)


def test_push_other_error_not_retried(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    fake = ScriptedGit(outcomes={"push": [(1, "fatal: Authentication failed")]})
    monkeypatch.setattr(subprocess, "run", fake.run)
    with pytest.raises(git_service.GitError, match="Authentication failed"):
        git_service.push_ci_files(tmp_path, "msg")
    assert [c[0] for c in fake.commands].count("push") == 1
    assert "pull" not in [c[0] for c in fake.commands]


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
