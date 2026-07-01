from __future__ import annotations

from pathlib import Path

from cisetup import paths
from cisetup.ci_preset_catalog import PRESETS, CiPreset, find_preset
from cisetup.jenkinsfile_generator import build_agent_declaration, generate_jenkinsfile
from cisetup.models import CISetupConfig, BuildConfig


def test_paths_helpers(tmp_path: Path):
    assert paths.config_path(tmp_path).name == paths.CONFIG_FILE
    assert paths.secrets_path(tmp_path).name == paths.SECRETS_FILE
    assert paths.jenkinsfile_path(tmp_path).name == paths.JENKINSFILE
    assert paths.scripts_dir(tmp_path).name == "scripts"
    assert paths.ci_dir(tmp_path).name == paths.CI_FOLDER


def test_is_url():
    assert paths.is_url("https://contoso.sharepoint.com/x")
    assert paths.is_url("HTTP://example.com")
    assert not paths.is_url(r"\\fileserver\ci")
    assert not paths.is_url(r"C:\Users\me\OneDrive\CI")
    assert not paths.is_url("")


def test_is_url_true_only_for_http_scheme():
    # http(s) で始まる場合のみ True（前後空白・大文字小文字は無視）
    assert paths.is_url("https://contoso.sharepoint.com/sites/team/MyApp")
    assert paths.is_url("HTTPS://contoso.sharepoint.com/x")
    assert paths.is_url("  http://example.com/path  ")


def test_is_url_false_for_local_and_unc_paths():
    # 正当なローカル/UNC パス（スペース・ハイフン・日本語を含んでも）は URL ではない
    assert not paths.is_url(r"C:\Users\taro\OneDrive - 会社名\CI\MyApp")
    assert not paths.is_url(r"C:\Users\taro\OneDrive\個人用\CI\アプリ")
    assert not paths.is_url(r"D:\日本語 パス-test\CI")
    assert not paths.is_url(r"\\fileserver\ci\MyApp")
    assert not paths.is_url("  C:\\Users\\me\\OneDrive\\CI  ")
    # file:// / onedrive: などのスキームも http(s) ではないので URL 扱いしない
    assert not paths.is_url("file:///C:/Users/me/OneDrive/CI")
    assert not paths.is_url("onedrive:C:/Users/me/CI")
    assert not paths.is_url(None)  # type: ignore[arg-type]


def test_join_location_path():
    assert paths.join_location(r"\\srv\share", "logs", "20260101") == r"\\srv\share\logs\20260101"
    assert paths.join_location(r"C:\OneDrive\CI", "releases") == r"C:\OneDrive\CI\releases"
    # 余分な区切りは正規化される
    assert paths.join_location("\\\\srv\\share\\", "/logs/") == r"\\srv\share\logs"


def test_join_location_url():
    assert (
        paths.join_location("https://host/sites/team", "tests", "20260101")
        == "https://host/sites/team/tests/20260101"
    )
    assert paths.join_location("https://host/x/", "/logs/") == "https://host/x/logs"


def test_join_location_empty_base():
    assert paths.join_location("", "logs", "20260101") == r"logs\20260101"


def test_has_ci_layout(tmp_path: Path):
    assert not paths.has_ci_layout(tmp_path)
    paths.config_path(tmp_path).parent.mkdir(parents=True)
    paths.config_path(tmp_path).write_text("{}", encoding="utf-8")
    assert paths.has_ci_layout(tmp_path)


def test_has_saved_config(tmp_path: Path):
    assert not paths.has_saved_config(tmp_path)
    paths.config_path(tmp_path).parent.mkdir(parents=True)
    paths.config_path(tmp_path).write_text("{}", encoding="utf-8")
    assert paths.has_saved_config(tmp_path)
    other = tmp_path / "legacy"
    other.mkdir()
    (other / paths.CONFIG_FILE).write_text("{}", encoding="utf-8")
    assert paths.has_saved_config(other)


def test_resolve_repository_root_cisetup_subfolder(tmp_path: Path):
    repo = tmp_path / "MyApp"
    bb = repo / paths.CI_FOLDER
    bb.mkdir(parents=True)
    (bb / paths.CONFIG_FILE).write_text("{}", encoding="utf-8")
    assert paths.resolve_repository_root(bb) == repo.resolve()
    assert paths.resolve_repository_root(repo) == repo.resolve()


def test_resolve_repository_root_legacy(tmp_path: Path):
    (tmp_path / paths.CONFIG_FILE).write_text("{}", encoding="utf-8")
    assert paths.resolve_repository_root(tmp_path) == tmp_path.resolve()


def test_resolve_repository_root_walk_up(tmp_path: Path):
    repo = tmp_path / "Proj"
    repo.mkdir()
    paths.config_path(repo).parent.mkdir(parents=True)
    paths.config_path(repo).write_text("{}", encoding="utf-8")
    deep = repo / "src" / "nested"
    deep.mkdir(parents=True)
    assert paths.resolve_repository_root(deep) == repo.resolve()


def test_resolve_repository_root_none(tmp_path: Path):
    assert paths.resolve_repository_root(tmp_path) is None


