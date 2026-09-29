"""CI の実行ログ（コンソール出力の全文保存）まわりの回帰テスト。

背景: 以前は Prepare ステージで 1 回だけ Start-Transcript していたため、
Jenkins が powershell ステップごとに別プロセスを起こす関係で Build 以降の出力が
artifacts/logs/build.log に残らなかった。さらに dotnet / vivado / quartus_sh のような
native コマンドの出力は Transcript では取りこぼすことがあり、「CI が失敗したが
ログを見ても原因が分からない」状態になっていた。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cisetup import template_store
from cisetup.jenkinsfile_generator import render_jenkinsfile
from cisetup.models import default_config
from cisetup.project_setup import deploy_ci_files

from .groovy_sanity import GroovySyntaxError, check_quotes_and_brackets


def _template(name: str) -> str:
    return (template_store.bundled_template_dir() / name).read_text(encoding="utf-8-sig")


def _script(name: str) -> str:
    return (template_store.bundled_template_dir() / "scripts" / name).read_text(encoding="utf-8-sig")


def _pwsh() -> str | None:
    for name in ("pwsh", "powershell"):
        path = shutil.which(name)
        if path:
            return path
    return None


def test_generated_jenkinsfile_quoting_is_balanced():
    # Jenkinsfile が構文エラーだと全ビルドが即失敗するため、三連引用符の閉じ忘れや
    # 括弧の不一致だけでも Jenkins に載せる前に気付けるようにする。
    config = default_config()
    config.project.name = "Demo"
    config.git.repository_url = "https://git.example.com/demo.git"
    text = render_jenkinsfile(template_store.read_template("Jenkinsfile.template"), config)
    check_quotes_and_brackets(text)

    # チェッカ自身が壊れていないこと（壊した Jenkinsfile を見逃さない）。
    with pytest.raises(GroovySyntaxError):
        check_quotes_and_brackets(text + "\nrunPs 'x', '''閉じていない")
    with pytest.raises(GroovySyntaxError):
        check_quotes_and_brackets(text + "}")


def test_jenkinsfile_appends_console_output_per_stage():
    text = _template("Jenkinsfile.template")
    # ステージごとに Transcript を開き直して 1 本の build.log へ追記する。
    assert "def runPs(String label, String script)" in text
    assert "Start-Transcript -Path artifacts/logs/build.log -Append" in text
    # ラベル無しの 1 引数呼び出し（旧形式）が残っていないこと。
    assert "runPs '''" not in text
    assert "runPs './CISetup" not in text
    # artifacts を作り直す Prepare とログ配置だけは Transcript なしで実行する。
    assert "runPsRaw '''" in text
    assert "runPsRaw './CISetup/scripts/ci-deploy-fileserver.ps1 -Type Logs'" in text
    # ログは成功・失敗どちらでも配置する（post.always に置く）。
    always_block = text.split("post {", 1)[1].split("success {", 1)[0]
    assert "-Type Logs" in always_block
    assert "jenkins-build-info.log" in always_block
    assert "jenkins-console.log" in always_block
    assert "currentBuild.rawBuild.getLog(Integer.MAX_VALUE)" in always_block
    assert "consoleText" not in always_block
    # ステージ順: Prepare（artifacts 再作成）が CISetup 展開より前。
    assert text.index("stage('Prepare')") < text.index("stage('Materialize CISetup')")


def _run_ps_wrapper(label: str, script: str) -> str:
    """Jenkinsfile の runPs が生成する PowerShell 本文を取り出す（Groovy の \\$ を戻す）。"""
    text = _template("Jenkinsfile.template")
    body = text.split('runPsRaw("""', 1)[1].split('\n""")', 1)[0]
    return body.replace("\\$", "$").replace("${label}", label).replace("${script}", script)


def _read_text_any(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_stage_failure_reason_lands_in_build_log(tmp_path: Path):
    # 失敗の本文は Stop-Transcript の後に PowerShell が表示するため、以前は build.log に
    # 開始・終了の行しか残らず「ログを見ても原因が分からない」状態だった。
    runner = tmp_path / "stage.ps1"
    runner.write_text(
        _run_ps_wrapper("Build", "    throw 'SOLUTION_NOT_FOUND: MyApp.sln'"),
        encoding="utf-8-sig",
    )
    proc = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(runner)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    # 失敗はステージ失敗として伝播させる（ログに書いて握りつぶすのではない）。
    assert proc.returncode != 0

    log_text = _read_text_any(tmp_path / "artifacts" / "logs" / "build.log")
    assert "SOLUTION_NOT_FOUND: MyApp.sln" in log_text
    assert "Build : FAILED" in log_text
    assert "Build : end" in log_text


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_successful_stage_has_no_failure_marker(tmp_path: Path):
    runner = tmp_path / "stage.ps1"
    runner.write_text(
        _run_ps_wrapper("Build", "    Write-Output 'OK_LINE'"),
        encoding="utf-8-sig",
    )
    proc = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(runner)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    log_text = _read_text_any(tmp_path / "artifacts" / "logs" / "build.log")
    assert "OK_LINE" in log_text
    assert "FAILED" not in log_text


def test_run_ps_writes_failure_reason_into_transcript():
    text = _template("Jenkinsfile.template")
    wrapper = text.split("def runPs(String label, String script)", 1)[1].split("\npipeline {", 1)[0]
    # catch は finally（Stop-Transcript）より前に置き、理由をログへ書いてから投げ直す。
    assert wrapper.index("catch {") < wrapper.index("Stop-Transcript")
    assert "$_.Exception.Message" in wrapper
    assert "$_.ScriptStackTrace" in wrapper
    assert "throw" in wrapper


def test_pipeline_job_is_trusted_for_console_log_access():
    job_xml = _template("JenkinsJob.config.template.xml")
    # rawBuild は Script Security sandbox から呼べない。Pipeline は本ツールが生成・管理する。
    assert "<sandbox>false</sandbox>" in job_xml


def test_stage_scripts_write_native_output_to_logs():
    # dotnet / 合成ツールの出力はヘルパー経由でログへ流す（素の呼び出しに戻っていないこと）。
    build = _script("ci-build.ps1")
    assert "Get-CiLogPath -Root $ci.Root -Name 'build-output.log'" in build
    assert "Invoke-CiLogged -LogPath $buildLog" in build
    assert "\ndotnet build" not in build

    lint = _script("ci-lint.ps1")
    assert "lint-output.log" in lint
    assert "\ndotnet restore" not in lint

    publish = _script("ci-publish.ps1")
    assert "publish-output.log" in publish
    assert "\ndotnet @publishArgs" not in publish

    fpga = _script("ci-fpga.ps1")
    assert "fpga-output.log" in fpga
    assert "Invoke-CiLogged" in fpga
    assert "Copy-CiFpgaReports" in fpga


def test_logs_deploy_copies_every_log_file():
    deploy = _script("ci-deploy-fileserver.ps1")
    logs_branch = deploy.split("if ($Type -eq 'Logs')", 1)[1].split("if ($Type -eq 'Analysis')", 1)[0]
    # build.log 1 本だけでなく logs フォルダ全体 + テスト/解析の生ログを配置する。
    assert "Get-ChildItem -Path $logsLocal -File -Recurse" in logs_branch
    assert "fpga-reports" in _script("ci-config.ps1")
    assert "Copy-CiFpgaReports" in _script("ci-fpga.ps1")
    assert "test-output.log" in logs_branch
    assert "analysis-build.log" in logs_branch
    assert "logDir" in logs_branch


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_invoke_cilogged_captures_stdout_stderr_and_exit_code(tmp_path: Path):
    exe = _pwsh()
    scripts = tmp_path / "CISetup" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(
        template_store.bundled_template_dir() / "scripts" / "ci-config.ps1",
        scripts / "ci-config.ps1",
    )

    runner = tmp_path / "run.ps1"
    runner.write_text(
        # 呼び出し元は ErrorActionPreference=Stop（各 ci-*.ps1 と同じ条件）。
        # Windows PowerShell 5.1 はこの状態で native の stderr を 2>&1 すると
        # NativeCommandError で止まってしまうため、その回帰も兼ねる。
        "$ErrorActionPreference = 'Stop'\n"
        "$root = $args[0]\n"
        "$exe = $args[1]\n"
        ". (Join-Path $root 'CISetup/scripts/ci-config.ps1')\n"
        "$log = Get-CiLogPath -Root $root -Name 'build-output.log'\n"
        "$code = Invoke-CiLogged -LogPath $log -FilePath $exe -Label 'stub' -Arguments @(\n"
        "    '-NoProfile', '-Command',\n"
        "    \"Write-Output 'OUT_LINE'; [Console]::Error.WriteLine('ERR_LINE'); exit 7\")\n"
        "Write-Output \"code=$code\"\n"
        "Write-Output \"eap=$ErrorActionPreference\"\n"
        "Write-Output \"log=$log\"\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [exe, "-NoProfile", "-File", str(runner), str(tmp_path), exe],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    assert "code=7" in out, out
    # 呼び出し元の設定を書き換えたままにしない。
    assert "eap=Stop" in out, out

    log_text = (tmp_path / "artifacts" / "logs" / "build-output.log").read_text(encoding="utf-8")
    assert "OUT_LINE" in log_text
    assert "ERR_LINE" in log_text  # stderr も残す（原因はたいていこちら側に出る）
    assert "exit code 7" in log_text


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_ci_build_custom_command_output_lands_in_logs(tmp_path: Path):
    exe = _pwsh()
    deploy_ci_files(tmp_path)
    config = {
        "project": {"name": "LogSample"},
        "build": {
            "profile": "custom",
            "buildCommand": f"& '{exe}' -NoProfile -Command \"Write-Output 'MARKER_FROM_BUILD'\"",
        },
        "storage": {"basePaths": []},
        "jenkins": {"ciFileServers": []},
    }
    (tmp_path / "CISetup" / "cisetup.config.json").write_text(
        json.dumps(config), encoding="utf-8"
    )

    proc = subprocess.run(
        [exe, "-NoProfile", "-File", str(tmp_path / "CISetup" / "scripts" / "ci-build.ps1")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    assert "MARKER_FROM_BUILD" in out  # コンソール（Jenkins の Console Output 相当）にも出る
    log_text = (tmp_path / "artifacts" / "logs" / "build-output.log").read_text(encoding="utf-8")
    assert "MARKER_FROM_BUILD" in log_text  # 同じ内容が logs にも残る


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_copy_fpga_reports_collects_tool_files_and_skips_junk(tmp_path: Path):
    exe = _pwsh()
    scripts = tmp_path / "CISetup" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(
        template_store.bundled_template_dir() / "scripts" / "ci-config.ps1",
        scripts / "ci-config.ps1",
    )
    proj = tmp_path / "hw" / "quartus"
    out = proj / "output_files"
    junk = proj / "incremental_db"
    out.mkdir(parents=True)
    junk.mkdir()
    (out / "top.sta.rpt").write_text("timing fail", encoding="utf-8")
    (proj / "vivado.log").write_text("ERROR: synth", encoding="utf-8")
    (junk / "stale.rpt").write_text("should skip", encoding="utf-8")
    (proj / "huge.rpt").write_bytes(b"x" * 100)
    (tmp_path / "artifacts" / "old").mkdir(parents=True)
    (tmp_path / "artifacts" / "old" / "old.rpt").write_text("skip artifacts", encoding="utf-8")

    runner = tmp_path / "run.ps1"
    runner.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        ". (Join-Path $args[0] 'CISetup/scripts/ci-config.ps1')\n"
        "Copy-CiFpgaReports -Root $args[0] -SearchRoot (Join-Path $args[0] 'hw/quartus') -MaxBytes 50\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [exe, "-NoProfile", "-File", str(runner), str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    out_text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out_text
    dest = tmp_path / "artifacts" / "logs" / "fpga-reports"
    names = {p.name for p in dest.iterdir()} if dest.is_dir() else set()
    assert "output_files__top.sta.rpt" in names
    assert "vivado.log" in names
    assert "stale.rpt" not in names
    assert "huge.rpt" not in names  # MaxBytes 50 で除外
    assert "old.rpt" not in names
    assert "timing fail" in (dest / "output_files__top.sta.rpt").read_text(encoding="utf-8")
