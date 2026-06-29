from __future__ import annotations

import copy
import json
from pathlib import Path

from . import paths
from .jenkinsfile_generator import generate_jenkinsfile
from .models import (
    CISetupConfig,
    CISetupLocal,
    CISetupSecrets,
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
from .template_store import extract_to_repository, read_template


class ConfigRepository:
    def find_repository_root(self, start: Path | None = None) -> Path | None:
        return paths.find_repository_root(start)

    def load_config(self, repository_root: Path) -> CISetupConfig:
        config_file = paths.config_path(repository_root)
        legacy_config = repository_root / paths.CONFIG_FILE
        legacy_flat = repository_root / "ci.settings.json"

        if config_file.is_file():
            config = config_from_dict(json.loads(config_file.read_text(encoding="utf-8-sig")))
        elif legacy_config.is_file():
            config = config_from_dict(json.loads(legacy_config.read_text(encoding="utf-8-sig")))
        elif legacy_flat.is_file():
            config = migrate_from_legacy(json.loads(legacy_flat.read_text(encoding="utf-8-sig")))
        else:
            return default_config()

        # 個人 ID を含みうる書き込み先は git 非追跡のローカルファイルから復元する。
        local = self.load_local(repository_root)
        if local.base_path.strip():
            config.storage.base_path = local.base_path
        if local.ci_file_server.strip():
            config.jenkins.ci_file_server = local.ci_file_server
        return config

    def load_local(self, repository_root: Path) -> CISetupLocal:
        local_file = paths.local_path(repository_root)
        if local_file.is_file():
            return local_from_dict(json.loads(local_file.read_text(encoding="utf-8-sig")))
        return CISetupLocal()

    def load_secrets(self, repository_root: Path) -> CISetupSecrets:
        secrets_file = paths.secrets_path(repository_root)
        if secrets_file.is_file():
            return secrets_from_dict(json.loads(secrets_file.read_text(encoding="utf-8-sig")))
        legacy = repository_root / paths.SECRETS_FILE
        if legacy.is_file():
            return secrets_from_dict(json.loads(legacy.read_text(encoding="utf-8-sig")))
        return CISetupSecrets()

    def save_all(
        self,
        repository_root: Path,
        config: CISetupConfig,
        secrets: CISetupSecrets,
    ) -> None:
        # Git URL に埋め込まれた個人ユーザー名を除去し、ユーザー名は（未設定なら）secrets へ。
        clean_url, username = split_repository_url(config.git.repository_url)
        config.git.repository_url = clean_url
        if username and not secrets.git_username.strip():
            secrets.git_username = username

        self.validate(config, repository_root)

        paths.ci_dir(repository_root).mkdir(parents=True, exist_ok=True)
        # 最新の scripts / テンプレートを cisetup/ 以下へ上書き配置
        extract_to_repository(repository_root, overwrite=True)

        # 個人 ID / マシン固有の書き込み先は git 非追跡のローカルファイルへ。
        local = CISetupLocal(
            base_path=config.storage.base_path,
            ci_file_server=config.jenkins.ci_file_server,
        )
        paths.local_path(repository_root).write_text(
            json.dumps(local_to_dict(local), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        # コミットされる config.json / Jenkinsfile には書き込み先を残さない（空にする）。
        committed = copy.deepcopy(config)
        committed.storage.base_path = ""
        committed.jenkins.ci_file_server = ""

        paths.config_path(repository_root).write_text(
            json.dumps(config_to_dict(committed), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        paths.secrets_path(repository_root).write_text(
            json.dumps(secrets_to_dict(secrets), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        template = read_template("Jenkinsfile.template")
        generate_jenkinsfile(template, paths.jenkinsfile_path(repository_root), committed)

    def build_preview_paths(
        self, config: CISetupConfig, date_folder: str = "YYYYMMDD"
    ) -> tuple[str, str, str]:
        """GUI の保存先プレビュー用。

        書き込み先は後勝ち（GUI 上で ④ CI_FILE_SERVER と base_path は相互排他のため、
        実効値は常にどちらか1つだけ）。④ CI_FILE_SERVER があればその下に
        プロジェクト名を付けて使い、無ければ base_path を「そのまま」使う。
        両方非空になるのはレガシー設定のロード直後だけで、その決定的タイブレークとして
        file_server を優先する。

        戻り値は (logs, releases, tests) の順。
        """
        file_server = config.jenkins.ci_file_server.strip()
        base = config.storage.base_path.strip()
        if file_server:
            root = paths.join_location(file_server, config.project.name)
        else:
            root = base

        def build(category_dir: str) -> str:
            if config.storage.use_date_subfolder:
                return paths.join_location(root, category_dir, date_folder)
            return paths.join_location(root, category_dir)

        return (
            build(config.storage.logs_dir),
            build(config.storage.releases_dir),
            build(config.storage.tests_dir),
        )

    def validate(self, config: CISetupConfig, repository_root: Path) -> None:
        if not config.project.name.strip():
            raise ValueError("プロジェクト名を入力してください。")

        is_custom = config.build.profile.lower() == "custom"
        if is_custom:
            if not config.build.build_command.strip():
                raise ValueError(
                    "カスタムビルドの「ビルド コマンド」を入力してください（詳細設定 → ビルド種別）。"
                )
        else:
            if not config.project.solution_file.strip():
                raise ValueError("ソリューションファイルを入力してください。")
            if not config.project.publish_project.strip():
                raise ValueError("Publish 対象 csproj を入力してください。")
            if not config.project.artifact_prefix.strip():
                raise ValueError("成果物プレフィックスを入力してください。")

        if not config.jenkins.cron_schedule.strip():
            raise ValueError("cron スケジュールを入力してください。")

        base_path = config.storage.base_path.strip()
        file_server = config.jenkins.ci_file_server.strip()
        if not base_path and not file_server:
            raise ValueError(
                "成果物の書き込み先を入力してください（④ CI_FILE_SERVER、または詳細設定の格納ベース）。"
            )
        # 無人 CI から OneDrive/SharePoint の共有 URL へ直接書き込むには Graph 連携が必要なため、
        # 書き込み先には UNC・ローカルパス（OneDrive 同期フォルダ等）を指定する。
        url_guide = (
            "\nOneDrive/SharePoint を使う場合は同期済みのローカルフォルダのパスを指定し、"
            "共有 URL は『成果物／ログ／ユニットテスト／解析』の各 URL 欄に入力してください。"
        )
        # 書き込み先は後勝ち（GUI で実効値は常に1つ）。実際に使われる書き込み先だけ検証する。
        # 両方非空になるのはレガシー設定のロード直後だけで、その決定的タイブレークとして
        # file_server を優先する（④ が有効なら base_path に古い URL が残っていてもエラーにしない）。
        if file_server:
            if paths.is_url(file_server):
                raise ValueError(
                    "『④ 成果物・ログの保存先（CI_FILE_SERVER）』に URL が入っています。"
                    "ここには UNC またはローカルパスを指定してください。" + url_guide
                )
        elif paths.is_url(base_path):
            raise ValueError(
                "『詳細設定 → 保存先の詳細 → 書き込み先ベース』に URL が入っています。"
                "ここには UNC またはローカルパスを指定してください。" + url_guide
            )

        if is_custom:
            return

        sln = repository_root / config.project.solution_file.replace("/", "\\")
        if not sln.is_file():
            raise ValueError(f"ソリューションファイルが見つかりません: {config.project.solution_file}")

        pub = repository_root / config.project.publish_project.replace("/", "\\")
        if not pub.is_file():
            raise ValueError(f"Publish 対象 csproj が見つかりません: {config.project.publish_project}")

        if config.project.test_project.strip():
            test = repository_root / config.project.test_project.replace("/", "\\")
            if not test.is_file():
                raise ValueError(f"テスト csproj が見つかりません: {config.project.test_project}")
