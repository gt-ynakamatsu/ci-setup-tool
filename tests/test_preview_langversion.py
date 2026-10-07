"""device-platform だけ、コンパイル中に LangVersion=preview を許可する一時措置。"""

import shutil
import subprocess
from pathlib import Path

import pytest

from cisetup import template_store


def test_compile_scripts_apply_and_remove_preview_override():
    scripts = template_store.bundled_template_dir() / "scripts"
    config = (scripts / "ci-config.ps1").read_text(encoding="utf-8-sig")
    assert "CustomAfterDirectoryBuildTargets" in config
    assert "DevicePlatform" in config
    assert "function Add-CiPreviewLangVersionOverride" in config
    assert "function Remove-CiPreviewLangVersionOverride" in config
    for name in ("ci-lint.ps1", "ci-build.ps1", "ci-test.ps1", "ci-publish.ps1", "ci-analyze.ps1"):
        text = (scripts / name).read_text(encoding="utf-8-sig")
        assert "Add-CiPreviewLangVersionOverride" in text
        assert "Remove-CiPreviewLangVersionOverride" in text
    archive = (scripts / "ci-archive-source.ps1").read_text(encoding="utf-8-sig")
    assert "Remove-CiPreviewLangVersionOverride" in archive


@pytest.mark.skipif(
    not (shutil.which("powershell") or shutil.which("pwsh")),
    reason="powershell/pwsh が見つからないため preview 上書きの実行テストをスキップ",
)
def test_preview_override_is_scoped_and_removed(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(
        template_store.bundled_template_dir() / "scripts" / "ci-config.ps1",
        scripts / "ci-config.ps1",
    )
    device = tmp_path / "vendor" / "DevicePlatform"
    device.mkdir(parents=True)
    other = tmp_path / "src" / "App"
    other.mkdir(parents=True)
    customer_props = device / "Directory.Build.props"
    customer_props.write_text("<Project />\n", encoding="utf-8")
    customer_targets = device / "Directory.Build.targets"
    customer_targets.write_text("<Project />\n", encoding="utf-8")

    runner = tmp_path / "run.ps1"
    runner.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        ". (Join-Path $args[0] 'ci-config.ps1')\n"
        "if ($args[1] -eq 'add') { Add-CiPreviewLangVersionOverride -Root $args[2] }\n"
        "elseif ($args[1] -eq 'remove') { Remove-CiPreviewLangVersionOverride -Root $args[2] }\n",
        encoding="utf-8",
    )
    exe = "pwsh" if shutil.which("pwsh") else "powershell"

    def run(action: str) -> None:
        proc = subprocess.run(
            [exe, "-NoProfile", "-File", str(runner), str(scripts), action, str(tmp_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout

    override = tmp_path / "artifacts" / "ci" / "device-platform-langversion.targets"
    run("add")
    assert customer_props.read_text(encoding="utf-8") == "<Project />\n"
    assert customer_targets.read_text(encoding="utf-8") == "<Project />\n"
    written = override.read_text(encoding="utf-8")
    assert "<LangVersion>preview</LangVersion>" in written
    assert "$(MSBuildProjectFullPath.Contains('DevicePlatform'))" in written
    assert "CISetup temporary: allow C# preview" in written
    run("remove")
    assert not override.exists()
    assert customer_props.read_text(encoding="utf-8") == "<Project />\n"
    assert not (other / "Directory.Build.props").exists()
