"""各設定項目のヘルプ文（GUI のツールチップ用）。C# SettingHelpTexts 相当。"""

PROJECT_FOLDER = (
    "【何を】CI を設定する対象アプリのフォルダ（.sln や CI 用ファイルがある場所）\n"
    "【なぜ】ここを選ぶとプロジェクト名・ビルド対象・CI テンプレートが自動配置され、"
    "手入力の手間と設定ミスを減らせます\n"
    "【操作】フォルダを選ぶ → 読み込み で反映"
)

PROJECT_NAME = (
    "【何を】CI で識別するプロジェクト名\n"
    "【なぜ】Teams 通知の表示名やファイルサーバーのサブフォルダ名に使われ、"
    "複数プロジェクトを同じ保存先に分けて整理するために必要です\n"
    "【どこで使う】Teams 通知の表示名、ファイルサーバーのサブフォルダ名\n"
    "【例】MyApp\n"
    "【保存先】cisetup.config.json → project.name"
)

SOLUTION_FILE = (
    "【何を】ビルド対象のソリューションファイル (.sln)\n"
    "【なぜ】CI のビルド・テスト・解析ステージがどのソリューションを対象にするか決めるため\n"
    "【どこで】リポジトリルートからの相対パス\n"
    "【例】MyApp.sln または src/MyApp.sln\n"
    "【保存先】cisetup.config.json → project.solutionFile"
)

PUBLISH_PROJECT = (
    "【何を】成果物 zip を作る csproj（dotnet publish 対象）\n"
    "【なぜ】ビルド成功時に配布する実行ファイル一式をどのプロジェクトから作るか指定するため\n"
    "【例】src/MyApp/MyApp.csproj\n"
    "【保存先】cisetup.config.json → project.publishProject"
)

TEST_PROJECT = (
    "【何を】ユニットテスト用 csproj（dotnet test / xUnit 等）\n"
    "【なぜ】自動テストを CI に含めるかどうかを決めるため。空欄ならテストはスキップ\n"
    "【空欄】CI の Test ステージはスキップします\n"
    "【例】tests/MyApp.Tests/MyApp.Tests.csproj\n"
    "【保存先】cisetup.config.json → project.testProject"
)

ARTIFACT_PREFIX = (
    "【何を】成果物 zip のファイル名の先頭部分\n"
    "【なぜ】保存先に複数ビルドの zip が並ぶとき、どのプロジェクトの成果物か判別するため\n"
    "【例】MyApp → MyApp-42-win-x64.zip\n"
    "【保存先】cisetup.config.json → project.artifactPrefix"
)

STORAGE_BASE_PATH = (
    "【何を】書き込み先のベースディレクトリ（UNC/ローカル）。プロジェクト名を付けずそのまま使います\n"
    "【なぜ】ビルド成果物・ログ・テスト結果をチームで共有する保存場所を決めるため。"
    "ここが無いと CI は成果物を置けません\n"
    "【複数可】右端の「＋」で複数指定でき、共有フォルダルート（CI_FILE_SERVER）と併用した全先へコピーします"
    "（相互排他ではありません）\n"
    "【OneDrive/SharePoint】同期済みのローカルフォルダのパスを指定します"
    "（例: C:\\Users\\you\\OneDrive - 会社\\CI\\MyApp）。共有 URL ではありません\n"
    "【共有リンク】Teams から開く URL は ④ の各カテゴリ（logs / releases / …）欄へ\n"
    "【例】\\\\fileserver\\share\\builds\\MyApp\n"
    "【push されません】個人 ID を含むため cisetup.local.json（git 非追跡）に保存。"
    "CI 側は Jenkins の CI_FILE_SERVER（パラメータ/環境変数）から取得します\n"
    "【保存先】cisetup.local.json → basePath"
)

