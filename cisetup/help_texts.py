"""各設定項目のヘルプ文（GUI のツールチップ用）。C# SettingHelpTexts 相当。"""

PROJECT_NAME = (
    "【何を】CI で識別するプロジェクト名\n"
    "【どこで使う】Teams 通知の表示名、ファイルサーバーのサブフォルダ名\n"
    "【例】MyApp\n"
    "【保存先】cisetup.config.json → project.name"
)

SOLUTION_FILE = (
    "【何を】ビルド対象のソリューションファイル (.sln)\n"
    "【どこで】リポジトリルートからの相対パス\n"
    "【例】MyApp.sln または src/MyApp.sln\n"
    "【保存先】cisetup.config.json → project.solutionFile"
)

PUBLISH_PROJECT = (
    "【何を】成果物 zip を作る csproj（dotnet publish 対象）\n"
    "【例】src/MyApp/MyApp.csproj\n"
    "【保存先】cisetup.config.json → project.publishProject"
)

TEST_PROJECT = (
    "【何を】ユニットテスト用 csproj（dotnet test / xUnit 等）\n"
    "【空欄】CI の Test ステージはスキップします\n"
    "【例】tests/MyApp.Tests/MyApp.Tests.csproj\n"
    "【保存先】cisetup.config.json → project.testProject"
)

ARTIFACT_PREFIX = (
    "【何を】成果物 zip のファイル名の先頭部分\n"
    "【例】MyApp → MyApp-42-win-x64.zip\n"
    "【保存先】cisetup.config.json → project.artifactPrefix"
)

STORAGE_BASE_PATH = (
    "【何を】書き込み先を『プロジェクト名を付けずにそのまま』指定したいときのパス（UNC/ローカル）\n"
    "【複数可】右端の「＋」で複数指定でき、④ CI_FILE_SERVER と併用した全先へコピーします"
    "（相互排他ではありません）\n"
    "【OneDrive/SharePoint】同期済みのローカルフォルダのパスを指定します"
    "（例: C:\\Users\\you\\OneDrive - 会社\\CI\\MyApp）。共有 URL ではありません\n"
    "【共有リンク】Teams から開く URL は下の『成果物／ログ／ユニットテスト／解析 URL』欄へ\n"
    "【例】\\\\fileserver\\share\\builds\\MyApp\n"
    "【push されません】個人 ID を含むため cisetup.local.json（git 非追跡）に保存。"
    "CI 側は Jenkins の CI_FILE_SERVER（パラメータ/環境変数）から取得します\n"
    "【保存先】cisetup.local.json → basePath"
)

LOGS_DIR = (
    "【何を】ビルド失敗時のログを置くフォルダ名\n"
    "【デフォルト】logs\n"
    "【保存先】cisetup.config.json → storage.logsDir"
)

RELEASES_DIR = (
    "【何を】ビルド成功時の zip を置くフォルダ名\n"
    "【デフォルト】releases\n"
    "【保存先】cisetup.config.json → storage.releasesDir"
)

USE_DATE_SUBFOLDER = (
    "【何を】保存先の下に日付フォルダ (YYYYMMDD) を作るか\n"
    "【ON の例】...\\releases\\20260615\\MyApp-42-win-x64.zip\n"
    "【保存先】cisetup.config.json → storage.useDateSubfolder"
)

RELEASE_URL = (
    "【何を】成果物フォルダを開くための共有 URL（SharePoint / Web 等）\n"
    "【どこで使う】Teams 通知の「成果物フォルダを開く」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ローカルパス (file://) のリンクになります（同じ PC でのみ有効）\n"
    "【例】https://contoso.sharepoint.com/:f:/s/share/xxxxx\n"
    "【保存先】cisetup.config.json → storage.releaseUrls"
)

ANALYSIS_URL = (
    "【何を】解析レポートフォルダを開くための共有 URL（SharePoint / Web 等）\n"
    "【どこで使う】Teams 通知の「解析レポート (HTML)」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ローカルパス (file://) のリンクになります（同じ PC でのみ有効）\n"
    "【保存先】cisetup.config.json → storage.analysisUrls"
)

