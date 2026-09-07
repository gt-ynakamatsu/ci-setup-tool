from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from cisetup.ci_preset_catalog import PRESETS, find_preset, is_fpga_preset
from cisetup.config_repository import ConfigRepository
from cisetup.models import default_config
from cisetup.project_setup import deploy_ci_files
from cisetup.template_store import BUNDLED_FILES, bundled_template_dir


def test_fpga_preset_ids_and_empty_build_command():
    assert is_fpga_preset("fpga-vivado")
    assert is_fpga_preset("FPGA-QUARTUS")
    assert not is_fpga_preset("dotnet")
    assert not is_fpga_preset("custom-empty")
    vivado = find_preset("fpga-vivado")
    quartus = find_preset("fpga-quartus")
    assert vivado is not None and quartus is not None
    assert vivado.profile == "custom" and quartus.profile == "custom"
    assert vivado.build_command == ""
    assert quartus.build_command == ""
    assert "*.bit" in vivado.artifact_glob or "**/*.bit" in vivado.artifact_glob
    assert ".sof" in quartus.artifact_glob


def test_validate_fpga_allows_empty_build_command():
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "FpgaApp"
    cfg.build.profile = "custom"
    cfg.build.preset = "fpga-vivado"
    cfg.build.build_command = ""
    repo.validate(cfg, Path("."))


def test_validate_non_fpga_custom_still_requires_command():
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "X"
    cfg.build.profile = "custom"
    cfg.build.preset = "custom-empty"
    cfg.build.build_command = ""
    with pytest.raises(ValueError, match="ビルド コマンド"):
        repo.validate(cfg, Path("."))


def test_ci_fpga_is_bundled_and_deployed(tmp_path: Path):
    assert "scripts/ci-fpga.ps1" in BUNDLED_FILES
    src = bundled_template_dir() / "scripts" / "ci-fpga.ps1"
    text = src.read_text(encoding="utf-8-sig")
    assert "Find-VivadoExe" in text
    assert "Find-QuartusSh" in text
    assert "DryRun" in text
    assert "-Recurse" in text
    assert "Test-IgnoredSearchPath" in text
    (tmp_path / "dummy.sln").write_text("x", encoding="utf-8")
    deploy_ci_files(tmp_path)
    deployed = tmp_path / "CISetup" / "scripts" / "ci-fpga.ps1"
    assert deployed.is_file()
    build = (tmp_path / "CISetup" / "scripts" / "ci-build.ps1").read_text(encoding="utf-8-sig")
    assert "fpga-" in build
    assert "ci-fpga.ps1" in build


def _pwsh() -> str | None:
    for name in ("pwsh", "powershell"):
        path = shutil.which(name)
        if path:
            return path
    return None


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_ci_fpga_dryrun_detects_quartus_project(tmp_path: Path):
    deploy_ci_files(tmp_path)
    (tmp_path / "blink.qpf").write_text("dummy", encoding="utf-8")
    script = tmp_path / "CISetup" / "scripts" / "ci-fpga.ps1"
    proc = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(script), "-Tool", "Quartus", "-DryRun"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    assert "tool=Quartus" in out
    assert "project=blink" in out


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_ci_fpga_dryrun_requires_vivado_inputs(tmp_path: Path):
    deploy_ci_files(tmp_path)
    script = tmp_path / "CISetup" / "scripts" / "ci-fpga.ps1"
    proc = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(script), "-Tool", "Vivado", "-DryRun"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "build.tcl" in out or ".xpr" in out


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_ci_fpga_dryrun_finds_quartus_in_subdir(tmp_path: Path):
    deploy_ci_files(tmp_path)
    nested = tmp_path / "hw" / "quartus"
    nested.mkdir(parents=True)
    (nested / "blink.qpf").write_text("dummy", encoding="utf-8")
    script = tmp_path / "CISetup" / "scripts" / "ci-fpga.ps1"
    proc = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(script), "-Tool", "Quartus", "-DryRun"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    assert "project=blink" in out
    assert "hw/quartus/blink.qpf" in out.replace("\\", "/")


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_ci_fpga_dryrun_finds_vivado_tcl_in_subdir(tmp_path: Path):
    deploy_ci_files(tmp_path)
    nested = tmp_path / "fpga" / "vivado"
    nested.mkdir(parents=True)
    (nested / "build.tcl").write_text("puts hi", encoding="utf-8")
    script = tmp_path / "CISetup" / "scripts" / "ci-fpga.ps1"
    proc = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(script), "-Tool", "Vivado", "-DryRun"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    assert "kind=tcl" in out
    assert "build.tcl" in out


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_ci_fpga_dryrun_ignores_qpf_under_artifacts(tmp_path: Path):
    deploy_ci_files(tmp_path)
    junk = tmp_path / "artifacts" / "old"
    junk.mkdir(parents=True)
    (junk / "stale.qpf").write_text("dummy", encoding="utf-8")
    nested = tmp_path / "rtl"
    nested.mkdir()
    (nested / "top.qpf").write_text("dummy", encoding="utf-8")
    script = tmp_path / "CISetup" / "scripts" / "ci-fpga.ps1"
    proc = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(script), "-Tool", "Quartus", "-DryRun"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    assert "project=top" in out
    assert "stale" not in out


@pytest.mark.skipif(_pwsh() is None, reason="PowerShell が無い")
def test_ci_fpga_dryrun_multiple_qpf_requires_project(tmp_path: Path):
    deploy_ci_files(tmp_path)
    a = tmp_path / "board_a"
    b = tmp_path / "board_b"
    a.mkdir()
    b.mkdir()
    (a / "top.qpf").write_text("dummy", encoding="utf-8")
    (b / "top.qpf").write_text("dummy", encoding="utf-8")
    script = tmp_path / "CISetup" / "scripts" / "ci-fpga.ps1"
    proc = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(script), "-Tool", "Quartus", "-DryRun"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "-Project" in out

    proc2 = subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(script), "-Tool", "Quartus", "-Project", "board_b/top.qpf", "-DryRun"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    out2 = (proc2.stdout or "") + (proc2.stderr or "")
    assert proc2.returncode == 0, out2
    assert "board_b/top.qpf" in out2.replace("\\", "/")


def test_preset_count_still_six():
    assert len(PRESETS) == 6


def test_ci_build_treats_dash_prefix_as_helper_options():
    # ビルドコマンド欄は '-' 始まりならヘルパーのオプション、それ以外は独自コマンド。
    build = (bundled_template_dir() / "scripts" / "ci-build.ps1").read_text(encoding="utf-8-sig")
    assert "$extra.StartsWith('-')" in build
    assert "-Project" in build and "-Tcl" in build
