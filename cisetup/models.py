from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any


@dataclass
class BuildConfig:
    preset: str = "dotnet"
    profile: str = "dotnet"
    build_command: str = ""
    lint_command: str = ""
    analyze_command: str = ""
    publish_command: str = ""
    test_command: str = ""
    artifact_glob: str = ""


@dataclass
class ProjectConfig:
    name: str = ""
    solution_file: str = ""
    publish_project: str = ""
    test_project: str = ""
    artifact_prefix: str = ""


@dataclass
class StorageConfig:
    base_path: str = ""
    logs_dir: str = "logs"
    releases_dir: str = "releases"
    tests_dir: str = "tests"
    use_date_subfolder: bool = True
    release_url: str = ""
    analysis_url: str = ""
    logs_url: str = ""
    tests_url: str = ""


@dataclass
class JenkinsConfig:
    job_name: str = "CISetup-CI"
    agent_label: str = ""
    cron_schedule: str = "0 0 * * *"
    poll_schedule: str = "H/5 * * * *"
    ci_file_server: str = r"\\fileserver\ci"
    teams_credential_id: str = "teams-webhook-url"
    default_configuration: str = "Release"
    build_timeout_minutes: int = 30
    log_retention_count: int = 30
    timezone: str = "Asia/Tokyo"


@dataclass
class GitConfig:
    repository_url: str = ""
    branch: str = "main"
    credential_id: str = "internal-git"


@dataclass
class CISetupConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    jenkins: JenkinsConfig = field(default_factory=JenkinsConfig)
    git: GitConfig = field(default_factory=GitConfig)
    build: BuildConfig = field(default_factory=BuildConfig)


@dataclass
class CISetupSecrets:
    jenkins_url: str = ""
    jenkins_user: str = ""
    jenkins_api_token: str = ""
    git_username: str = ""
    git_password: str = ""
    teams_webhook_url: str = ""


@dataclass
class CISetupLocal:
    """個人 ID / マシン固有の値（git に push しないローカル設定）。

    OneDrive 等の書き込み先パスは個人名 ID を含むことがあるため、
    コミットされる cisetup.config.json には保存せず、このローカルファイルに保持する。
    """

    base_path: str = ""
    ci_file_server: str = ""


# --- camelCase <-> snake_case 変換（C# 版 JSON と相互運用するため） ---

def _snake_to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def _camel_to_snake(name: str) -> str:
    out: list[str] = []
    for ch in name:
        if ch.isupper():
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def _to_camel_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        result: dict[str, Any] = {}
        for f in fields(obj):
            result[_snake_to_camel(f.name)] = _to_camel_dict(getattr(obj, f.name))
        return result
    return obj


def _from_camel_dict(cls: type, data: dict[str, Any] | None) -> Any:
    if not data:
        return cls()
    field_names = {f.name for f in fields(cls)}
    kwargs: dict[str, Any] = {}
    for raw_key, value in data.items():
        snake = _camel_to_snake(raw_key)
        if snake in field_names:
            kwargs[snake] = value
    return cls(**kwargs)


def config_from_dict(data: dict[str, Any]) -> CISetupConfig:
    return CISetupConfig(
        project=_from_camel_dict(ProjectConfig, data.get("project")),
        storage=_from_camel_dict(StorageConfig, data.get("storage")),
        jenkins=_from_camel_dict(JenkinsConfig, data.get("jenkins")),
        git=_from_camel_dict(GitConfig, data.get("git")),
        build=_from_camel_dict(BuildConfig, data.get("build")),
    )


def secrets_from_dict(data: dict[str, Any]) -> CISetupSecrets:
    return _from_camel_dict(CISetupSecrets, data)


def config_to_dict(config: CISetupConfig) -> dict[str, Any]:
    return _to_camel_dict(config)


def secrets_to_dict(secrets: CISetupSecrets) -> dict[str, Any]:
    return _to_camel_dict(secrets)


def local_from_dict(data: dict[str, Any]) -> CISetupLocal:
    return _from_camel_dict(CISetupLocal, data)


def local_to_dict(local: CISetupLocal) -> dict[str, Any]:
    return _to_camel_dict(local)


def split_repository_url(url: str) -> tuple[str, str]:
    """Git URL から埋め込みユーザー情報を分離する。

    例: http://user@host/path → ("http://host/path", "user")
        http://user:pass@host/path → ("http://host/path", "user")
    認証は Jenkins 資格情報で行うため、コミットする URL から個人名を除去する。
    戻り値は (ユーザー情報を除いた URL, ユーザー名)。
    """
    value = (url or "").strip()
    if "://" not in value:
        return value, ""
    scheme, rest = value.split("://", 1)
    # userinfo は authority（最初の "/" まで）に含まれる。パス内の "@" は対象外。
    slash = rest.find("/")
    authority = rest if slash == -1 else rest[:slash]
    path = "" if slash == -1 else rest[slash:]
    if "@" not in authority:
        return value, ""
    userinfo, host = authority.split("@", 1)
    username = userinfo.split(":", 1)[0]
    return f"{scheme}://{host}{path}", username


def migrate_from_legacy(data: dict[str, Any]) -> CISetupConfig:
    """旧フラット形式 ci.settings.json からの移行（C# MigrateFromLegacy 相当）。"""
    config = CISetupConfig()
    config.project.name = str(data.get("projectName", "") or "")
    config.project.solution_file = str(data.get("solutionFile", "") or "")
    config.project.publish_project = str(data.get("publishProject", "") or "")
    config.project.artifact_prefix = str(data.get("artifactPrefix", "") or "")
    storage = data.get("storage")
    if isinstance(storage, dict):
        config.storage = _from_camel_dict(StorageConfig, storage)
    return config


def default_config() -> CISetupConfig:
    return CISetupConfig(
        project=ProjectConfig(
            name="YourProject",
            solution_file="YourProject.sln",
            publish_project="src/YourProject/YourProject.csproj",
            artifact_prefix="YourProject",
        )
    )