LOGS_URL = (
    "【何を】ログフォルダを開くための共有 URL（SharePoint / Web 等）\n"
    "【どこで使う】Teams 通知（失敗時）の「ログフォルダを開く」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ボタンは表示されません\n"
    "【保存先】cisetup.config.json → storage.logsUrls"
)

TESTS_URL = (
    "【何を】ユニットテストログを開くための共有 URL（SharePoint / Web 等）\n"
    "【どこで使う】Teams 通知でユニットテスト失敗時の「ユニットテストログを開く」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ファイルサーバーへ配置したログへのリンク（同一 PC のみ有効）にフォールバック\n"
    "【保存先】cisetup.config.json → storage.testsUrls"
)

TESTS_DIR = (
    "【何を】ユニットテスト結果（TRX / サマリ / 失敗ログ）を毎回置く専用トップレベルフォルダ名\n"
    "【ポイント】releases / logs / analysis とは混ざらない独立フォルダに分離して保存\n"
    "【保存先パス】CI_FILE_SERVER 指定時: <保存先>/<このフォルダ名>/<プロジェクト>/[日付]\n"
    "【デフォルト】tests\n"
    "【保存先】cisetup.config.json → storage.testsDir"
)

ARCHIVE_SOURCE = (
    "【何を】pull した最新の開発環境一式（チェックアウト済みソースツリー）を zip 化して保存先へ格納するか\n"
    "【除外】.git / artifacts / bin / obj / .vs / node_modules / packages / TestResults / *.user\n"
    "【デフォルト】OFF\n"
    "【保存先】cisetup.config.json → storage.archiveSource"
)

SOURCE_DIR = (
    "【何を】開発環境一式 zip を毎回置くフォルダ名（releases / logs / tests と同列）\n"
    "【保存先パス】<保存先>/<このフォルダ名>/[日付]/<プレフィックス>-<ビルド番号>-src.zip\n"
    "【デフォルト】source\n"
    "【保存先】cisetup.config.json → storage.sourceDir"
)

JENKINS_URL = (
    "【何を】設定を反映する Jenkins サーバーの URL（http://ホスト:ポート/）\n"
    "【どの画面の URL?】Jenkins にログインした直後の "
    "ホーム画面（ダッシュボード＝ジョブ一覧や『新規ジョブ作成』『Jenkins の管理』が並ぶトップ）を開いた状態で、"
    "ブラウザのアドレスバーに出ている URL です。\n"
    "  ・左上の『Jenkins』ロゴをクリックするとホーム画面に戻れます。そのときの URL が正解\n"
    "  ・ジョブを開くと .../job/ジョブ名/ になりますが、その /job/... 以降は入れない\n"
    "  ・Manage Jenkins → System の『Jenkins URL』とも同じ値\n"
    "【例】http://localhost:8086  /  http://CI-SRV:8086\n"
    "【注意】別 PC で設定アプリを使うときは localhost ではなくホスト名/IP を入れる\n"
    "【保存先】cisetup.secrets.local.json → jenkinsUrl"
)

JENKINS_USER = (
    "【何を】Jenkins の Web ログインユーザー名（管理者）\n"
    "【どこで作る】6.5『Create First Admin User』で作成した admin\n"
    "【例】admin\n"
    "【保存先】cisetup.secrets.local.json → jenkinsUser"
)

JENKINS_API_TOKEN = (
    "【何を】上記ユーザーの API Token（パスワードではありません）\n"
    "【どこで発行】Jenkins 右上のユーザー名 → Configure → API Token → Add new Token\n"
    "【注意】発行直後しか表示されません。コピーして保管してください\n"
    "【保存先】cisetup.secrets.local.json → jenkinsApiToken"
)