CI_FILE_SERVERS = (
    "【何を】共有フォルダのルート（CI_FILE_SERVER）。この下にプロジェクト名フォルダを自動作成します\n"
    "【なぜ】社内ファイルサーバーへ成果物を集約し、エージェントから書き込める UNC パスを"
    " Jenkins に渡すため（書き込み先ベースと併用可）\n"
    "【例】\\\\fileserver\\ci → \\\\fileserver\\ci\\MyApp\\releases\\...\n"
    "【push されません】cisetup.local.json（git 非追跡）に保存"
)

LOGS_DIR = (
    "【③ 保存フォルダ】失敗時ログ（logs）\n"
    "【何を】ビルド失敗時のログを置くフォルダ名\n"
    "【なぜ】失敗時にどこを見ればよいか Teams 通知と保存先を一致させるため\n"
    "【④ 対応】同じカテゴリの Teams ボタン URL 欄（logs）\n"
    "【デフォルト】logs\n"
    "【保存先】cisetup.config.json → storage.logsDir"
)

RELEASES_DIR = (
    "【③ 保存フォルダ】成果物 zip（releases）\n"
    "【何を】ビルド成功時の zip を置くフォルダ名\n"
    "【④ 対応】同じカテゴリの Teams ボタン URL 欄（releases）\n"
    "【デフォルト】releases\n"
    "【保存先】cisetup.config.json → storage.releasesDir"
)

ANALYSIS_DIR = (
    "【③ 保存フォルダ】解析レポート（analysis）\n"
    "【何を】解析レポート（HTML / タイミング・使用率など）を置くフォルダ名\n"
    "【④ 対応】同じカテゴリの Teams ボタン URL 欄（analysis）\n"
    "【ポイント】releases / logs / tests と同じくプロジェクト配下に入れ子で保存\n"
    "【保存先パス】CI_FILE_SERVER 指定時: <保存先>/<プロジェクト>/<このフォルダ名>/[日付]\n"
    "【デフォルト】analysis\n"
    "【保存先】cisetup.config.json → storage.analysisDir"
)

USE_DATE_SUBFOLDER = (
    "【何を】保存先の下に日付フォルダ (YYYYMMDD) を作るか\n"
    "【なぜ】毎日のビルド成果物を上書きせず、日付ごとに履歴を残すため\n"
    "【ON の例】...\\releases\\20260615\\MyApp-42-win-x64.zip\n"
    "【保存先】cisetup.config.json → storage.useDateSubfolder"
)

RELEASE_URL = (
    "【④ Teams ボタン】成果物 zip（releases）\n"
    "【何を】成果物フォルダを開くための共有 URL（SharePoint / Web 等）\n"
    "【③ 対応】同じカテゴリの保存フォルダ名（releases）\n"
    "【どこで使う】Teams 通知の「成果物フォルダを開く」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ローカルパス (file://) のリンクになります（同じ PC でのみ有効）\n"
    "【例】https://contoso.sharepoint.com/:f:/s/share/xxxxx\n"
    "【保存先】cisetup.config.json → storage.releaseUrls"
)

ANALYSIS_URL = (
    "【④ Teams ボタン】解析レポート（analysis）\n"
    "【何を】解析レポートフォルダを開くための共有 URL（SharePoint / Web 等）\n"
    "【③ 対応】同じカテゴリの保存フォルダ名（analysis）\n"
    "【どこで使う】Teams 通知の「解析レポート (HTML)」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ローカルパス (file://) のリンクになります（同じ PC でのみ有効）\n"
    "【保存先】cisetup.config.json → storage.analysisUrls"
)

LOGS_URL = (
    "【④ Teams ボタン】失敗時ログ（logs）\n"
    "【何を】ログフォルダを開くための共有 URL（SharePoint / Web 等）\n"
    "【③ 対応】同じカテゴリの保存フォルダ名（logs）\n"
    "【どこで使う】Teams 通知（失敗時）の「ログフォルダを開く」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ボタンは表示されません\n"
    "【保存先】cisetup.config.json → storage.logsUrls"
)

