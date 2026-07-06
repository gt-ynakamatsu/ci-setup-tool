from __future__ import annotations

import json
from pathlib import Path

import pytest

from cisetup import paths, template_store
from cisetup.config_repository import ConfigRepository
from cisetup.models import CISetupConfig, CISetupSecrets, default_config
from cisetup.project_setup import (
    apply_auto_detection,
    count_projects,
    deploy_ci_files,
    find_test_project,
    has_solution_file,
    looks_like_test_project,
    parse_solution_projects,
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


def test_apply_auto_detection_redetects_invalid_publish(sln_repo: Path):
    # 実在しない publish/未設定 test は再検出で差し替え・補完される
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.project.solution_file = "MyApp.sln"
    cfg.project.artifact_prefix = "MyApp"
    cfg.project.publish_project = "IpuTestApp/IpuTestApp.csproj"  # 存在しない
    cfg.project.test_project = ""
    out = apply_auto_detection(sln_repo, cfg)
    assert out.project.publish_project.endswith("MyApp.csproj")
    assert "IpuTestApp" not in out.project.publish_project
    assert out.project.test_project.endswith("MyApp.Tests.csproj")


def test_apply_auto_detection_keeps_valid_publish(sln_repo: Path):
    # 実在する publish は再検出でも保持される
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.project.solution_file = "MyApp.sln"
    cfg.project.artifact_prefix = "MyApp"
    cfg.project.publish_project = "src/MyApp/MyApp.csproj"  # 実在
    out = apply_auto_detection(sln_repo, cfg)
    assert out.project.publish_project == "src/MyApp/MyApp.csproj"


def _sln_with_projects(*entries: tuple[str, str]) -> str:
    """(プロジェクト名, sln相対csprojパス) から .sln テキストを生成。"""
    lines = ["Microsoft Visual Studio Solution File, Format Version 12.00"]
    for name, path in entries:
        lines.append(
            'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = '
            f'"{name}", "{path}", '
            '"{11111111-2222-3333-4444-555555555555}"'
        )
        lines.append("EndProject")
    return "\n".join(lines) + "\n"


def test_parse_solution_projects():
    text = _sln_with_projects(
        ("App", r"deep\nested\App.csproj"),
        ("App.Tests", r"qa\App.Tests.csproj"),
    )
    # ソリューションフォルダ（csproj でない）は無視される
    text += (
        'Project("{2150E333-8FDC-42A3-9474-1A3956D46DE8}") = '
        '"SolutionItems", "SolutionItems", "{AAAA}"\nEndProject\n'
    )
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        sln = Path(tmp) / "App.sln"
        sln.write_text(text, encoding="utf-8")
        got = parse_solution_projects(sln)
    assert got == [r"deep\nested\App.csproj", r"qa\App.Tests.csproj"]


def test_apply_auto_detection_uses_sln_for_nonadjacent_csproj(tmp_path: Path):
    # csproj が .sln と別階層にある構成。.sln 解析で正しいパスを特定する。
    (tmp_path / "deep" / "nested").mkdir(parents=True)
    (tmp_path / "deep" / "nested" / "IpuTestApp.csproj").write_text("<Project/>", encoding="utf-8")
    (tmp_path / "qa").mkdir()
    (tmp_path / "qa" / "IpuTestAppCore.Tests.csproj").write_text("<Project/>", encoding="utf-8")
    (tmp_path / "IpuTestApp.sln").write_text(
        _sln_with_projects(
            ("IpuTestApp", r"deep\nested\IpuTestApp.csproj"),
            ("IpuTestAppCore.Tests", r"qa\IpuTestAppCore.Tests.csproj"),
        ),
        encoding="utf-8",
    )
    cfg = default_config()
    cfg.project.name = "IpuTestApp"
    cfg.project.solution_file = "IpuTestApp.sln"
    cfg.project.artifact_prefix = "IpuTestApp"
    cfg.project.publish_project = "IpuTestApp/IpuTestApp.csproj"  # 旧・実在しない
    cfg.project.test_project = ""
    out = apply_auto_detection(tmp_path, cfg)
    assert out.project.publish_project == "deep/nested/IpuTestApp.csproj"
    assert out.project.test_project == "qa/IpuTestAppCore.Tests.csproj"


def test_publish_detection_is_name_independent_prefers_executable(tmp_path: Path):
    # ソリューション名・プロジェクト名が一致しなくても、実行アプリ(WinExe)を選ぶ。
    (tmp_path / "App").mkdir()
    (tmp_path / "App" / "CoreLib.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup></PropertyGroup></Project>',
        encoding="utf-8",
    )
    (tmp_path / "Main").mkdir()
    (tmp_path / "Main" / "IpuTestAppCore.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
        "<OutputType>WinExe</OutputType></PropertyGroup></Project>",
        encoding="utf-8",
    )
    (tmp_path / "IpuTestApp.sln").write_text(
        _sln_with_projects(
            ("CoreLib", r"App\CoreLib.csproj"),
            ("IpuTestAppCore", r"Main\IpuTestAppCore.csproj"),
        ),
        encoding="utf-8",
    )
    cfg = default_config()
    cfg.project.name = "IpuTestApp"  # 名前は publish と一致しない
    cfg.project.solution_file = "IpuTestApp.sln"
    cfg.project.artifact_prefix = "IpuTestApp"
    cfg.project.publish_project = ""
    out = apply_auto_detection(tmp_path, cfg)
    # ライブラリ(CoreLib)が先頭でも、実行アプリ(IpuTestAppCore)が選ばれる
    assert out.project.publish_project == "Main/IpuTestAppCore.csproj"


def test_count_projects(sln_repo: Path):
    # dummy sln（Project 行なし）なので rglob フォールバックで 2 件
    assert count_projects(sln_repo) == 2


def test_find_publish_project_skips_test_project(tmp_path: Path):
    # 非テストの csproj が無くテストのみの場合を除き、publish にはテストを選ばない
    (tmp_path / "App.sln").write_text("x", encoding="utf-8")
    app = tmp_path / "App"
    app.mkdir()
    (app / "App.csproj").write_text("<Project/>", encoding="utf-8")
    tst = tmp_path / "App.Tests"
    tst.mkdir()
    (tst / "App.Tests.csproj").write_text("<Project/>", encoding="utf-8")
    cfg = default_config()
    cfg.project.publish_project = ""  # 強制再検出
    cfg.project.name = "App"
    out = apply_auto_detection(tmp_path, cfg)
    assert out.project.publish_project.endswith("App.csproj")
    assert "Tests" not in out.project.publish_project


def test_find_test_project(sln_repo: Path):
    found = find_test_project(sln_repo, "MyApp")
    assert found is not None
    assert found.endswith("MyApp.Tests.csproj")


def test_find_test_project_none(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.csproj").write_text("<Project/>", encoding="utf-8")
    assert find_test_project(tmp_path) is None


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
    assert "CISetup/cisetup.secrets.local.json" in gi
    assert "cisetup.secrets.local.json" in gi


def test_bundled_ps1_sources_are_utf8_bom():
    # Windows PowerShell 5.1 は BOM なし UTF-8 を Shift-JIS 扱いして日本語を文字化け/構文崩れさせる。
    # 同梱ソースの .ps1 はすべて UTF-8 BOM 付きで統一しておく（配置時の付与に依存しない正本側の保証）。
    scripts_dir = template_store.bundled_template_dir() / "scripts"
    ps1_files = sorted(scripts_dir.glob("*.ps1"))
    assert ps1_files, "同梱スクリプトが見つかりません"
    missing = [p.name for p in ps1_files if not p.read_bytes().startswith(b"\xef\xbb\xbf")]
    assert not missing, f"BOM なしの .ps1 があります: {missing}"


def test_notify_teams_uses_toarray_for_actions_list():
    # Windows PowerShell 5.1 では、関数内で要素を追加した List[object] を
    # @(...) で配列化すると "Argument types do not match" になる既知の不具合がある。
    # ci-notify-teams.ps1 の actions は ToArray() で配列化していること（@($actions) は禁止）。
    script = template_store.bundled_template_dir() / "scripts" / "ci-notify-teams.ps1"
    text = script.read_text(encoding="utf-8-sig")
    assert "@($actions)" not in text, "List[object] を @(...) で配列化すると 5.1 でクラッシュする"
    assert "$actions.ToArray()" in text, "actions は ToArray() で配列化すること"


def test_bundled_ps1_no_array_op_on_generic_lists():
    # New-Object / ::new() で作った Generic.List 変数を @(...) で配列化していないことを保証する。
    import re

    scripts_dir = template_store.bundled_template_dir() / "scripts"
    list_decl = re.compile(
        r"\$(\w+)\s*=\s*(?:New-Object\s+System\.Collections\.Generic\.List"
        r"|\[System\.Collections\.Generic\.List\[[^\]]+\]\]::new)",
        re.IGNORECASE,
    )
    offenders: list[str] = []
    for ps1 in sorted(scripts_dir.glob("*.ps1")):
        text = ps1.read_text(encoding="utf-8-sig")
        list_vars = set(list_decl.findall(text))
        # パラメータとして List 型を受け取る変数も対象に含める。
        list_vars |= set(
            re.findall(
                r"\[System\.Collections\.Generic\.List\[[^\]]+\]\]\$(\w+)",
                text,
                re.IGNORECASE,
            )
        )
        for var in list_vars:
            # @($var) はクラッシュ要因。@($var | ...) のようなパイプライン化は安全なので除外する。
            if re.search(r"@\(\s*\$" + re.escape(var) + r"\s*\)", text):
                offenders.append(f"{ps1.name}: @(${var})")
    assert not offenders, f"Generic.List を @(...) で配列化しています: {offenders}"


def test_ci_config_exposes_analysis_dir():
    # ci-config.ps1 は storage.analysisDir を読み、既定 'analysis' で AnalysisDir を公開する。
    script = template_store.bundled_template_dir() / "scripts" / "ci-config.ps1"
    text = script.read_text(encoding="utf-8-sig")
    assert "$storage.analysisDir" in text
    assert "AnalysisDir = (ConvertTo-PlatformPath" in text


def test_deploy_analysis_dest_uses_configured_folder():
    # 解析の配置先フォルダ名は設定値 $ci.AnalysisDir を使う（ハードコード 'analysis' 廃止）。
    # 入力元のローカル変数 artifacts/analysis はハードコードのまま（別物）。
    script = template_store.bundled_template_dir() / "scripts" / "ci-deploy-fileserver.ps1"
    text = script.read_text(encoding="utf-8-sig")
    assert "Get-CategoryDest -Target $t -CategoryDir $ci.AnalysisDir" in text
    assert "-CategoryDir 'analysis'" not in text
    # 入力元（ビルドが解析レポートを出力する artifacts/analysis）は従来どおり。
    assert "Join-PathMulti $ci.Root @('artifacts', 'analysis')" in text


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
        "CISetup/cisetup.secrets.local.json\ncisetup.secrets.local.json\n",
        encoding="utf-8",
    )
    deploy_ci_files(tmp_path)
    lines = [
        line.strip()
        for line in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines.count("CISetup/cisetup.secrets.local.json") == 1
    assert lines.count("cisetup.secrets.local.json") == 1


def test_read_template_missing():
    with pytest.raises(FileNotFoundError):
        template_store.read_template("nope.template")


def test_read_template_nested_forward_slash_path():
    # BUNDLED_FILES は "/" 区切り。バックスラッシュへ変換せずそのまま渡しても
    # サブフォルダ内のファイルを解決できること（Linux では変換すると単一ファイル名に
    # 誤解釈されて壊れるため、変換しないことが正しい実装）。
    text = template_store.read_template("scripts/ci-build.ps1")
    assert text.strip()


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
    # 生成 Jenkinsfile は新フォルダ CISetup/scripts を参照する
    assert "./CISetup/scripts/" in jf
    assert "./cisetup/scripts/" not in jf


def test_save_all_writes_into_cisetup_folder(sln_repo: Path):
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    repo.save_all(sln_repo, cfg, CISetupSecrets())
    # 新規保存は CISetup/ 配下（大文字 C）
    assert (sln_repo / "CISetup" / paths.CONFIG_FILE).is_file()


def test_save_all_migrates_legacy_cisetup_folder(sln_repo: Path):
    # 既存プロジェクト（旧 cisetup/ 展開済み）を用意し、保存で CISetup/ へ移行されること。
    legacy = sln_repo / "cisetup"
    legacy.mkdir()
    (legacy / paths.CONFIG_FILE).write_text(
        json.dumps({"project": {"name": "MyApp"}}), encoding="utf-8"
    )
    (legacy / "keepme.txt").write_text("legacy-marker", encoding="utf-8")

    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    repo.save_all(sln_repo, cfg, CISetupSecrets())

    # 実体のディレクトリ名が CISetup（正しいケース）に移行されていること。
    ci = paths.find_ci_dir(sln_repo)
    assert ci is not None and ci.name == "CISetup"
    # 旧フォルダの中身（git 非追跡ファイル等）が保持されていること。
    assert (ci / "keepme.txt").read_text(encoding="utf-8") == "legacy-marker"
    assert (ci / paths.CONFIG_FILE).is_file()


def test_load_config_reads_legacy_cisetup_layout(sln_repo: Path):
    # 旧 cisetup/ レイアウトのままでも load_config で読めること（後方互換）。
    legacy = sln_repo / "cisetup"
    legacy.mkdir()
    (legacy / paths.CONFIG_FILE).write_text(
        json.dumps({"project": {"name": "LegacyProj"}}), encoding="utf-8"
    )
    repo = ConfigRepository()
    loaded = repo.load_config(sln_repo)
    assert loaded.project.name == "LegacyProj"


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
    # ユニットテストも他カテゴリと同じ入れ子 <fileServer>/<project>/<testsDir>
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
    # ユニットテストも releases/logs と同じプロジェクト配下の入れ子
    assert tests == r"\\fileserver\ci\MyApp\tests"


def test_build_preview_tests_separated_with_date(sln_repo: Path):
    # 他カテゴリと同じ入れ子＋日付サブフォルダ: <fileServer>/<project>/<testsDir>/<date>
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_server = r"\\fileserver\ci"
    cfg.storage.use_date_subfolder = True
    _, releases, tests = repo.build_preview_paths(cfg, date_folder="20260101")
    # releases も tests も同じくプロジェクト配下（カテゴリのみ異なる）
    assert releases == r"\\fileserver\ci\MyApp\releases\20260101"
    assert tests == r"\\fileserver\ci\MyApp\tests\20260101"


def test_build_source_preview(sln_repo: Path):
    # 開発環境 zip は releases / logs と同じ category 構造（<root>/<sourceDir>[/date]）
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_server = r"\\fileserver\ci"
    cfg.storage.use_date_subfolder = True
    cfg.storage.source_dir = "source"
    assert repo.build_source_preview(cfg, date_folder="20260101") == (
        r"\\fileserver\ci\MyApp\source\20260101"
    )
    # base_path のみ・日付なし・カスタムフォルダ名
    cfg.jenkins.ci_file_server = ""
    cfg.storage.base_path = r"\\srv\share\MyApp"
    cfg.storage.use_date_subfolder = False
    cfg.storage.source_dir = "src-snap"
    assert repo.build_source_preview(cfg) == r"\\srv\share\MyApp\src-snap"


def test_build_target_roots_multiple_mixed(sln_repo: Path):
    # ④ CI_FILE_SERVER 群はプロジェクト名を付与、書き込み先ベース群はそのまま。重複ルートは除外。
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = [r"\\fileserver\ci", r"\\fs2\ci"]
    cfg.storage.base_paths = [r"D:\onedrive\MyApp", r"\\fileserver\ci\MyApp"]
    roots = repo.build_target_roots(cfg)
    assert (r"\\fileserver\ci", r"\\fileserver\ci\MyApp") in roots
    assert (r"\\fs2\ci", r"\\fs2\ci\MyApp") in roots
    assert (r"D:\onedrive\MyApp", r"D:\onedrive\MyApp") in roots
    # base_path が ④ の実効ルートと重複する場合は除外される
    resolved = [root for _, root in roots]
    assert resolved.count(r"\\fileserver\ci\MyApp") == 1


def test_create_storage_folders_default_categories(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = []
    cfg.storage.base_paths = [str(tmp_path)]
    cfg.storage.archive_source = False
    result = repo.create_storage_folders(cfg)
    for cat in ("releases", "logs", "analysis", "tests"):
        assert (tmp_path / cat).is_dir()
        assert str(tmp_path / cat) in result.created
    # archive_source が False なら source は作られない
    assert not (tmp_path / "source").exists()
    assert result.failed == []
    assert result.skipped_urls == []
    # 日付サブフォルダは作られない
    assert not (tmp_path / "releases" / "YYYYMMDD").exists()


def test_create_storage_folders_archive_source(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = []
    cfg.storage.base_paths = [str(tmp_path)]
    cfg.storage.archive_source = True
    result = repo.create_storage_folders(cfg)
    assert (tmp_path / "source").is_dir()
    assert str(tmp_path / "source") in result.created


def test_storage_folder_exists_respects_enable_and_path(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = []
    cfg.storage.base_paths = [str(tmp_path)]
    cfg.storage.enable_analysis = False
    assert repo.storage_folder_exists(cfg, "analysis") is False
    cfg.storage.enable_analysis = True
    assert repo.storage_folder_exists(cfg, "analysis") is False
    (tmp_path / "analysis").mkdir()
    assert repo.storage_folder_exists(cfg, "analysis") is True


def test_create_storage_folders_respects_disabled_categories(tmp_path: Path):
    # 無効化したカテゴリはフォルダを作らない
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = []
    cfg.storage.base_paths = [str(tmp_path)]
    cfg.storage.enable_logs = False
    cfg.storage.enable_analysis = False
    cfg.storage.enable_releases = True
    cfg.storage.enable_tests = True
    result = repo.create_storage_folders(cfg)
    assert (tmp_path / "releases").is_dir()
    assert (tmp_path / "tests").is_dir()
    assert not (tmp_path / "logs").exists()
    assert not (tmp_path / "analysis").exists()
    assert str(tmp_path / "logs") not in result.created
    assert str(tmp_path / "analysis") not in result.created


def test_create_storage_folders_custom_category_name(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = []
    cfg.storage.base_paths = [str(tmp_path)]
    cfg.storage.analysis_dir = "解析"
    result = repo.create_storage_folders(cfg)
    assert (tmp_path / "解析").is_dir()
    assert not (tmp_path / "analysis").exists()
    assert str(tmp_path / "解析") in result.created


def test_create_storage_folders_ci_file_server_adds_project(tmp_path: Path):
    # ④ CI_FILE_SERVER 系はルートに project 名が付く（<base>/<project>/releases）
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = [str(tmp_path)]
    cfg.storage.base_paths = []
    repo.create_storage_folders(cfg)
    assert (tmp_path / "MyApp" / "releases").is_dir()
    assert (tmp_path / "MyApp" / "logs").is_dir()
    # base 直下（project 名なし）には作られない
    assert not (tmp_path / "releases").exists()


def test_create_storage_folders_base_path_no_project(tmp_path: Path):
    # 書き込み先ベース系は project 名を付けずそのまま <base>/releases
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = []
    cfg.storage.base_paths = [str(tmp_path)]
    repo.create_storage_folders(cfg)
    assert (tmp_path / "releases").is_dir()
    assert not (tmp_path / "MyApp").exists()


def test_create_storage_folders_skips_url_target(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = []
    cfg.storage.base_paths = [
        str(tmp_path),
        "https://contoso.sharepoint.com/sites/team/MyApp",
    ]
    result = repo.create_storage_folders(cfg)
    # ローカルパス側は作られる
    assert (tmp_path / "releases").is_dir()
    # URL 側はスキップされ、作成結果に出ない
    assert "https://contoso.sharepoint.com/sites/team/MyApp" in result.skipped_urls
    assert all(not p.startswith("http") for p in result.created)


def test_create_storage_folders_empty_when_all_urls(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.project.name = "MyApp"
    cfg.jenkins.ci_file_servers = []
    cfg.storage.base_paths = ["https://contoso.sharepoint.com/sites/team/MyApp"]
    result = repo.create_storage_folders(cfg)
    assert result.created == []
    assert result.skipped_urls == ["https://contoso.sharepoint.com/sites/team/MyApp"]


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


def test_validate_rejects_url_in_any_target(sln_repo: Path):
    # 複数書き込み先は全先へコピーするため、いずれの欄でも URL は拒否される
    # （旧「後勝ち」のように URL を黙って無視しない）。
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_servers = [r"\\fileserver\ci"]
    cfg.storage.base_paths = ["https://contoso.sharepoint.com/sites/team/MyApp"]
    with pytest.raises(ValueError, match="UNC またはローカルパス"):
        repo.validate(cfg, sln_repo)


def test_validate_accepts_multiple_write_targets(sln_repo: Path):
    # ④ CI_FILE_SERVER と書き込み先ベースは併用でき、全てがローカル/UNC なら通る
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_servers = [r"\\srv1\ci", r"\\srv2\ci"]
    cfg.storage.base_paths = [r"C:\Users\me\OneDrive - Co\CI\MyApp"]
    repo.validate(cfg, sln_repo)  # 例外が出ないこと


def test_effective_write_targets_union_and_dedup(sln_repo: Path):
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_servers = [r"\\srv1\ci", r"\\srv2\ci"]
    cfg.storage.base_paths = [r"C:\local\CI", r"\\srv1\ci"]  # 重複は1つに
    targets = repo.effective_write_targets(cfg)
    assert targets == [r"\\srv1\ci", r"\\srv2\ci", r"C:\local\CI"]


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
    assert saved["storage"]["basePaths"] == []
    assert saved["jenkins"]["ciFileServers"] == []
    assert saved["git"]["repositoryUrl"] == "http://172.29.162.37/kallithea/x/ipu-test-app"
    assert "taro" not in json.dumps(saved)

    # ローカルファイル（git 非追跡）に書き込み先が保存される
    local = json.loads(paths.local_path(sln_repo).read_text(encoding="utf-8"))
    assert local["basePaths"] == [r"C:\Users\taro\OneDrive - Co\CI\MyApp"]
    assert local["ciFileServers"] == [r"\\fileserver\ci"]

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


def test_save_all_persists_agent_workspace_path_local_only(sln_repo: Path, tmp_path: Path):
    # agent_workspace_path は local に保存、committed config.json からは除去される
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_server = r"\\fileserver\ci"
    ws = tmp_path / "agent_ws" / "IPU_TEST_APP"
    ws.mkdir(parents=True)
    cfg.jenkins.agent_workspace_path = str(ws)
    repo.save_all(sln_repo, cfg, CISetupSecrets())

    local = json.loads(paths.local_path(sln_repo).read_text(encoding="utf-8"))
    assert local["agentWorkspacePath"] == str(ws)

    saved = json.loads(paths.config_path(sln_repo).read_text(encoding="utf-8"))
    assert saved["jenkins"]["agentWorkspacePath"] == ""

    # load_config が local から復元する
    loaded = repo.load_config(sln_repo)
    assert loaded.jenkins.agent_workspace_path == str(ws)


def test_save_all_auto_deploys_to_agent_sibling(sln_repo: Path, tmp_path: Path):
    repo = ConfigRepository()
    cfg = _valid_config(sln_repo)
    cfg.jenkins.ci_file_server = r"\\fileserver\ci"
    cfg.storage.base_path = r"C:\local\CI\MyApp"
    ws = tmp_path / "agent_ws" / "IPU_TEST_APP"
    ws.mkdir(parents=True)
    cfg.jenkins.agent_workspace_path = str(ws)
    repo.save_all(sln_repo, cfg, CISetupSecrets())

    sibling = ws.parent / (ws.name + ".cisetup.local.json")
    assert sibling.is_file()
    data = json.loads(sibling.read_text(encoding="utf-8"))
    assert data["ciFileServers"] == [r"\\fileserver\ci"]
    assert data["basePaths"] == [r"C:\local\CI\MyApp"]
    # 兄弟パス側には機械固有パスは含めない
    assert "agentWorkspacePath" not in data


def test_deploy_local_to_agent_matches_ci_config_formula(tmp_path: Path):
    # ci-config.ps1 (225〜260 行目付近):
    #   $externalLocalPath = Join-Path (Split-Path -Parent $root)
    #       ("$(Split-Path -Leaf $root).cisetup.local.json")
    repo = ConfigRepository()
    cfg = default_config()
    cfg.storage.base_paths = [r"C:\local\CI"]
    cfg.jenkins.ci_file_servers = [r"\\srv\ci"]
    ws = tmp_path / "workspace" / "IPU_TEST_APP"
    ws.mkdir(parents=True)
    cfg.jenkins.agent_workspace_path = str(ws)

    written = repo.deploy_local_to_agent(cfg)
    expected = tmp_path / "workspace" / "IPU_TEST_APP.cisetup.local.json"
    assert written == expected
    assert expected.is_file()
    data = json.loads(expected.read_text(encoding="utf-8"))
    assert data["basePaths"] == [r"C:\local\CI"]
    assert data["ciFileServers"] == [r"\\srv\ci"]


def test_deploy_local_to_agent_returns_none_when_empty():
    repo = ConfigRepository()
    cfg = default_config()
    cfg.jenkins.agent_workspace_path = ""
    assert repo.deploy_local_to_agent(cfg) is None


def test_deploy_local_to_agent_also_writes_into_workspace_cisetup(tmp_path: Path):
    repo = ConfigRepository()
    cfg = default_config()
    cfg.storage.base_paths = [r"C:\local\CI"]
    ws = tmp_path / "workspace" / "IPU_TEST_APP"
    (ws / "cisetup").mkdir(parents=True)
    cfg.jenkins.agent_workspace_path = str(ws)

    repo.deploy_local_to_agent(cfg)
    inside = ws / "cisetup" / "cisetup.local.json"
    assert inside.is_file()
    data = json.loads(inside.read_text(encoding="utf-8"))
    assert data["basePaths"] == [r"C:\local\CI"]


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
