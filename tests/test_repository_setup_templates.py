from __future__ import annotations

import json
from pathlib import Path

import pytest

from cisetup import paths, template_store
from cisetup.config_repository import ConfigRepository
from cisetup.models import CISetupConfig, CISetupSecrets, default_config
from cisetup.project_setup import (
    apply_auto_detection,
    deploy_ci_files,
    has_solution_file,
    looks_like_test_project,
)


# ----------------------------------------------------------- project_setup

def test_looks_like_test_project():
    assert looks_like_test_project("Foo.Tests")
    assert looks_like_test_project("FooTests")
    assert looks_like_test_project("Foo.Test")
    assert not looks_like_test_project("Contest")
    assert not looks_like_test_project("")


def test_has_solution_file(tmp_path: Path):
    assert not has_solution_file(tmp_path)
    (tmp_path / "X.sln").write_text("x", encoding="utf-8")
    assert has_solution_file(tmp_path)


def test_apply_auto_detection(sln_repo: Path):
    cfg = default_config()
    out = apply_auto_detection(sln_repo, cfg)
    assert out.project.name == "MyApp"
    assert out.project.solution_file == "MyApp.sln"
    assert out.jenkins.job_name == "MyApp-CI"
    assert out.project.publish_project.endswith("MyApp.csproj")
    assert out.project.test_project.endswith("MyApp.Tests.csproj")


def test_apply_auto_detection_overwrites_default_jobname_case_insensitive(sln_repo: Path):
    # C# は OrdinalIgnoreCase 比較なので "cisetup-ci" でも上書きされる
    cfg = default_config()
    cfg.jenkins.job_name = "cisetup-ci"
    out = apply_auto_detection(sln_repo, cfg)
    assert out.jenkins.job_name == "MyApp-CI"


def test_apply_auto_detection_keeps_custom_jobname(sln_repo: Path):
    cfg = default_config()
    cfg.jenkins.job_name = "MyCustom-CI"
    out = apply_auto_detection(sln_repo, cfg)
    assert out.jenkins.job_name == "MyCustom-CI"


def test_apply_auto_detection_no_sln(tmp_path: Path):
    cfg = default_config()
    out = apply_auto_detection(tmp_path, cfg)
    assert out is cfg


# ----------------------------------------------------------- template_store

def test_extract_to_repository(tmp_path: Path):
    written = deploy_ci_files(tmp_path)
    assert written
    assert paths.jenkinsfile_path(tmp_path).parent.is_dir()
    # PowerShell スクリプトは BOM 付き
    ps1 = tmp_path / paths.CI_FOLDER / "scripts" / "ci-build.ps1"
    assert ps1.read_bytes().startswith(b"\xef\xbb\xbf")
    # .gitignore に secrets 追記
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "cisetup/cisetup.secrets.local.json" in gi
    assert "cisetup.secrets.local.json" in gi


def test_extract_no_overwrite(tmp_path: Path):
    deploy_ci_files(tmp_path)
    target = tmp_path / paths.CI_FOLDER / "scripts" / "ci-build.ps1"
    target.write_bytes(b"custom")
    deploy_ci_files(tmp_path, overwrite=False)
    assert target.read_bytes() == b"custom"


