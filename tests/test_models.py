from __future__ import annotations

import json
from pathlib import Path

from cisetup.models import (
    CISetupConfig,
    CISetupLocal,
    config_from_dict,
    config_to_dict,
    default_config,
    local_from_dict,
    local_to_dict,
    migrate_from_legacy,
    secrets_from_dict,
    secrets_to_dict,
    split_repository_url,
)
from cisetup.models import _camel_to_snake, _snake_to_camel


def test_split_repository_url():
    assert split_repository_url("http://user@host/path") == ("http://host/path", "user")
    assert split_repository_url("http://user:pw@host/p") == ("http://host/p", "user")
    assert split_repository_url("https://host/p.git") == ("https://host/p.git", "")
    assert split_repository_url("") == ("", "")
    # ホスト内の @ ではなく認証情報の @ のみ分離（rsplit）
    assert split_repository_url("http://u@h/a@b") == ("http://h/a@b", "u")


def test_local_roundtrip():
    local = CISetupLocal(base_paths=[r"C:\OneDrive\CI"], ci_file_servers=[r"\\srv\ci"])
    data = local_to_dict(local)
    assert data["basePaths"] == [r"C:\OneDrive\CI"]
    assert data["ciFileServers"] == [r"\\srv\ci"]
    assert local_from_dict(data) == local
    assert local_from_dict({}) == CISetupLocal()
    # 旧単一キー（basePath / ciFileServer）も読める（後方互換）
    legacy = local_from_dict({"basePath": r"C:\X", "ciFileServer": r"\\s\c"})
    assert legacy.base_paths == [r"C:\X"]
    assert legacy.ci_file_servers == [r"\\s\c"]


def test_local_agent_workspace_path_roundtrip():
    local = CISetupLocal(
        base_paths=[r"C:\OneDrive\CI"],
        ci_file_servers=[r"\\srv\ci"],
        agent_workspace_path=r"C:\jenkins-agent\workspace\IPU_TEST_APP",
    )
    data = local_to_dict(local)
    assert data["agentWorkspacePath"] == r"C:\jenkins-agent\workspace\IPU_TEST_APP"
    assert local_from_dict(data) == local
    # 後方互換: キーが無ければ空文字
    assert local_from_dict({"basePath": r"C:\X"}).agent_workspace_path == ""
    assert local_from_dict({}).agent_workspace_path == ""


def test_jenkins_agent_workspace_path_roundtrip():
    cfg = config_from_dict({"jenkins": {"agentWorkspacePath": r"C:\ws\App"}})
    assert cfg.jenkins.agent_workspace_path == r"C:\ws\App"
    assert config_to_dict(cfg)["jenkins"]["agentWorkspacePath"] == r"C:\ws\App"
    # 既定値（キー欠落時）は空文字
    assert config_from_dict({}).jenkins.agent_workspace_path == ""


def test_push_ci_file_server_env_roundtrip_and_default():
    # 既定値（キー欠落時）は False（後方互換）
    assert config_from_dict({}).jenkins.push_ci_file_server_env is False
    assert config_from_dict({"jenkins": {}}).jenkins.push_ci_file_server_env is False
    # camelCase で round-trip
    cfg = config_from_dict({"jenkins": {"pushCiFileServerEnv": True}})
    assert cfg.jenkins.push_ci_file_server_env is True
    assert config_to_dict(cfg)["jenkins"]["pushCiFileServerEnv"] is True


def test_storage_multi_value_roundtrip_and_legacy():
    # 配列キーは配列のまま、旧単一キーは 1 要素リストへ正規化される
    cfg = config_from_dict(
        {
            "storage": {
                "basePaths": [r"C:\A", r"\\srv\b"],
                "releaseUrls": ["https://r1", "https://r2"],
            },
            "jenkins": {"ciFileServers": [r"\\s1\ci", r"\\s2\ci"]},
        }
    )
    assert cfg.storage.base_paths == [r"C:\A", r"\\srv\b"]
    assert cfg.storage.release_urls == ["https://r1", "https://r2"]
    assert cfg.jenkins.ci_file_servers == [r"\\s1\ci", r"\\s2\ci"]
    # 出力は配列キー
    out = config_to_dict(cfg)
    assert out["storage"]["basePaths"] == [r"C:\A", r"\\srv\b"]
    assert out["jenkins"]["ciFileServers"] == [r"\\s1\ci", r"\\s2\ci"]

    # 旧単一キー（string）も読める
    legacy = config_from_dict(
        {
            "storage": {"basePath": r"C:\Only", "analysisUrl": "https://a"},
            "jenkins": {"ciFileServer": r"\\srv\only"},
        }
    )
    assert legacy.storage.base_paths == [r"C:\Only"]
    assert legacy.storage.analysis_urls == ["https://a"]
    assert legacy.jenkins.ci_file_servers == [r"\\srv\only"]

    source_cfg = config_from_dict(
        {"storage": {"sourceUrls": ["https://s1"], "sourceUrl": "https://legacy"}}
    )
    assert source_cfg.storage.source_urls == ["https://s1"]
    legacy_source = config_from_dict({"storage": {"sourceUrl": "https://only"}})
    assert legacy_source.storage.source_urls == ["https://only"]
    # 後方互換プロパティ（先頭要素）
    assert legacy.storage.base_path == r"C:\Only"
    assert legacy.jenkins.ci_file_server == r"\\srv\only"


