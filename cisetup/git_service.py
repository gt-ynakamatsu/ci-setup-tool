from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import paths
from .process_util import no_window_kwargs

DEFAULT_COMMIT_MESSAGE = "Add CISetup CI configuration"

LOCAL_GIT_TIMEOUT = 30  # add/commit/diff（ローカル操作）
REMOTE_GIT_TIMEOUT = 120  # push（リモート通信）


class GitError(RuntimeError):
    pass


class GitTimeout(GitError):
    pass


def _normalize_staged_path(line: str) -> str:
    return line.strip().replace("\\", "/").lstrip("/")


def _matches_ci_file(normalized: str, filename: str) -> bool:
    if not normalized:
        return False
    if normalized.lower() == filename.lower():
        return True
    expected = f"{paths.CI_FOLDER}/{filename}"
    return normalized.lower() == expected.lower()


def _is_secrets_path(normalized: str) -> bool:
    return _matches_ci_file(normalized, paths.SECRETS_FILE)


def _is_local_path(normalized: str) -> bool:
    return _matches_ci_file(normalized, paths.LOCAL_FILE)


def contains_staged_secrets(staged_name_only: str) -> bool:
    if not staged_name_only.strip():
        return False
    for raw in staged_name_only.replace("\r", "\n").split("\n"):
        if raw and _is_secrets_path(_normalize_staged_path(raw)):
            return True
    return False


def contains_staged_local(staged_name_only: str) -> bool:
    if not staged_name_only.strip():
        return False
    for raw in staged_name_only.replace("\r", "\n").split("\n"):
        if raw and _is_local_path(_normalize_staged_path(raw)):
            return True
    return False


def _run_git(repository_root: Path, timeout: float, *args: str) -> str:
    env = dict(os.environ)
    # 認証やホスト鍵確認などの対話でハングさせず、即エラーにする。
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_SSH_COMMAND"] = "ssh -oBatchMode=yes -oStrictHostKeyChecking=accept-new"

    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repository_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            **no_window_kwargs(),
        )
    except FileNotFoundError as exc:
        raise GitError(
            "git コマンドを起動できません。Git for Windows をインストールしてください。"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        command = args[0] if args else "git"
        raise GitTimeout(
            f"git {command} が {int(timeout)} 秒以内に応答しませんでした。\n\n"
            "考えられる原因:\n"
            "• Git サーバーに接続できない（URL / ネットワーク / VPN）\n"
            "• 認証情報が未設定（資格情報マネージャーに保存されていない）\n"
            "• リモートが応答しない\n\n"
            "コマンドプロンプトでそのフォルダから手動で git push を一度実行し、"
            "認証情報を保存してから再実行してください。"
        ) from exc

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()
        if not message:
            message = f"git コマンドが異常終了しました (ExitCode {proc.returncode})。"
        raise GitError(message)

    return (proc.stdout or "").strip()


def _is_non_fast_forward(message: str) -> bool:
    """push 拒否（リモートに先行コミットがある）かどうかを判定する。"""
    low = message.lower()
    if "rejected" not in low and "failed to push" not in low:
        return False
    return any(
        hint in low
        for hint in ("fetch first", "non-fast-forward", "non fast forward", "behind")
    )


def _push_with_autosync(repository_root: Path) -> None:
    """push する。リモートに先行コミットがあれば pull --rebase で取り込んで再 push。"""
    try:
        _run_git(repository_root, REMOTE_GIT_TIMEOUT, "push")
        return
    except GitTimeout:
        raise
    except GitError as exc:
        if not _is_non_fast_forward(str(exc)):
            raise

    # リモートに別の変更がある。自分のコミットをその上に載せ直してから再 push する。
    try:
        _run_git(repository_root, REMOTE_GIT_TIMEOUT, "pull", "--rebase")
    except GitTimeout:
        raise
    except GitError as exc:
        # 衝突などで取り込みに失敗。rebase を中断して元の状態へ戻す。
        try:
            _run_git(repository_root, LOCAL_GIT_TIMEOUT, "rebase", "--abort")
        except GitError:
            pass
        raise GitError(
            "リモートに別の変更があり、自動での取り込み（git pull --rebase）に失敗しました。\n"
            "同じファイルが両方で変更されている可能性があります。\n\n"
            "対処:\n"
            "1. コマンドプロンプトでこのフォルダを開く\n"
            "2. git pull --rebase を実行して競合を解決する\n"
            "3. もう一度この操作を実行する"
        ) from exc

    # 取り込みに成功したので再度 push する。
    _run_git(repository_root, REMOTE_GIT_TIMEOUT, "push")


def _ci_add_paths(repository_root: Path) -> list[str]:
    result = [paths.CI_FOLDER]
    if (repository_root / ".gitignore").is_file():
        result.append(".gitignore")
    return result


def push_ci_files(repository_root: Path, commit_message: str | None = None) -> str:
    """CI 関連ファイルだけを add / commit / push する（secrets は除外）。"""
    if not (repository_root / ".git").is_dir():
        raise GitError("Git リポジトリではありません。.git フォルダがあるか確認してください。")

    _run_git(repository_root, LOCAL_GIT_TIMEOUT, "add", *_ci_add_paths(repository_root))

    staged = _run_git(repository_root, LOCAL_GIT_TIMEOUT, "diff", "--cached", "--name-only")

    # 個人 ID を含むローカル設定（cisetup.local.json）は push しない。静かに除外する。
    if contains_staged_local(staged):
        for path in (paths.LOCAL_FILE, f"{paths.CI_FOLDER}/{paths.LOCAL_FILE}"):
            try:
                _run_git(repository_root, LOCAL_GIT_TIMEOUT, "reset", "HEAD", "--", path)
            except GitError:
                pass
        staged = _run_git(repository_root, LOCAL_GIT_TIMEOUT, "diff", "--cached", "--name-only")

    if contains_staged_secrets(staged):
        for path in (
            paths.SECRETS_FILE,
            f"{paths.CI_FOLDER}/{paths.SECRETS_FILE}",
        ):
            try:
                _run_git(repository_root, LOCAL_GIT_TIMEOUT, "reset", "HEAD", "--", path)
            except GitError:
                pass
        raise GitError(
            "cisetup.secrets.local.json が commit 対象に含まれていました。"
            "除外しました。secrets は Git に push しないでください。"
        )

    if not staged.strip():
        raise GitError("commit する変更がありません。先に「すべて保存」を実行してください。")

    message = (commit_message or "").strip() or DEFAULT_COMMIT_MESSAGE
    _run_git(repository_root, LOCAL_GIT_TIMEOUT, "commit", "-m", message)
    _push_with_autosync(repository_root)

    return staged