TESTS_URL = (
    "【④ Teams ボタン】テスト成果物（tests）\n"
    "【何を】ユニットテストログを開くための共有 URL（SharePoint / Web 等）\n"
    "【③ 対応】同じカテゴリの保存フォルダ名（tests）\n"
    "【どこで使う】Teams 通知でユニットテスト失敗時の「ユニットテストログを開く」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ファイルサーバーへ配置したログへのリンク（同一 PC のみ有効）にフォールバック\n"
    "【保存先】cisetup.config.json → storage.testsUrls"
)

SOURCE_URL = (
    "【④ Teams ボタン】開発環境 zip（source）\n"
    "【何を】開発環境一式 zip を開くための共有 URL（SharePoint / Web 等）\n"
    "【③ 対応】同じカテゴリの保存フォルダ名（source）— archiveSource が ON のときのみ有効\n"
    "【どこで使う】Teams 通知の「開発環境 zip を開く」ボタン\n"
    "【複数可】右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します\n"
    "【空欄】ローカルパス (file://) のリンクになります（同じ PC でのみ有効）\n"
    "【保存先】cisetup.config.json → storage.sourceUrls"
)

TESTS_DIR = (
    "【③ 保存フォルダ】テスト成果物（tests）\n"
    "【何を】ユニットテスト結果（TRX / サマリ / 失敗ログ）を毎回置くフォルダ名\n"
    "【④ 対応】同じカテゴリの Teams ボタン URL 欄（tests）\n"
    "【ポイント】releases / logs / analysis と同じくプロジェクト配下に入れ子で保存\n"
    "【保存先パス】CI_FILE_SERVER 指定時: <保存先>/<プロジェクト>/<このフォルダ名>/[日付]\n"
    "【デフォルト】tests\n"
    "【保存先】cisetup.config.json → storage.testsDir"
)

ARCHIVE_SOURCE = (
    "【何を】pull した最新の開発環境一式（チェックアウト済みソースツリー）を zip 化して保存先へ格納するか\n"
    "【除外】.git / artifacts / bin / obj / .vs / node_modules / packages / TestResults / *.user\n"
    "【デフォルト】OFF\n"
    "【保存先】cisetup.config.json → storage.archiveSource"
)

ENABLE_CATEGORY = (
    "【何を】このカテゴリを使うか（作成/配置の対象にするか）\n"
    "【OFF のとき】「格納先フォルダを作成」ボタンで作らず、CI の配置(deploy)でもスキップします\n"
    "【なぜ】プロジェクトによって不要なカテゴリ（テスト無し・解析無し等）を無効化するため\n"
    "【ソース行】「開発環境一式を zip 化して保存する」(archiveSource) と同じ設定です\n"
    "【保存先】cisetup.config.json → storage.enableLogs / enableReleases / enableAnalysis / enableTests"
)

CREATE_STORAGE_FOLDERS = (
    "【何を】書き込み先の実効ルート配下に、有効化したカテゴリフォルダを今すぐ作成します\n"
    "【作成】チェックが ON の releases / logs / analysis / tests（archive_source が ON なら source も）。"
    "日付フォルダは作りません\n"
    "【なぜ】OneDrive 同期フォルダなら同期後に SharePoint 側で各フォルダの共有 URL を取得し、"
    "上の各 URL 欄に貼り付けられます（ビルド前に URL を用意できます）\n"
    "【スキップ】URL の書き込み先には作成できないためスキップします\n"
    "【対象ルート】共有フォルダルートは <base>/<プロジェクト名>、書き込み先ベースは <base>"
)