JOB_NAME = (
    "【何を】Jenkins の Pipeline ジョブ名\n"
    "【例】MyApp-CI（フォルダ選択時に「プロジェクト名-CI」で自動設定）\n"
    "【どこで使う】Jenkins 画面のジョブ一覧、Teams 通知\n"
    "【保存先】cisetup.config.json → jenkins.jobName"
)

AGENT_LABEL = (
    "【何を】ビルドを実行する Jenkins エージェントのラベル\n"
    "【例】windows（Jenkins ノードの Labels と一致させる）\n"
    "【空欄】Jenkins の任意の空きノードで実行（agent any）\n"
    "【保存先】cisetup.config.json + Jenkinsfile 自動生成"
)

CRON_SCHEDULE = (
    "【何を】定期ビルドのスケジュール（cron 形式）\n"
    "【例】0 0 * * * → 毎日 0:00（Jenkins のタイムゾーンに従う）\n"
    "【保存先】cisetup.config.json + Jenkinsfile 自動生成"
)

POLL_SCHEDULE = (
    "【何を】Git をポーリングして master/main へのマージ（push）を検知する間隔\n"
    "【動き】対象ブランチに新しいコミットがあるとビルドを自動実行\n"
    "【例】H/5 * * * * → 約5分ごとに変更を確認\n"
    "【空欄】ポーリングを無効化（定期ビルドのみ）\n"
    "【保存先】cisetup.config.json + Jenkinsfile 自動生成"
)

TEAMS_CREDENTIAL_ID = (
    "【何を】Jenkins Credentials に登録する Teams Webhook の ID\n"
    "【例】teams-webhook-url（変更不要なことが多い）\n"
    "【関連】Teams の Webhook URL がこの ID で Jenkins に登録されます"
)

TIMEZONE = (
    "【何を】cron 実行時刻の基準タイムゾーン\n"
    "【例】Asia/Tokyo\n"
    "【注意】Jenkins 本体の System 設定も同じ TZ に揃えてください"
)

GIT_REPOSITORY_URL = (
    "【何を】社内 Git のリポジトリ URL（clone URL）\n"
    "【例】https://git.example.com/team/MyApp.git\n"
    "【ユーザー名】URL に user@ が含まれる場合は保存時に自動除去し、ユーザー名は secrets へ移動します"
    "（認証は Jenkins 資格情報で実施）\n"
    "【保存先】cisetup.config.json → git.repositoryUrl"
)

GIT_BRANCH = (
    "【何を】CI 対象のブランチ\n"
    "【例】main / master\n"
    "【保存先】cisetup.config.json → git.branch"
)

GIT_CREDENTIAL_ID = (
    "【何を】Jenkins に登録する Git 認証の Credential ID\n"
    "【例】internal-git\n"
    "【関連】② で入力したユーザー名・パスワードがこの ID で Jenkins に登録されます"
)

JENKINS_AGENT_NAME = (
    "【何を】Jenkins に登録する Windows エージェントの名前\n"
    "【例】windows-agent"
)

JENKINS_AGENT_ROOT = (
    "【何を】エージェントがビルドファイルを置くフォルダ\n"
    "【例】C:\\Jenkins\\workspace\n"
    "【注意】エージェント PC 上に存在するパスを指定"
)

LOCAL_BUILD_TEST = (
    "【何を】配置済みの ci-build.ps1 / ci-test.ps1 をこの PC でそのまま実行し、"
    "現在のローカルコード（作業コピー）をビルド＆テストします\n"
    "【git 操作なし】fetch / pull / push を一切行いません。push 前に手元の変更を確認する用途です\n"
    "【テストビルドとの違い】「テストビルド」は Jenkins がリモート Git のコードをビルド。"
    "こちらは push せずにローカルのコードを検証します\n"
    "【おすすめ】先に「設定を保存」を実行すると最新のスクリプトで検証できます\n"
    "【実行内容】cisetup\\scripts\\ci-build.ps1 → ci-test.ps1"
    "（ビルドが失敗したらテストは実行しません）"
)
