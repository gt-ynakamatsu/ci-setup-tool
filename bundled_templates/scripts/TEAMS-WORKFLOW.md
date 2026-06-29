# Teams 通知 — 設定ガイド

CISetup は Webhook に **1 枚のアダプティブ カード** を POST します。  
Teams の定型 Webhook ワークフロー（「Webhook リンクをコピー」で作るもの）だけで動作します。Power Automate での追加設定は不要です。

## カードの内容

| 状況 | 表示 |
|------|------|
| 常時 | ビルド成功/失敗、プロジェクト情報、静的解析件数、ユニットテスト件数サマリー |
| テスト成功時 | 「すべてのテストが成功しました」 |
| **テスト失敗時** | **失敗したテスト名の一覧**（❌ 付き） |
| **テスト失敗時** | **「ユニットテストログを開く」ボタン**（`storage.testsUrl` またはファイルサーバー配置先） |

成功したテストの一覧はカードに出しません。

## Jenkins 側の設定

1. Teams ワークフローで **Webhook リンクをコピー**
2. Jenkins Credentials に `TEAMS_WEBHOOK_URL` として登録
3. Jenkinsfile の `ci-notify-teams.ps1` がその URL を使って POST

## ペイロード確認（任意）

```powershell
# cisetup.config.json と artifacts\test\test-summary.json がある状態で
.\scripts\ci-notify-teams.ps1 -Status complete -BuildNumber 1 -OutFile payload.json
```

## 失敗ログの配置先

`ci-deploy-fileserver.ps1 -Type Test` がテスト成果物をファイルサーバーへ配置し、
`test-failures.log` へのパスを `deploy-manifest.json` に記録します。
通知カードの「ユニットテストログを開く」ボタンはこのパス（または `storage.testsUrl`）を開きます。

## 注意

- 旧来の「Incoming Webhook」（Connector）でもカード投稿は可能ですが、組織ポリシーにより Teams **ワークフロー** を推奨します。
- スレッド返信は使いません。失敗詳細はカード内のテスト名一覧と、ファイルサーバー上の `test-failures.log` で確認してください。
