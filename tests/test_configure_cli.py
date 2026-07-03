from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
    assert (tmp_path / "CISetup" / "scripts" / "ci-build.ps1").is_file()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.skipif(
    not (shutil.which("powershell") or shutil.which("pwsh")),
    reason="powershell/pwsh が見つからないため ci-config.ps1 の実行テストをスキップ",
)
def test_ci_config_local_json_survives_workspace_wipe(tmp_path: Path):
    """cisetup.local.json がワークスペース内から失われても、ワークスペースの
    兄弟パスに置いたバックアップから書き込み先設定を復元できることを確認する。

    背景: git checkout がフレッシュクローンにフォールバックする際（例: retry() で
    リトライした checkout が、直前の失敗で不完全になった .git を検出し、
    ワークスペースを丸ごと削除して再クローンするケース）、ワークスペース内に
    直接置いていた cisetup.local.json（git 非追跡）は失われる。これが
    "CI_FILE_SERVER is not set and storage.basePaths is empty. Skipping file
    server deploy." の警告（成果物が格納されなくなる）の主因となり得る。
    ワークスペースの外側（兄弟パス）にも同名の内容を置けるようにし、
    ワークスペースが失われても書き込み先設定を保持できるようにする。

    また、要素数 1 の配列が PowerShell の return で暗黙にスカラーへ展開され、
    `[0]` 添字アクセスが「先頭文字」を指してしまう回帰（CiFileServer /
    StorageBasePath 等の単数アクセサが壊れる）が無いことも併せて確認する。
    """
    workspace = tmp_path / "workspace" / "IPU_TEST_APP"
    scripts_dir = workspace / "cisetup" / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy(
        template_store.bundled_template_dir() / "scripts" / "ci-config.ps1",
        scripts_dir / "ci-config.ps1",
    )
    _write_json(
        workspace / "cisetup" / "cisetup.config.json",
        {
            "project": {
                "name": "IpuTestApp",
                "solutionFile": "IpuTestApp.sln",
                "publishProject": "src/IpuTestApp/IpuTestApp.csproj",
                "artifactPrefix": "IpuTestApp",
            },
            "storage": {"basePaths": []},
            "jenkins": {"ciFileServers": []},
        },
    )

    runner = (tmp_path / "run.ps1")
    runner.write_text(
        ". (Join-Path $args[0] 'cisetup\\scripts\\ci-config.ps1')\n"
        "$ci = Get-CiSettings\n"
        "[PSCustomObject]@{\n"
        "    CiFileServers = @($ci.CiFileServers)\n"
        "    CiFileServer = $ci.CiFileServer\n"
        "} | ConvertTo-Json -Compress\n",
        encoding="utf-8",
    )

    def run_get_ci_settings() -> dict:
        exe = "pwsh" if shutil.which("pwsh") else "powershell"
        proc = subprocess.run(
            [exe, "-NoProfile", "-File", str(runner), str(workspace)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    # 1) cisetup.local.json が全く無い → 元の報告どおり空になる。
    result = run_get_ci_settings()
    assert result["CiFileServers"] in ([], None)

    # 2) ワークスペースの兄弟パス（<ワークスペース>.cisetup.local.json）だけに
    #    要素数 1 の配列を置くと、ワイプ後も復元でき、スカラー展開もされない。
    sibling = workspace.parent / "IPU_TEST_APP.cisetup.local.json"
    _write_json(sibling, {"ciFileServers": [r"\\fileserver\ci"]})
    result = run_get_ci_settings()
    assert result["CiFileServers"] == [r"\\fileserver\ci"]
    assert result["CiFileServer"] == r"\\fileserver\ci"  # 「先頭文字」に壊れていないこと

    # 3) ワークスペース内に別の値があれば、そちらが優先される。
    local_in_workspace = workspace / "cisetup" / "cisetup.local.json"
    _write_json(local_in_workspace, {"ciFileServers": [r"\\primary\ci", r"\\secondary\ci"]})
    result = run_get_ci_settings()
    assert result["CiFileServers"] == [r"\\primary\ci", r"\\secondary\ci"]

    # 4) ワークスペースがワイプされて cisetup.local.json が消えても、
    #    兄弟パスのバックアップから復元される（デプロイが空スキップにならない）。
    local_in_workspace.unlink()
    result = run_get_ci_settings()
    assert result["CiFileServers"] == [r"\\fileserver\ci"]


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