SOURCE_DIR = (
    "【③ 保存フォルダ】開発環境 zip（source）\n"
    "【何を】開発環境一式 zip を毎回置くフォルダ名（releases / logs / tests と同列）\n"
    "【なぜ】ビルド時点のソース一式を後から参照・再現できるようにするため（任意）\n"
    "【④ 対応】同じカテゴリの URL 欄（source）— archiveSource が ON のときのみ\n"
    "【保存先パス】<保存先>/<このフォルダ名>/[日付]/<プレフィックス>-<ビルド番号>-src.zip\n"
    "【デフォルト】source\n"
    "【保存先】cisetup.config.json → storage.sourceDir"
)

TEAMS_WEBHOOK_URL = (
    "【何を】Teams チャンネルへ通知を送る Webhook URL\n"
    "【なぜ】ビルド成功・失敗をチームに即座に知らせ、対応を早めるため\n"
    "【取得】Teams チャンネル → ワークフロー →「Webhook アラートをチャネルに送信する」\n"
    "【保存先】cisetup.secrets.local.json → teamsWebhookUrl（Git には push されません）"
)

JENKINS_URL = (
    "【何を】設定を反映する Jenkins サーバーの URL（http://ホスト:ポート/）\n"
    "【なぜ】ジョブ作成・Credentials 登録・ビルド起動はすべてこの Jenkins に対して行うため\n"
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
    "【例】0 0 * * * → 毎日 0:00（タイムゾーン欄の設定に従う）\n"
    "【保存先】cisetup.config.json。「Jenkins に反映」時にジョブ XML の TimerTrigger として登録"
    "（retry ラッパー ON 時はラッパージョブ側のみ）"
)

POLL_SCHEDULE = (
    "【何を】Git をポーリングして master/main へのマージ（push）を検知する間隔\n"
    "【動き】対象ブランチに新しいコミットがあるとビルドを自動実行\n"
    "【例】H/5 * * * * → 約5分ごとに変更を確認\n"
    "【空欄】ポーリングを無効化（定期ビルドのみ）\n"
    "【保存先】cisetup.config.json。「Jenkins に反映」時にジョブ XML の SCMTrigger として登録"
    "（Jenkinsfile 上書きでトリガーが消える問題を避けるため）"
)

AGENT_WORKSPACE_PATH = (
    "【何を】同一 PC で Jenkins エージェントを動かしている場合の、エージェントのワークスペースパス\n"
    "【例】C:\\jenkins-agent\\workspace\\IPU_TEST_APP\n"
    "【用途】保存時（または「エージェントへ書き込み先設定を配置」ボタン）で、書き込み先設定"
    "(cisetup.local.json) を『ワイプで消えない兄弟パス』"
    "（<親>\\<ワークスペース名>.cisetup.local.json）へ自動配置します\n"
    "【なぜ】Git のフレッシュクローンでワークスペースが丸ごと再作成されても書き込み先設定が失われないようにするため\n"
    "【空欄】何もしません\n"
    "【push されません】機械固有のため cisetup.local.json（git 非追跡）に保存。config/Jenkinsfile には残しません\n"
    "【保存先】cisetup.local.json → agentWorkspacePath"
)

