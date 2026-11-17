# CISetup

社内 CI（Jenkins / Git / Teams / ファイルサーバー）を、画面の操作で設定するツールです。
**Python のインストールは不要**です。

## 使い方

1. この zip をフォルダに展開します。
2. **`CISetup.exe`** をダブルクリックします。
3. 画面の案内にしたがって入力し、保存します。

各項目の意味は、画面に表示されます。

## 同梱物

| ファイル | 内容 |
|----------|------|
| `CISetup.exe` | 本体。ダブルクリックで設定画面が開きます |
| `README.md` | このファイル |
| `docs\` | 画面の操作、CI の構築手順、Jenkins サーバーのセットアップ手順（PDF） |
| `tools\Setup-JenkinsServer.ps1` | 未導入の Windows サーバーへ Jenkins を入れるスクリプト |
| `Setup-Project.bat` | プロジェクトフォルダを選んでから画面を開く補助です。通常は `CISetup.exe` だけで足ります |

## 困ったとき

- exe が起動しない: 社内の共有フォルダではなく、自分の PC 上のフォルダに展開してから開いてください。
- 画面の項目の意味: `docs\GUI.pdf`
- Jenkins やファイルサーバーを含めた構築手順: `docs\CI-GUIDE.pdf`
- 全体をスライドで見たいとき: `docs\CISetup-CI-Guide.pdf`
- 未導入の Windows サーバーへ Jenkins を入れるとき: `docs\JENKINS-SERVER-SETUP-version3.2.pdf` と `tools\Setup-JenkinsServer.ps1`
- MSI 版、または別 PC をエージェントにするとき: `docs\JENKINS-SERVER-SETUP-MANUAL-version1.2.pdf`
