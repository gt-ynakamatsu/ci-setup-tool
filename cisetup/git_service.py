"""リモートの最新コードを取り込む（pull）ための最小限の git 操作。

CISetup から顧客 Git へ CI 定義を push することはない（CI は Jenkins ジョブに内蔵する）。
一方で、ビルド＆テストは「リモートの最新状態」に対して行わないと意味がないため、
取り込み方向（fetch → fast-forward マージ）だけをここで扱う。

履歴を書き換えないよう ``--ff-only`` に限定し、ローカルコミットがあってリモートと
分岐している場合は手動解決を促してエラーにする。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .process_util import no_window_kwargs

LOCAL_GIT_TIMEOUT = 30  # rev-parse / merge（ローカル操作）
REMOTE_GIT_TIMEOUT = 120  # fetch（リモート通信）


class GitError(RuntimeError):
    pass


class GitTimeout(GitError):
    pass


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
            "コマンドプロンプトでそのフォルダから手動で git fetch を一度実行し、"
            "認証情報を保存してから再実行してください。"
        ) from exc

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()
        if not message:
            message = f"git コマンドが異常終了しました (ExitCode {proc.returncode})。"
        raise GitError(message)

    return (proc.stdout or "").strip()


def _current_branch(repository_root: Path) -> str:
    name = _run_git(repository_root, LOCAL_GIT_TIMEOUT, "rev-parse", "--abbrev-ref", "HEAD")
    if name == "HEAD":
        raise GitError(
            "特定のコミットを直接チェックアウトしています（detached HEAD）。\n"
            "取り込み対象のブランチを checkout してから実行してください。"
        )
    return name


def pull_latest(repository_root: Path, branch: str = "", remote: str = "origin") -> str:
    """リモートの最新を取り込む（fetch → fast-forward マージ）。

    :param repository_root: リポジトリルート。
    :param branch: 取り込むブランチ。空なら現在のブランチ。
    :param remote: リモート名（既定 ``origin``）。
    :return: 実行結果の要約（画面表示用）。
    """
    if not (repository_root / ".git").is_dir():
        raise GitError("Git リポジトリではありません。.git フォルダがあるか確認してください。")

    target = (branch or "").strip() or _current_branch(repository_root)
    before = _run_git(repository_root, LOCAL_GIT_TIMEOUT, "rev-parse", "HEAD")

    _run_git(repository_root, REMOTE_GIT_TIMEOUT, "fetch", remote, target)

    try:
        _run_git(repository_root, LOCAL_GIT_TIMEOUT, "merge", "--ff-only", "FETCH_HEAD")
    except GitTimeout:
        raise
    except GitError as exc:
        raise GitError(
            f"{remote}/{target} の取り込み（fast-forward）に失敗しました。\n"
            "リモートにない自分のコミットがある、または未コミットの変更が"
            "取り込み対象のファイルと衝突している可能性があります。\n\n"
            "対処:\n"
            "1. コマンドプロンプトでこのフォルダを開く\n"
            "2. git status で状態を確認し、commit / stash か git pull --rebase で解決する\n"
            "3. もう一度この操作を実行する\n\n"
            f"git の出力:\n{exc}"
        ) from exc

    after = _run_git(repository_root, LOCAL_GIT_TIMEOUT, "rev-parse", "HEAD")
    if before == after:
        return f"{remote}/{target} は既に最新です。"
    return f"{remote}/{target} の最新を取り込みました（{before[:7]} → {after[:7]}）。"