PUSH_CI_FILE_SERVER_ENV = (
    "【何を】ON にすると「Jenkinsに反映」時に、先頭の書き込み先を Jenkins 本体のグローバル環境変数"
    " CI_FILE_SERVER として自動登録します（Manage Jenkins → System → Global properties）\n"
    "【なぜ】git 非経由・ワークスペースのワイプに影響されず、別 PC のエージェントにも有効。"
    "共有アクセスできない環境で書き込み先をエージェントへ届ける手段です\n"
    "【使い分け】同一 PC でエージェントを動かす場合は「エージェントへ書き込み先設定を配置（兄弟パス）」でも可。"
    "別 PC・共有不可の場合はこちらを使います\n"
    "【注意】値は単一（先頭の書き込み先のみ）。複数先が必要な場合は兄弟パス配置を使ってください\n"
    "【権限】Jenkins 管理者権限（Groovy スクリプト実行）が必要です\n"
    "【保存先】cisetup.config.json → jenkins.pushCiFileServerEnv"
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

CHECKOUT_RETRY_COUNT = (
    "【何を】Checkout ステージで git checkout に失敗した際の自動リトライ回数\n"
    "【想定エラー】Empty reply from server 等、Git サーバーの瞬断・過負荷\n"
    "【注意】Jenkinsfile 自体の取得失敗（Pipeline 開始前のエラー）には効きません。"
    "そちらは下の「cron失敗時に自動リトライ」で対応します"
)

RETRY_WRAPPER_ENABLED = (
    "【何を】定期ビルド（cron）が失敗したら自動的に再実行する\n"
    "【仕組み】cron を本体 Jenkinsfile ではなく別建ての軽量ジョブ（○○-trigger）に持たせ、"
    "そこから本体ジョブを起動・待機します。失敗したら Naginator がこのジョブごと再実行するため、"
    "Jenkinsfile 取得自体の失敗（Git サーバー瞬断など）も含めて再試行できます\n"
    "【前提】Jenkins に Naginator プラグインと Parameterized Trigger プラグインが必要"
    "（②Jenkins に反映 実行時に未導入なら自動インストールされます）\n"
    "【注意】有効化すると本体 Jenkinsfile 側の cron トリガーは自動的に無効化されます"
    "（pollSCM は従来通り有効）"
)

RETRY_MAX_COUNT = (
    "【何を】cron 失敗時に最大何回まで自動リトライするか\n"
    "【例】3 → 最初の失敗後、最大3回まで再実行"
)

RETRY_DELAY_SECONDS = (
    "【何を】cron 失敗後、次のリトライまで待つ秒数\n"
    "【例】300 → 5分後に再実行"
)

GIT_REPOSITORY_URL = (
    "【何を】社内 Git のリポジトリ URL（clone URL）\n"
    "【なぜ】Jenkins がビルドするソースコードをここから取得するため\n"
    "【例】https://git.example.com/team/MyApp.git\n"
    "【ユーザー名】URL に user@ が含まれる場合は保存時に自動除去し、ユーザー名は secrets へ移動します"
    "（認証は Jenkins 資格情報で実施）\n"
    "【保存先】cisetup.config.json → git.repositoryUrl"
)

GIT_BRANCH = (
    "【何を】CI 対象のブランチ\n"
    "【なぜ】どのブランチへのマージで自動ビルドするかを Jenkins に伝えるため\n"
    "【例】main / master\n"
    "【保存先】cisetup.config.json → git.branch"
)

GIT_USERNAME = (
    "【何を】社内 Git にログインするユーザー名\n"
    "【なぜ】Jenkins がリポジトリを clone する際の認証に使います（Git には保存されません）\n"
    "【保存先】cisetup.secrets.local.json → gitUsername"
)

GIT_PASSWORD = (
    "【何を】社内 Git のパスワード、または個人アクセストークン (PAT)\n"
    "【なぜ】パスワード認証や PAT で Jenkins が安全に Git にアクセスするため\n"
    "【注意】Git リポジトリには push されません。Jenkins Credentials に登録されます\n"
    "【保存先】cisetup.secrets.local.json → gitPassword"
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
    "【なぜ】push 前に手元の変更が通るか確認し、壊れたコードをリモートに送らないため\n"
    "【git 操作なし】fetch / pull / push を一切行いません。push 前に手元の変更を確認する用途です\n"
    "【テストビルドとの違い】「テストビルド」は Jenkins がリモート Git のコードをビルド。"
    "こちらは push せずにローカルのコードを検証します\n"
    "【おすすめ】先に「設定を保存」を実行すると最新のスクリプトで検証できます\n"
    "【実行内容】cisetup\\scripts\\ci-build.ps1 → ci-test.ps1"
    "（ビルドが失敗したらテストは実行しません）"
)

PUBLISH_RELEASE = (
    "【何を】テストビルド時に成果物 zip（dotnet publish 等）も作成して releases に保存するか\n"
    "【なぜ】本番と同じ成果物がファイルサーバーに届くか、CI 全体を通しで確認するため\n"
    "【OFF】ビルド・テストのみ実行し、zip 作成と releases への配置はスキップします"
)

STEP_SAVE = (
    "【何を】入力内容を cisetup.config.json / cisetup.local.json / secrets に保存し、"
    "CI スクリプトをリポジトリへ配置します\n"
    "【なぜ】Jenkins 反映や push の前に、設定ファイルとスクリプトを最新状態にするため"
)

STEP_JENKINS = (
    "【何を】Jenkins ジョブ・Credentials・トリガー設定をサーバーへ反映します\n"
    "【なぜ】GUI で編集した設定を実際の CI パイプラインとして動かすため"
)

STEP_PUSH = (
    "【何を】ローカルの変更を社内 Git へ push します\n"
    "【なぜ】Jenkins が取得するコードを最新にし、チームと設定・ソースを共有するため"
)

STEP_BUILD = (
    "【何を】Jenkins でテストビルドを起動します\n"
    "【なぜ】本番と同じ経路でビルド・テスト・通知・成果物配置が動くか最終確認するため"
)

BUILD_PROFILE = (
    "【何を】CI のビルド方式（.NET 自動 / カスタムコマンド）\n"
    "【なぜ】.NET 以外（FPGA・C/C++・Python 等）でも同じ CI 基盤を使えるようにするため\n"
    "【.NET】dotnet build / test / publish を自動実行\n"
    "【カスタム】各ステージのコマンドを自分で指定"
)

BUILD_COMMAND = (
    "【何を】CI のビルドステージで実行するコマンド（カスタム時・必須）\n"
    "【なぜ】プロジェクト固有のビルド手順（vivado、make 等）を CI に組み込むため\n"
    "【例】vivado -mode batch -source build.tcl"
)

LINT_COMMAND = (
    "【何を】Lint / 静的チェック用コマンド（任意）\n"
    "【なぜ】ビルド前にコーディング規約違反や明らかな問題を検出するため"
)

TEST_COMMAND = (
    "【何を】テストステージで実行するコマンド（任意）\n"
    "【なぜ】自動テストで回帰を検出し、壊れたビルドを早く気づくため\n"
    "【例】pytest -q / dotnet test"
)

ANALYZE_COMMAND = (
    "【何を】解析・レポート生成コマンド（任意）\n"
    "【なぜ】タイミング・使用率レポート等を CI で毎回残すため"
)

PUBLISH_COMMAND = (
    "【何を】成果物を生成するコマンド（任意・カスタム時）\n"
    "【なぜ】ビットストリーム生成など、ビルド後の成果物作成手順を CI に含めるため\n"
    "【注意】zip に含めるファイルは下の glob で指定します"
)

ARTIFACT_GLOB = (
    "【何を】成果物 zip に含めるファイルの glob パターン（; 区切り）\n"
    "【なぜ】カスタムビルドでできたファイルのうち、配布・保存したいものだけを選ぶため\n"
    "【例】**/*.bit;**/*.bin;reports/*.rpt"
)

BUILD_TIMEOUT = (
    "【何を】1 回の Jenkins ビルドがタイムアウトするまでの時間（分）\n"
    "【なぜ】ハングしたビルドがエージェントを占有し続けるのを防ぐため"
)

LOG_RETENTION = (
    "【何を】Jenkins が保持するビルドログの件数\n"
    "【なぜ】ディスクを圧迫しないよう、古いビルド履歴を自動削除するため"
)

DEPLOY_LOCAL_TO_AGENT = (
    "【何を】書き込み先設定 (cisetup.local.json) をエージェントの兄弟パスへ今すぐコピーします\n"
    "【なぜ】ワークスペースのワイプで設定が消えても、次のビルドで書き込み先を復元するため\n"
    "【前提】上のワークスペースパスが正しく、同一 PC でエージェントを動かしていること"
)
