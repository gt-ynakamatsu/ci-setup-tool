判定: 合格（第3回）
総合点: 92（正確性 23/25、論理性 18/20、レイアウト 12/15、構成 10/10、明瞭性 9/10、整合性 10/10、実用性 10/10。項目点の合計と記載の総合点は一致）
重大: 0（レビュワー 0、採点担当 0）
重要: レビュワー 7、採点担当 1（第3回）
実施回数: 3
文章の毛色: 技術・仕様・設計
仮定した目的と読み手: 本番の Jenkins サーバーで tools/Setup-JenkinsServer.ps1 を実行する担当者が、CISetup の接続テスト成功まで迷わず進められるようにする。読み手は CI 基盤を触るインフラ担当で、PowerShell と Windows サーバー運用は分かるが、CISetup の内部は知らない。
レビューイー: GPT-5.6（gpt-5.6-sol-medium）
レビュワー: Claude Opus 5.5（claude-opus-5-5-high）
採点: Grok 4.7（grok-4.7-high-fast）
選定理由: 毛色を技術・仕様・設計と判断し、models.md の割当表どおりにした。3役は別ファミリーにして独立させた。Claude Opus 5.5 は許可一覧にある上位の high を使った。

改稿案:
- 最終案（第3回）: D:\work\ynakamatsu\WindowsApp\ci-setup-tool\ci-setup-tool\docs\JENKINS-SERVER-SETUP.marp-document-review\20261111-005816-JENKINS-SERVER-SETUP.marp-改稿-03.md
- 第1回、第2回の改稿案は old に保管

各回のレビューと採点:
- 第1回: 採点 87、レビュー 重大 1 → 不合格（スクリプト自体が未実行であることが読み取れなくなった）
  - 20261111-003702-JENKINS-SERVER-SETUP.marp-レビュー-01.md
  - 20261111-003703-JENKINS-SERVER-SETUP.marp-採点-01.md
- 第2回: 採点 88、レビュー 重大 1 → 不合格（リポジトリ URL を空でよいとする記述が原文と合わない）
  - 20261111-004659-JENKINS-SERVER-SETUP.marp-レビュー-02.md
  - 20261111-004659-JENKINS-SERVER-SETUP.marp-採点-02.md
- 第3回: 採点 92、重大 0 → 合格
  - 20261111-005817-JENKINS-SERVER-SETUP.marp-レビュー-03.md
  - 20261111-005817-JENKINS-SERVER-SETUP.marp-採点-03.md

原文の保管先: D:\work\ynakamatsu\WindowsApp\ci-setup-tool\ci-setup-tool\docs\JENKINS-SERVER-SETUP.marp-document-review\old\20261111-003657-JENKINS-SERVER-SETUP.marp-原文.md（原文は docs\JENKINS-SERVER-SETUP.marp.md に変更せず残している）

未確認:
- Marp のレンダリング（文字切れ、重なり、余白、コントラスト、表の折り返し）。レイアウトは 15 点にしていない。
- CISetup の現行画面と表示文言（接続テストの成功メッセージ、環境スキャンの対象 PC、接続テストで空欄にできる入力項目）。
- Jenkins 2.580.2 側の挙動（更新サイトに接続できない場合のプラグイン処理、crumb を取れない場合の POST、API トークン管理画面の名称）。
- 配布元のリダイレクト先、別 PC エージェントの接続方式（TCP 50000 か WebSocket か）。
- tools/Setup-JenkinsServer.ps1 は一度も実行していない。

不合格の理由: （合格のため該当なし）

推奨する次の対応:
- 最終案を docs\JENKINS-SERVER-SETUP.marp.md へ反映するかは利用者が決める。
- 第3回のレビュー結果に、重要 7 件が残っている。主なものは次のとおり。
  - 「Jenkins サーバーを初期設定」を実行しない理由の記載。
  - 既存 MSI 版 Jenkins は、停止だけでなく自動起動の無効化まで必要。
  - プラグイン不足でもスクリプトが止まらないこと。
  - 作り直したトークンで古いトークンが無効にならないこと。
  - 別 PC エージェントの方針と TCP 50000 の受信規則。
  - 接続テストでリポジトリ URL を必須にしている記述の根拠。
  - 作成されるノードにラベルが付かないこと。
- 採点担当は第3回の重要を 1 件（完了判定の文言を同じ資料が未確認にしている）とした。反映の前に、レビュー結果の重要 7 件を取捨選択する。
- 成功メッセージの文言と、接続テストでリポジトリ URL が不要かは、CISetup の実装または実機で確認する。
- 手順書の根拠になるスクリプトに、Bugbot の指摘（`-ProjectPath` による設定の上書き、API トークンの保存漏れなど）が未修正で残っている。手順書と同時に直すかを決める。