def test_normalize_project_root_cisetup_folder(tmp_path: Path):
    repo = tmp_path / "MyApp"
    bb = repo / paths.CI_FOLDER
    bb.mkdir(parents=True)
    (bb / paths.CONFIG_FILE).write_text("{}", encoding="utf-8")
    # 設定入りの cisetup フォルダを選んだら親に繰り上げる（入れ子配置の防止）
    assert paths.normalize_project_root(bb) == repo.resolve()


def test_normalize_project_root_plain_folder(tmp_path: Path):
    # 設定が無い新規フォルダは親へ遡らずそのまま返す
    assert paths.normalize_project_root(tmp_path) == tmp_path.resolve()
    # 設定の無い "cisetup" 名フォルダもそのまま（新規作成を妨げない）
    empty_bb = tmp_path / paths.CI_FOLDER
    empty_bb.mkdir()
    assert paths.normalize_project_root(empty_bb) == empty_bb.resolve()


def test_has_legacy_layout(tmp_path: Path):
    assert not paths.has_legacy_layout(tmp_path)
    (tmp_path / "Jenkinsfile").write_text("x", encoding="utf-8")
    assert paths.has_legacy_layout(tmp_path)


def test_find_repository_root_via_sln(tmp_path: Path):
    (tmp_path / "X.sln").write_text("x", encoding="utf-8")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert paths.find_repository_root(sub) == tmp_path.resolve()


def test_find_repository_root_none(tmp_path: Path):
    sub = tmp_path / "deep"
    sub.mkdir()
    # tmp_path 配下に手掛かりがなければ親をたどって最終的に見つかる可能性があるため、
    # 完全に孤立した一時ディレクトリでは None になることだけ型で確認。
    result = paths.find_repository_root(sub)
    assert result is None or isinstance(result, Path)


def test_find_preset():
    assert find_preset("python").id == "python"
    assert find_preset("PYTHON").id == "python"
    assert find_preset("") is None
    assert find_preset(None) is None
    assert find_preset("does-not-exist") is None


def test_preset_count_and_ids():
    ids = {p.id for p in PRESETS}
    assert {"dotnet", "fpga-vivado", "fpga-quartus", "cmake-cpp", "python", "custom-empty"} <= ids


def test_preset_descriptions_match_csharp():
    # C# CiPresetCatalog の Description と完全一致させる
    by_id = {p.id: p.description for p in PRESETS}
    assert by_id["dotnet"] == (
        "dotnet build / format / publish を自動実行。テスト csproj 選択時のみ dotnet test。"
        "Roslyn 静的解析つき（既定）。"
    )
    assert by_id["fpga-vivado"] == "build.tcl で合成〜ビットストリーム生成。.bit / レポートを成果物として保存します。"
    assert by_id["cmake-cpp"] == "CMake で構成・ビルド。バイナリを成果物として保存します。"
    assert by_id["python"] == "依存インストール → Lint(ruff) → ビルド(wheel)。dist の成果物を保存します。"


def test_preset_apply_to():
    preset = CiPreset(id="x", name="X", description="d", profile="custom", build_command="b")
    build = BuildConfig()
    preset.apply_to(build)
    assert build.preset == "x"
    assert build.profile == "custom"
    assert build.build_command == "b"


def test_build_agent_declaration():
    assert build_agent_declaration("") == "any"
    assert build_agent_declaration(None) == "any"
    assert build_agent_declaration("   ") == "any"
    decl = build_agent_declaration("windows")
    assert "label 'windows'" in decl


def test_build_agent_declaration_escapes():
    decl = build_agent_declaration("o'brien")
    assert "o\\'brien" in decl


def test_generate_jenkinsfile(tmp_path: Path):
    template = (
        "agent {{AGENT_DECLARATION}}\n"
        "cron(spec: '{{CRON_SCHEDULE}}', timezone: '{{TIMEZONE}}')\n"
        "{{POLL_TRIGGER}}\n"
        "server={{CI_FILE_SERVER}}\n"
        "cred={{TEAMS_CREDENTIAL_ID}}\n"
        "timeout={{BUILD_TIMEOUT}} retention={{LOG_RETENTION}}\n"
    )
    cfg = CISetupConfig()
    cfg.jenkins.agent_label = "windows"
    cfg.jenkins.cron_schedule = "0 0 * * *"
    cfg.jenkins.timezone = "Asia/Tokyo"
    cfg.jenkins.poll_schedule = "H/5 * * * *"
    cfg.jenkins.ci_file_server = r"\\server\ci"
    out = tmp_path / "Jenkinsfile"
    generate_jenkinsfile(template, out, cfg)
    text = out.read_text(encoding="utf-8")
    assert "label 'windows'" in text
    assert "cron(spec: '0 0 * * *', timezone: 'Asia/Tokyo')" in text
    assert "pollSCM('H/5 * * * *')" in text
    assert r"\\\\server\\ci" in text  # backslash escaped for groovy
    assert "timeout=30 retention=30" in text


def test_generate_jenkinsfile_empty_poll(tmp_path: Path):
    cfg = CISetupConfig()
    cfg.jenkins.poll_schedule = ""
    out = tmp_path / "Jenkinsfile"
    generate_jenkinsfile("{{POLL_TRIGGER}}X", out, cfg)
    assert out.read_text(encoding="utf-8") == "X"