def test_storage_singular_property_setter():
    cfg = config_from_dict({})
    cfg.storage.base_path = r"C:\Set"
    assert cfg.storage.base_paths == [r"C:\Set"]
    cfg.storage.base_path = ""
    assert cfg.storage.base_paths == []


def test_archive_source_roundtrip_and_default():
    # 既定値（旧設定に無いケース）
    cfg = config_from_dict({})
    assert cfg.storage.archive_source is False
    assert cfg.storage.source_dir == "source"
    # camelCase で round-trip
    cfg.storage.archive_source = True
    cfg.storage.source_dir = "src-snapshot"
    out = config_to_dict(cfg)
    assert out["storage"]["archiveSource"] is True
    assert out["storage"]["sourceDir"] == "src-snapshot"
    restored = config_from_dict(out)
    assert restored.storage.archive_source is True
    assert restored.storage.source_dir == "src-snapshot"

def test_enable_category_flags_roundtrip_and_default():
    # 既定値（キー欠落時）はすべて有効（後方互換）
    s = config_from_dict({}).storage
    assert (s.enable_logs, s.enable_releases, s.enable_analysis, s.enable_tests) == (
        True,
        True,
        True,
        True,
    )
    assert config_from_dict({"storage": {}}).storage.enable_tests is True
    # camelCase で round-trip
    cfg = config_from_dict(
        {
            "storage": {
                "enableLogs": False,
                "enableReleases": True,
                "enableAnalysis": False,
                "enableTests": False,
            }
        }
    )
    assert cfg.storage.enable_logs is False
    assert cfg.storage.enable_analysis is False
    assert cfg.storage.enable_tests is False
    out = config_to_dict(cfg)
    assert out["storage"]["enableLogs"] is False
    assert out["storage"]["enableReleases"] is True
    assert out["storage"]["enableAnalysis"] is False
    assert out["storage"]["enableTests"] is False
    restored = config_from_dict(out)
    assert restored.storage.enable_logs is False
    assert restored.storage.enable_tests is False


def test_analysis_dir_roundtrip_and_default():
    # 既定値（キー欠落時）は "analysis"（後方互換）
    assert config_from_dict({}).storage.analysis_dir == "analysis"
    assert config_from_dict({"storage": {}}).storage.analysis_dir == "analysis"
    # camelCase (analysisDir) で round-trip
    cfg = config_from_dict({"storage": {"analysisDir": "reports"}})
    assert cfg.storage.analysis_dir == "reports"
    out = config_to_dict(cfg)
    assert out["storage"]["analysisDir"] == "reports"
    restored = config_from_dict(out)
    assert restored.storage.analysis_dir == "reports"


EXAMPLE = (
    Path(__file__).resolve().parent.parent
    / "bundled_templates"
    / "cisetup.config.example.json"
)
SECRETS_EXAMPLE = (
    Path(__file__).resolve().parent.parent
    / "bundled_templates"
    / "cisetup.secrets.local.example.json"
)


def test_snake_camel_conversions():
    assert _snake_to_camel("solution_file") == "solutionFile"
    assert _snake_to_camel("build_timeout_minutes") == "buildTimeoutMinutes"
    assert _snake_to_camel("name") == "name"
    assert _camel_to_snake("solutionFile") == "solution_file"
    assert _camel_to_snake("useDateSubfolder") == "use_date_subfolder"


def test_config_roundtrip_matches_csharp_example():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8-sig"))
    cfg = config_from_dict(data)
    assert cfg.jenkins.agent_label == "windows"
    assert cfg.storage.use_date_subfolder is True
    assert cfg.jenkins.build_timeout_minutes == 30
    # 完全一致でラウンドトリップ（C# camelCase 互換）
    assert config_to_dict(cfg) == data


def test_secrets_roundtrip():
    data = json.loads(SECRETS_EXAMPLE.read_text(encoding="utf-8-sig"))
    sec = secrets_from_dict(data)
    out = secrets_to_dict(sec)
    assert set(out.keys()) == set(data.keys())


def test_from_dict_ignores_unknown_keys():
    cfg = config_from_dict({"project": {"name": "X", "bogus": 1}})
    assert cfg.project.name == "X"


def test_from_dict_empty():
    cfg = config_from_dict({})
    assert isinstance(cfg, CISetupConfig)
    assert cfg.jenkins.timezone == "Asia/Tokyo"


def test_default_config():
    cfg = default_config()
    assert cfg.project.name == "YourProject"
    assert cfg.project.solution_file == "YourProject.sln"


def test_migrate_from_legacy():
    legacy = {
        "projectName": "Legacy",
        "solutionFile": "Legacy.sln",
        "publishProject": "src/Legacy/Legacy.csproj",
        "artifactPrefix": "Legacy",
        "storage": {"logsDir": "mylogs"},
    }
    cfg = migrate_from_legacy(legacy)
    assert cfg.project.name == "Legacy"
    assert cfg.project.solution_file == "Legacy.sln"
    assert cfg.storage.logs_dir == "mylogs"


def test_migrate_from_legacy_without_storage():
    cfg = migrate_from_legacy({"projectName": "X"})
    assert cfg.project.name == "X"
    assert cfg.storage.logs_dir == "logs"
