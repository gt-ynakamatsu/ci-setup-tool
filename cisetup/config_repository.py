from __future__ import annotations

import copy
import json
import warnings
from dataclasses import dataclass, field
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


@dataclass
class StorageFolderResult:
    """create_storage_folders の結果。

    created: 作成/確保できたフォルダパス（重複なし・順序安定）。
    failed: 作成に失敗した (パス, エラー内容) の一覧。
    skipped_urls: URL のためスキップした書き込み先。
    """

    created: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    skipped_urls: list[str] = field(default_factory=list)


class ConfigRepository:
    def find_repository_root(self, start: Path | None = None) -> Path | None:
        return paths.find_repository_root(start)

    def load_config(self, repository_root: Path) -> CISetupConfig:
        config_file = paths.read_config_path(repository_root)
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

        # 個人 ID を含みうる書き込み先（複数可）は git 非追跡のローカルファイルから復元する。
        local = self.load_local(repository_root)
        if local.base_paths:
            config.storage.base_paths = list(local.base_paths)
        if local.ci_file_servers:
            config.jenkins.ci_file_servers = list(local.ci_file_servers)
        if local.agent_workspace_path:
            config.jenkins.agent_workspace_path = local.agent_workspace_path
        return config

    def load_local(self, repository_root: Path) -> CISetupLocal:
        local_file = paths.read_local_path(repository_root)
        if local_file.is_file():
            return local_from_dict(json.loads(local_file.read_text(encoding="utf-8-sig")))
        return CISetupLocal()

    def load_secrets(self, repository_root: Path) -> CISetupSecrets:
        secrets_file = paths.read_secrets_path(repository_root)
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

        # 旧 cisetup/ レイアウトの既存プロジェクトは新 CISetup/ へ自動移行する。
        # 移行に失敗しても保存全体は止めない（migrate_ci_dir が警告する）。
        paths.migrate_ci_dir(repository_root)

        paths.ci_dir(repository_root).mkdir(parents=True, exist_ok=True)
        # 最新の scripts / テンプレートを CISetup/ 以下へ上書き配置
        extract_to_repository(repository_root, overwrite=True)

        # 個人 ID / マシン固有の書き込み先（複数可）は git 非追跡のローカルファイルへ。
        local = CISetupLocal(
            base_paths=list(config.storage.base_paths),
            ci_file_servers=list(config.jenkins.ci_file_servers),
            agent_workspace_path=config.jenkins.agent_workspace_path,
        )
        paths.local_path(repository_root).write_text(
            json.dumps(local_to_dict(local), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        # コミットされる config.json / Jenkinsfile には書き込み先・機械固有パスを残さない（空にする）。
        committed = copy.deepcopy(config)
        committed.storage.base_paths = []
        committed.jenkins.ci_file_servers = []
        committed.jenkins.agent_workspace_path = ""

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

        # 同一 PC でエージェントを動かす場合、書き込み先設定をワイプで消えない兄弟パスへ配置する。
        # 配置に失敗しても保存自体は成功させる（握りつぶさず警告する）。
        if config.jenkins.agent_workspace_path.strip():
            try:
                self.deploy_local_to_agent(config, local)
            except OSError as exc:
                warnings.warn(
                    f"エージェントへの書き込み先設定の自動配置に失敗しました: {exc}",
                    stacklevel=2,
                )

    def deploy_local_to_agent(
        self, config: CISetupConfig, local: CISetupLocal | None = None
    ) -> Path | None:
        """書き込み先設定(cisetup.local.json 相当)をエージェントの兄弟パスへ配置する。

        同一 PC で Jenkins エージェントを動かす前提で、ワークスペースの「ワイプ＋再クローン」でも
        消えない兄弟パス（ci-config.ps1 の externalLocalPath と同一式）へ書き込む。
        ワークスペースパス未設定なら何もせず None を返す。書き出した兄弟パスを返す。
        """
        ws = config.jenkins.agent_workspace_path.strip()
        if not ws:
            return None
        if local is None:
            local = CISetupLocal(
                base_paths=list(config.storage.base_paths),
                ci_file_servers=list(config.jenkins.ci_file_servers),
            )
        # 兄弟パス側は basePaths / ciFileServers のみ（エージェントが読むのはこの 2 つ）。
        data = local_to_dict(local)
        data.pop("agentWorkspacePath", None)
        payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        workspace = Path(ws)
        sibling = workspace.parent / (workspace.name + "." + paths.LOCAL_FILE)
        sibling.write_text(payload, encoding="utf-8", newline="\n")

        # ベストエフォート: ワークスペース内 CISetup/（旧 cisetup/）があればそこにも置く。
        ci_dir = paths.find_ci_dir(workspace)
        if ci_dir is not None:
            try:
                (ci_dir / paths.LOCAL_FILE).write_text(
                    payload, encoding="utf-8", newline="\n"
                )
            except OSError as exc:
                warnings.warn(
                    f"ワークスペース内への書き込み先設定の配置に失敗しました: {exc}",
                    stacklevel=2,
                )
        return sibling

    def effective_write_targets(self, config: CISetupConfig) -> list[str]:
        """実際にコピーされる全書き込み先（重複除去）。

        ④ CI_FILE_SERVER（複数可・プロジェクト名を付与）と詳細設定の
        書き込み先ベース（複数可・そのまま使用）の和集合。デプロイ時はこの全先へコピーする。
        """
        targets: list[str] = []
        for value in list(config.jenkins.ci_file_servers) + list(config.storage.base_paths):
            v = value.strip()
            if v and v not in targets:
                targets.append(v)
        return targets

    def build_preview_paths(
        self, config: CISetupConfig, date_folder: str = "YYYYMMDD"
    ) -> tuple[str, str, str]:
        """GUI の保存先プレビュー用（代表＝先頭の書き込み先のレイアウト）。

        書き込み先は複数指定でき（④ CI_FILE_SERVER 群と書き込み先ベース群は併用可）、
        デプロイ時は全先へコピーする。本メソッドは代表として、先頭の CI_FILE_SERVER
        （無ければ先頭の base_path）を根にレイアウト例を返す。各先の実効ルートは
        build_target_roots() を参照（CI_FILE_SERVER 系はプロジェクト名を付与、base_path 系は
        そのまま）。

        ユニットテスト成果物は releases / logs / analysis と同じく <root>/<testsDir>/[date]
        に入れ子配置する（ci-deploy-fileserver.ps1 の Get-TestsDest と一致）。
          - CI_FILE_SERVER 指定時 : <fileServer>/<project>/<testsDir>/[date]
          - base_path のみ指定時   : <base>/<testsDir>/[date]

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

    def build_analysis_preview(
        self, config: CISetupConfig, date_folder: str = "YYYYMMDD"
    ) -> str:
        """解析レポートの保存先プレビュー（代表＝先頭の書き込み先）。

        releases / logs / tests と同じ category 構造で <root>/<analysisDir>[/date]
        に配置する（ci-deploy-fileserver.ps1 の Analysis タイプと一致）。
        """
        file_server = config.jenkins.ci_file_server.strip()
        base = config.storage.base_path.strip()
        root = paths.join_location(file_server, config.project.name) if file_server else base
        analysis_dir = config.storage.analysis_dir or "analysis"
        if config.storage.use_date_subfolder:
            return paths.join_location(root, analysis_dir, date_folder)
        return paths.join_location(root, analysis_dir)

    def build_source_preview(
        self, config: CISetupConfig, date_folder: str = "YYYYMMDD"
    ) -> str:
        """開発環境一式 zip の保存先プレビュー（代表＝先頭の書き込み先）。

        releases / logs と同じ category 構造で <root>/<sourceDir>[/date] に配置する
        （ci-deploy-fileserver.ps1 の Source タイプ = Get-CategoryDest と一致）。
        デプロイ時は build_target_roots() の全先へ同様に配置する。
        """
        file_server = config.jenkins.ci_file_server.strip()
        base = config.storage.base_path.strip()
        root = paths.join_location(file_server, config.project.name) if file_server else base
        source_dir = config.storage.source_dir or "source"
        if config.storage.use_date_subfolder:
            return paths.join_location(root, source_dir, date_folder)
        return paths.join_location(root, source_dir)

    def build_target_roots(self, config: CISetupConfig) -> list[tuple[str, str]]:
        """各書き込み先と、その実効ルート（成果物が配置される基点）の組を返す。

        デプロイ（ci-deploy-fileserver.ps1）と同じ規則:
          - ④ CI_FILE_SERVER 系 : <base>/<project>（プロジェクト名を付与）
          - 書き込み先ベース系   : <base>（そのまま）
        重複ルートは除外。戻り値は (入力された書き込み先, 実効ルート) のリスト。
        """
        seen: set[str] = set()
        out: list[tuple[str, str]] = []
        for value in config.jenkins.ci_file_servers:
            base = value.strip()
            if not base:
                continue
            root = paths.join_location(base, config.project.name)
            if root.lower() not in seen:
                seen.add(root.lower())
                out.append((base, root))
        for value in config.storage.base_paths:
            base = value.strip()
            if not base:
                continue
            if base.lower() not in seen:
                seen.add(base.lower())
                out.append((base, base))
        return out

    _STORAGE_CATEGORY_DIRS = {
        "logs": lambda s: s.logs_dir,
        "releases": lambda s: s.releases_dir,
        "analysis": lambda s: s.analysis_dir,
        "tests": lambda s: s.tests_dir,
        "source": lambda s: s.source_dir,
    }

    _STORAGE_CATEGORY_ENABLED = {
        "logs": lambda s: s.enable_logs,
        "releases": lambda s: s.enable_releases,
        "analysis": lambda s: s.enable_analysis,
        "tests": lambda s: s.enable_tests,
        "source": lambda s: s.archive_source,
    }

    def storage_folder_exists(self, config: CISetupConfig, category: str) -> bool:
        """書き込み先のいずれかに、指定カテゴリの格納フォルダが存在するか。

        category は logs / releases / analysis / tests / source のいずれか。
        カテゴリが無効、または書き込み先が URL のみの場合は False。
        """
        dir_fn = self._STORAGE_CATEGORY_DIRS.get(category)
        enabled_fn = self._STORAGE_CATEGORY_ENABLED.get(category)
        if dir_fn is None or enabled_fn is None:
            return False
        if not enabled_fn(config.storage):
            return False
        dir_name = dir_fn(config.storage).strip()
        if not dir_name:
            return False
        for base, root in self.build_target_roots(config):
            if paths.is_url(base) or paths.is_url(root):
                continue
            if Path(paths.join_location(root, dir_name)).is_dir():
                return True
        return False

    def create_storage_folders(self, config: CISetupConfig) -> StorageFolderResult:
        """各書き込み先の実効ルート配下にカテゴリフォルダ（日付フォルダは作らない）を作成する。

        deploy/preview と同じ規則で build_target_roots() の各実効ルート配下に
        有効化されたカテゴリのみを mkdir する。各カテゴリの有効/無効は enable_* フラグ
        （source は archive_source）で制御し、無効カテゴリはフォルダを作らない。
        URL の書き込み先には作成できないためスキップする。
        個々の失敗で全体を止めず、結果（作成・失敗・スキップ）をまとめて返す。
        """
        categories: list[str] = []
        if config.storage.enable_releases:
            categories.append(config.storage.releases_dir)
        if config.storage.enable_logs:
            categories.append(config.storage.logs_dir)
        if config.storage.enable_analysis:
            categories.append(config.storage.analysis_dir)
        if config.storage.enable_tests:
            categories.append(config.storage.tests_dir)
        if config.storage.archive_source:
            categories.append(config.storage.source_dir)
        categories = [c.strip() for c in categories if c and c.strip()]

        result = StorageFolderResult()
        seen: set[str] = set()
        for base, root in self.build_target_roots(config):
            if paths.is_url(base) or paths.is_url(root):
                if base not in result.skipped_urls:
                    result.skipped_urls.append(base)
                continue
            for category in categories:
                target = paths.join_location(root, category)
                key = target.lower()
                if key in seen:
                    continue
                seen.add(key)
                try:
                    Path(target).mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    result.failed.append((target, str(exc)))
                else:
                    result.created.append(target)
        return result

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

        file_servers = [v.strip() for v in config.jenkins.ci_file_servers if v.strip()]
        base_paths = [v.strip() for v in config.storage.base_paths if v.strip()]
        if not file_servers and not base_paths:
            raise ValueError(
                "成果物の書き込み先を入力してください（③ 保存先の書き込み先ベースまたは共有フォルダルート）。"
            )
        # 無人 CI から OneDrive/SharePoint の共有 URL へ直接書き込むには Graph 連携が必要なため、
        # 書き込み先には UNC・ローカルパス（OneDrive 同期フォルダ等）を指定する。
        url_guide = (
            "\nOneDrive/SharePoint を使う場合は同期済みのローカルフォルダのパスを指定し、"
            "共有 URL は『成果物／ログ／ユニットテスト／解析』の各 URL 欄に入力してください。"
        )
        # 複数書き込み先に対応（全先へコピーするため、いずれの欄も URL は不可）。空行は無視。
        for value in file_servers:
            if paths.is_url(value):
                raise ValueError(
                    "『③ 保存先 → 共有フォルダルート（CI_FILE_SERVER）』に URL が入っています。"
                    "ここには UNC またはローカルパスを指定してください。" + url_guide
                )
        for value in base_paths:
            if paths.is_url(value):
                raise ValueError(
                    "『③ 保存先 → 書き込み先ベース』に URL が入っています。"
                    "ここには UNC またはローカルパスを指定してください。" + url_guide
                )

        if is_custom:
            return

        # 保存値は "/" 区切り。pathlib は Windows でも "/" を解釈できるため置換不要
        # （置換すると Linux では単一ファイル名として誤解釈されてしまう）。
        sln = repository_root / config.project.solution_file
        if not sln.is_file():
            raise ValueError(f"ソリューションファイルが見つかりません: {config.project.solution_file}")

        pub = repository_root / config.project.publish_project
        if not pub.is_file():
            raise ValueError(f"Publish 対象 csproj が見つかりません: {config.project.publish_project}")

        if config.project.test_project.strip():
            test = repository_root / config.project.test_project
            if not test.is_file():
                raise ValueError(f"テスト csproj が見つかりません: {config.project.test_project}")
