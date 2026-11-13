# Jenkins サーバー セットアップ手順

Jenkins を動かす Windows サーバーで、CISetup から接続できる状態まで用意する手順です。サンドボックスは、この手順が通ることを確認した検証環境です。サーバーでは `tools/Setup-JenkinsServer.ps1` を実行します。

ここまで終わると、設定用 PC の CISetup で次ができます。

- Jenkins URL、ユーザー名、API トークンを入れて **接続テスト** が成功する
- 同じ PC をビルドエージェントにする場合、`windows-agent` がオンラインになる

プロジェクトごとの Git URL や Teams Webhook は、CISetup の画面で対象リポジトリに対して入力します。

## 実行する

Jenkins サーバーに管理者でログオンし、リポジトリのスクリプトを実行します。`-JenkinsUrl` は、CISetup を開く PC から届く URL にします。

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl http://ci-server:8080/
```

既にウィザードで Jenkins を作ってあるサーバーでは、その管理者パスワードを渡します。

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Setup-JenkinsServer.ps1 `
  -JenkinsUrl http://ci-server:8080/ `
  -AdminPassword '<既存の管理者パスワード>'
```

Jenkins 本体とビルドエージェントを分ける場合、サーバーでは `-SkipAgent` を付けます。エージェント PC では JDK 21、.NET SDK 8、Git を入れ、CISetup の「Jenkins サーバーを初期設定」が示す `agent.jar` の起動コマンドを実行します。

| パラメーター | 既定 | 意味 |
|--------------|------|------|
| `-JenkinsUrl` | `http://localhost:8080/` | CISetup に入れる Jenkins URL |
| `-AdminUser` | `admin` | 管理者ユーザー |
| `-AdminPassword` | `cisetup-admin` | 新規作成時のパスワード。2 回目以降は `C:\jenkins\cisetup-admin-password.txt` を使う |
| `-JenkinsHome` | `C:\jenkins` | `JENKINS_HOME` |
| `-Port` | `8080` | HTTP ポート |
| `-AgentName` | `windows-agent` | この PC に登録するエージェント名 |
| `-AgentWorkDir` | `C:\Jenkins\workspace` | エージェントの作業ディレクトリ |
| `-FileShare` | 空 | 指定時は `-ProjectPath` の共有フォルダルートに書く |
| `-ProjectPath` | 空 | 指定時は、そのプロジェクトの `CISetup` に接続情報を保存する |
| `-CISetupExe` | 空 | 指定時は、完了後に CISetup を起動する |
| `-SkipAgent` | オフ | Jenkins だけ入れ、この PC ではエージェントを起動しない |

スクリプトが行うことは次のとおりです。

1. Git for Windows 2.47.1 を入れる
2. この PC をエージェントにする場合、.NET SDK 8 を `C:\dotnet` に入れ、マシンの PATH に加える
3. Temurin JDK 21 を `C:\jdk21` に入れ、PATH の先頭にする
4. Jenkins LTS の `jenkins.war` を `C:\jenkins.war` に置く
5. セットアップウィザードを出さずに、指定ポートで Jenkins を起動する
6. 管理者、Jenkins URL、エージェント待受ポート 50000 を設定する
7. TCP 8080 と、エージェントを入れる場合は TCP 50000 をファイアウォールで許可する
8. CISetup が必要とするプラグインを入れる
9. エージェントを登録し、Java 21 で起動する
10. API トークンを発行し、`C:\jenkins\cisetup-api-token.txt` に保存する

完了時に表示する URL、ユーザー、パスワード、API トークンを、CISetup の「Jenkins への接続」に入力します。**接続テスト** が成功すれば、CISetup からこのサーバーを使えます。

Jenkins のウィンドウと、エージェントのウィンドウは閉じません。サーバーを再起動したあとは、次を実行します。

```text
C:\jenkins\start-jenkins.bat
C:\Jenkins\workspace\start-agent.bat
```

## CISetup に入力する

| 項目 | 値 |
|------|-----|
| Jenkins URL | スクリプトに渡した `-JenkinsUrl` |
| ユーザー名 | `admin` |
| API Token | 完了メッセージ、または `C:\jenkins\cisetup-api-token.txt` |
| リポジトリ URL | 対象プロジェクトの Git URL |
| ブランチ | 対象ブランチ（例: `main`） |
| 共有フォルダルート | 成果物の保存先。このサーバーのローカルフォルダでも、`\\fileserver\ci` のような共有でもよい |

Git のユーザー名と Teams Webhook は、使う場合だけ入力します。空でも接続テストは成功します。

**環境をスキャン** では、この PC がエージェントを兼ねる場合に Git、.NET SDK 8、Java 21 が検出されます。Jenkins を war で直接起動しているため、Windows サービスは未検出のままで問題ありません。

## 検証で確定したこと

サンドボックスで同じ手順を確認したときに、次が分かりました。スクリプトには反映済みです。

- 現在の Jenkins LTS（検証時は 2.580.2）は Java 21 または 25 が必要です。Java 17 では起動しません。
- サンドボックスには winget がありません。サーバーでも、スクリプトは公式の配布物を直接取得します。
- `dotnet-install.ps1` は実行中のプロセスにしか PATH を足しません。スクリプトはマシンの PATH に `C:\dotnet` を追加します。
- CISetup の「Jenkins サーバーを初期設定」は、エージェントノードの作成（`computer/doCreateItem`）で HTTP 400 になることがあります。スクリプトは Script Console 相当の Groovy でノードを登録します。
- エージェントの待受ポートは初期状態で閉じています。スクリプトは 50000 に設定します。
- エージェントは `cmd` から Java 21 で起動します。PowerShell では `-url` と `-secret` が引数として残りません。

## 認証情報

新規に作成した Jenkins の初期パスワードは `-AdminPassword` の値で、省略時は `cisetup-admin` です。ファイルは `C:\jenkins\cisetup-admin-password.txt` に残します。API トークンは発行のたびに変わるため、画面に入っている値とファイルの値が同じであることを確認します。