def test_gitignore_append_existing(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("bin/\n", encoding="utf-8")
    deploy_ci_files(tmp_path)
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "bin/" in gi and "cisetup.secrets.local.json" in gi


def test_gitignore_already_has_marker(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(
        "cisetup/cisetup.secrets.local.json\ncisetup.secrets.local.json\n",
        encoding="utf-8",
    )
    deploy_ci_files(tmp_path)
    lines = [
        line.strip()
        for line in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines.count("cisetup/cisetup.secrets.local.json") == 1
    assert lines.count("cisetup.secrets.local.json") == 1


def test_read_template_missing():
    with pytest.raises(FileNotFoundError):
        template_store.read_template("nope.template")


# --------------------------------------------------------- config_repository

def _valid_config(sln_repo: Path) -> CISetupConfig:
    cfg = default_config()
    cfg = apply_auto_detection(sln_repo, cfg)
    cfg.git.repository_url = "https://git.example.com/x.git"
    return cfg


def test_save_all_and_load(sln_repo: Path):
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    sec = CISetupSecrets(jenkins_url="http://j", jenkins_user="u", jenkins_api_token="t")
    repo.save_all(sln_repo, cfg, sec)

    saved = json.loads(paths.config_path(sln_repo).read_text(encoding="utf-8"))
    assert "agentLabel" in saved["jenkins"]

    loaded = repo.load_config(sln_repo)
    assert loaded.project.name == "MyApp"
    loaded_sec = repo.load_secrets(sln_repo)
    assert loaded_sec.jenkins_url == "http://j"

    jf = paths.jenkinsfile_path(sln_repo).read_text(encoding="utf-8")
    assert "pipeline" in jf
    assert not jf.startswith("\ufeff")


def test_build_preview_paths_with_base(sln_repo: Path):
    # ④ CI_FILE_SERVER が空なら base_path を「そのまま」使う（後勝ちで base_path が実効値）
    repo = ConfigRepository()
    cfg = default_config()
    cfg.jenkins.ci_file_server = ""
    cfg.storage.base_path = r"\\srv\share\MyApp"
    cfg.storage.use_date_subfolder = True
    logs, releases, tests = repo.build_preview_paths(cfg, date_folder="20260101")
    assert logs == r"\\srv\share\MyApp\logs\20260101"
    assert releases == r"\\srv\share\MyApp\releases\20260101"
    assert tests == r"\\srv\share\MyApp\tests\20260101"


def test_build_preview_paths_ci_file_server_wins_over_base(sln_repo: Path):
    # 両方非空（レガシー設定のロード直後）のときは file_server を決定的タイブレークとして使う
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_server = r"\\fileserver\ci"
    cfg.storage.base_path = r"\\srv\share\Stale"
    cfg.storage.use_date_subfolder = False
    logs, releases, tests = repo.build_preview_paths(cfg)
    assert logs == r"\\fileserver\ci\MyApp\logs"
    assert releases == r"\\fileserver\ci\MyApp\releases"
    assert tests == r"\\fileserver\ci\MyApp\tests"


def test_build_preview_paths_without_base(sln_repo: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_server = r"\\fileserver\ci"
    cfg.storage.use_date_subfolder = False
    logs, releases, tests = repo.build_preview_paths(cfg)
    assert logs == r"\\fileserver\ci\MyApp\logs"
    assert releases == r"\\fileserver\ci\MyApp\releases"
    assert tests == r"\\fileserver\ci\MyApp\tests"


def test_build_preview_paths_url_base(sln_repo: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.jenkins.ci_file_server = ""
    cfg.storage.base_path = "https://contoso.sharepoint.com/sites/team/MyApp"
    cfg.storage.use_date_subfolder = True
    logs, releases, tests = repo.build_preview_paths(cfg, date_folder="20260101")
    assert logs == "https://contoso.sharepoint.com/sites/team/MyApp/logs/20260101"
    assert releases == "https://contoso.sharepoint.com/sites/team/MyApp/releases/20260101"
    assert tests == "https://contoso.sharepoint.com/sites/team/MyApp/tests/20260101"


def test_validate_rejects_url_write_target(sln_repo: Path):
    # base_path が実効書き込み先（④ が空）のとき、URL は拒否される
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_server = ""
    cfg.storage.base_path = "https://contoso.sharepoint.com/:f:/s/share/xxx"
    with pytest.raises(ValueError, match="UNC またはローカルパス"):
        repo.validate(cfg, sln_repo)


def test_validate_rejects_url_in_ci_file_server(sln_repo: Path):
    # base_path 未指定で CI_FILE_SERVER に Web URL を入れた場合も拒否する
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.storage.base_path = ""
    cfg.jenkins.ci_file_server = "https://contoso.sharepoint.com/sites/team"
    with pytest.raises(ValueError, match="UNC またはローカルパス"):
        repo.validate(cfg, sln_repo)


def test_validate_ci_file_server_wins_over_stale_base_path_url(sln_repo: Path):
    # 後勝ちのレガシータイブレーク: 両方非空なら file_server が実効値となり、
    # base_path に古い URL が残っていても使われないためエラーにならない。
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_server = r"\\fileserver\ci"
    cfg.storage.base_path = "https://contoso.sharepoint.com/sites/team/MyApp"
    repo.validate(cfg, sln_repo)  # 例外が出ないこと（④ が優先）


def test_validate_names_ci_file_server_when_url(sln_repo: Path):
    # ④ CI_FILE_SERVER 自体が URL のときは ④ を名指しして拒否する
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_server = "https://contoso.sharepoint.com/sites/team"
    with pytest.raises(ValueError, match="CI_FILE_SERVER"):
        repo.validate(cfg, sln_repo)


def test_validate_accepts_onedrive_local_base_path(sln_repo: Path):
    # ④ が空のとき、同期済み OneDrive のローカルパス（スペース・ハイフン・日本語）は通る
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_server = ""
    cfg.storage.base_path = r"C:\Users\taro\OneDrive - 会社名\CI\MyApp"
    repo.validate(cfg, sln_repo)  # 例外が出ないこと


def test_validate_accepts_unc_ci_file_server(sln_repo: Path):
    # base_path 未指定でも UNC の CI_FILE_SERVER は通る
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.storage.base_path = ""
    cfg.jenkins.ci_file_server = r"\\fileserver\ci\MyApp"
    repo.validate(cfg, sln_repo)  # 例外が出ないこと


def test_validate_accepts_drive_letter_base_path(sln_repo: Path):
    # ④ が空のとき、ドライブ文字始まりの通常ローカルパスも通る
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_server = ""
    cfg.storage.base_path = r"D:\日本語 パス-test\CI"
    repo.validate(cfg, sln_repo)  # 例外が出ないこと


def test_validate_requires_write_target(sln_repo: Path):
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.storage.base_path = ""
    cfg.jenkins.ci_file_server = ""
    with pytest.raises(ValueError, match="書き込み先"):
        repo.validate(cfg, sln_repo)


def test_save_all_keeps_personal_paths_out_of_git(sln_repo: Path):
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.storage.base_path = r"C:\Users\taro\OneDrive - Co\CI\MyApp"
    cfg.jenkins.ci_file_server = r"\\fileserver\ci"
    cfg.git.repository_url = "http://taro@172.29.162.37/kallithea/x/ipu-test-app"
    sec = CISetupSecrets()
    repo.save_all(sln_repo, cfg, sec)

    # コミットされる config.json には個人 ID 入りの書き込み先・URL ユーザー名を残さない
    saved = json.loads(paths.config_path(sln_repo).read_text(encoding="utf-8"))
    assert saved["storage"]["basePath"] == ""
    assert saved["jenkins"]["ciFileServer"] == ""
    assert saved["git"]["repositoryUrl"] == "http://172.29.162.37/kallithea/x/ipu-test-app"
    assert "taro" not in json.dumps(saved)

    # ローカルファイル（git 非追跡）に書き込み先が保存される
    local = json.loads(paths.local_path(sln_repo).read_text(encoding="utf-8"))
    assert local["basePath"] == r"C:\Users\taro\OneDrive - Co\CI\MyApp"
    assert local["ciFileServer"] == r"\\fileserver\ci"

    # ユーザー名は secrets に移動
    saved_sec = json.loads(paths.secrets_path(sln_repo).read_text(encoding="utf-8"))
    assert saved_sec["gitUsername"] == "taro"

    # Jenkinsfile に個人パスが焼き込まれない
    jf = paths.jenkinsfile_path(sln_repo).read_text(encoding="utf-8")
    assert "taro" not in jf
    assert "OneDrive" not in jf


def test_load_config_overlays_local(sln_repo: Path):
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.storage.base_path = r"C:\Users\taro\OneDrive\CI"
    cfg.jenkins.ci_file_server = r"\\srv\ci"
    repo.save_all(sln_repo, cfg, CISetupSecrets())

    loaded = repo.load_config(sln_repo)
    assert loaded.storage.base_path == r"C:\Users\taro\OneDrive\CI"
    assert loaded.jenkins.ci_file_server == r"\\srv\ci"


def test_validate_requires_name(sln_repo: Path):
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.project.name = ""
    with pytest.raises(ValueError, match="プロジェクト名"):
        repo.validate(cfg, sln_repo)


def test_validate_custom_requires_build_command(sln_repo: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "X"
    cfg.build.profile = "custom"
    cfg.build.build_command = ""
    with pytest.raises(ValueError, match="ビルド コマンド"):
        repo.validate(cfg, sln_repo)


def test_validate_missing_solution(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "X"
    cfg.project.solution_file = "missing.sln"
    cfg.project.publish_project = "missing.csproj"
    cfg.project.artifact_prefix = "X"
    with pytest.raises(ValueError, match="ソリューションファイルが見つかりません"):
        repo.validate(cfg, tmp_path)


def test_validate_custom_skips_file_checks(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "X"
    cfg.build.profile = "custom"
    cfg.build.build_command = "make"
    # custom はファイル存在チェックをスキップするので例外なし
    repo.validate(cfg, tmp_path)


def test_load_legacy_flat(tmp_path: Path):
    repo = ConfigRepository()
    (tmp_path / "ci.settings.json").write_text(
        json.dumps({"projectName": "Legacy", "solutionFile": "Legacy.sln"}),
        encoding="utf-8",
    )
    cfg = repo.load_config(tmp_path)
    assert cfg.project.name == "Legacy"


def test_load_config_default_when_missing(tmp_path: Path):
    repo = ConfigRepository()
    cfg = repo.load_config(tmp_path)
    assert cfg.project.name == "YourProject"


def test_load_secrets_default_when_missing(tmp_path: Path):
    repo = ConfigRepository()
    sec = repo.load_secrets(tmp_path)
    assert sec.jenkins_url == ""


def test_find_repository_root_method(sln_repo: Path):
    repo = ConfigRepository()
    assert repo.find_repository_root(sln_repo) == sln_repo.resolve()
