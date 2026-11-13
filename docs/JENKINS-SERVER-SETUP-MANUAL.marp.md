---
marp: true
theme: genetec
paginate: true
size: 16:9
title: Jenkins サーバー 手動セットアップ手順
description: MSI 版 Jenkins を、CISetup から接続できる状態にする手順
footer: "©2026 GENETEC CORPORATION All Rights Reserved."
style: |
  section.cover { background: linear-gradient(#003894, #003894) top / 100% 14px no-repeat, url("./images/genetec-logo.png") right 64px bottom 56px / 210px auto no-repeat, #fff; }
  section:not(.cover) {
    background:
      linear-gradient(#003894, #003894) top / 100% 14px no-repeat,
      url("./images/genetec-logo-h.png") right 32px bottom 16px / 168px auto no-repeat,
      #fff;
  }
  footer {
    left: 86px;
    right: 230px;
    bottom: 20px;
    font-size: 14px;
  }
  section.cover::after {
    content: "" !important;
  }
  section.cover footer {
    left: 48px;
  }
---

<!-- _class: cover -->
<!-- _paginate: false -->

# Jenkins サーバー

<p class="lead">初回セットアップ手順（手動）</p>

Jenkins の Windows MSI と CISetup の「Jenkins サーバー初回設定」を使う

同一サーバーで自動起動まで設定する場合は、`JENKINS-SERVER-SETUP` を使う

<p class="meta">2026年11月13日<br>version 1.2<br>HW部 仲松</p>

---

<!-- _class: tight -->

# 改版履歴

| version | 日付 | 変更内容 | <span style="white-space:nowrap">改版者</span> |
|---|---|---|---|
| 1.0 | <span style="white-space:nowrap">2026-11-13</span> | 統合版 2.2 の手動手順を独立させた | 仲松 |
| 1.1 | <span style="white-space:nowrap">2026-11-13</span> | Java 要件とエージェント接続条件を実装に合わせて修正 | 仲松 |
| 1.2 | <span style="white-space:nowrap">2026-11-13</span> | エージェントの Java を 21 または 25 に戻し、受信規則の接続元と完了確認のログの場所を明記 | 仲松 |

---

<!-- _class: tight -->

## この資料の対象

`tools/Setup-JenkinsServer.ps1` を実行せず、Jenkins の Windows MSI 版と CISetup の「Jenkins サーバー初回設定」を使う手順です。

同一サーバーで Jenkins とエージェントを動かし、自動起動まで設定する場合は、`JENKINS-SERVER-SETUP` のスクリプト手順を使います。

この進め方では、次の作業は自動化されません。

- Jenkins MSI のインストールと画面で決める値の入力
- Jenkins サービスの再起動
- HTTP とエージェント用 TCP ポートの受信許可
- 組み込みノードの実行数を `0` にする操作
- API Token の発行
- エージェント PC の準備、起動、再接続

---

<!-- _class: tight -->

## 1. Jenkins サーバーへ JDK を入れる

Jenkins サーバーで操作します。

1. JDK 21 または 25 をインストールする
2. 新しい PowerShell を開く
3. 次のコマンドを実行する

```powershell
java -version
```

表示されたメジャー版が `21` または `25` であることを確認します。CISetup の環境スキャンは Java の有無を表示しますが、この版の判定は `java -version` で行います。

---

<!-- _class: tight -->

## 2. MSI を入手して値を決める

1. [jenkins.io/download](https://www.jenkins.io/download/) を開く
2. Jenkins LTS の Windows MSI を入手して実行する
3. HTTP ポートは、ほかで使っていなければ `8080` にする
4. 画面で Java の場所を求められたら、前ページで確認した JDK を指定する
5. サービスの実行アカウントなど、画面で決める値を記録する
6. インストールを完了する

MSI の画面項目は版によって異なります。HTTP ポートを `8080` 以外にした場合は、以降の `<ポート>` をその値に置き換えます。

---

<!-- _class: tight -->

## 3. Jenkins の初期設定を行う

1. Jenkins サーバーで `http://localhost:<ポート>/` を開く
2. 初期設定の解除用の値を求める画面では、画面に表示されたファイルを管理者権限で開いて値を確認する
3. 画面に従って初期設定を進める
4. 管理者ユーザーを作成し、ユーザー名を控える
5. Jenkins のホーム画面が開くことを確認する
6. 設定用 PC とエージェント PC から届く Jenkins URL を決める

作成した管理者ユーザーで API Token を発行し、CISetup の「⑤ Jenkins への接続」のユーザー名に同じユーザー名を入力します。別 PC から接続する URL には `localhost` を使いません。

---

<!-- _class: tight -->

## 4. HTTP の受信を許可する

別 PC から Jenkins URL を開く場合は、Jenkins サーバーで操作します。

1. Windows ファイアウォールの受信規則を開く
2. Jenkins URL の TCP ポートを許可する
3. 接続元を設定用 PC とエージェント PC に限定する
4. Jenkins の画面を見る利用者の PC が別にあれば、その PC または必要なセグメントも加える
5. 設定用 PC で Jenkins URL を開く
6. ログイン画面またはホーム画面が表示されることを確認する

既存の規則がある場合も、ポートと接続元がこの構成に合うことを確認します。

---

<!-- _class: tight -->

## 5. API Token を発行する

Jenkins の画面で、作成した管理者ユーザーとして操作します。

1. `右上のユーザー名 → Configure → API Token → Add new Token` を開く
2. Token の名前に `cisetup` と入力する
3. 生成操作を押す
4. 表示された値を画面を離れる前にコピーし、安全な場所に保管する

CISetup にはログインパスワードではなく、この API Token を入力します。

---

<!-- _class: tight -->

## 6. CISetup から接続を確認する

設定用 PC で操作します。

1. CISetup のアイコンをダブルクリックする
2. 「⑤ Jenkins への接続」までスクロールする
3. Jenkins URL、管理者ユーザー名、API Token を入力する
4. 「接続テスト」を押す
5. 「接続成功」ダイアログを確認する

> Jenkins への接続に成功しました。

この操作は接続だけを確認します。Jenkins URL の設定と `windows-agent` の登録は、次の「Jenkins サーバーを初期設定」で行われます。

---

<!-- _class: tight -->

## 7. Jenkins サーバーを初期設定する

1. 「詳細設定（ふだんは開かなくて OK・自動入力されています）」を開く
2. 「Jenkins サーバー初回設定（はじめてのときだけ）」へ進む
3. エージェント名が `windows-agent` であることを確認する
4. エージェント作業フォルダが `C:\Jenkins\workspace` であることを確認する
5. 「Jenkins サーバーを初期設定」を押す
6. 完了メッセージが表示されるまで待つ

この操作で、接続確認、プラグイン確認・導入、Jenkins URL の設定、`windows-agent` の作成または更新、起動コマンドの取得を行います。

---

<!-- _class: tight -->

## 初期設定ボタンを押し直すとき

プラグインの再確認や起動コマンドの再取得が必要なときは、「はじめてのときだけ」と表示されていても押し直せます。同名ノードを二重作成せず、次を毎回行います。

- 必須プラグイン7個の確認。足りないものは導入する
- CISetup の「Jenkins URL」を Jenkins 本体へ設定する
- `windows-agent` を作成または上書きする
- `windows-agent` の実行数を `1` にする
- ラベルを CISetup の「エージェントラベル」の値にする
- エージェント起動コマンドを取得する

Jenkins 画面で `windows-agent` の設定を変更している場合は、その変更が上書きされることを確認してから実行します。

---

<!-- _class: tight -->

## 8. Jenkins サービスを再起動する

再起動が必要と表示された場合は、Jenkins サーバーの管理者 PowerShell で操作します。

```powershell
Get-Service Jenkins
Restart-Service Jenkins
Get-Service Jenkins
```

最初の `Get-Service Jenkins` でサービスがあることを確認してから再起動します。最後の結果が `Running` になったら、設定用 PC で Jenkins URL を開き、ホーム画面が開くまで待ちます。その後、CISetup で「Jenkins サーバーを初期設定」をもう一度押します。

再起動が必要と表示されなかった場合も、次ページのプラグイン確認へ進みます。

---

<!-- _class: tight -->

## 9. プラグイン7個を確認する

1. 初期設定の実行ログに、`OK: all plugins already installed (...)` と次の7個の ID があることを確認する
   `workflow-aggregator`、`git`、`credentials-binding`、`plain-credentials`、`parameterized-trigger`、`naginator`、`timestamper`
2. `Manage Jenkins → Plugins` の Installed plugins で、7個が有効でエラー表示がないことを確認する

ログが `INSTALLED:` の場合は、足りないプラグインを導入した直後です。「Jenkins サーバーを初期設定」をもう一度押し、`OK: all plugins already installed` の行に7個そろうことを確認します。2回目でも ID がそろわない場合は、更新サイトへの通信を確認します。ログはプラグインが入っていることだけを示すため、有効かどうかは Plugins 画面で確認します。

---

<!-- _class: tight -->

## 10. 組み込みノードの実行数を 0 にする

ビルドが Jenkins サーバー本体で実行されないようにします。

1. `Manage Jenkins → Nodes` を開く
2. 組み込みノードを開く
3. 設定画面を開く
4. 実行数を `0` にする
5. 保存する
6. 実行数が `0` になったことを確認する

CISetup のエージェントラベルが空欄の場合、Jenkinsfile は `agent any` になります。組み込みノードの実行数を `0` にして、ジョブを `windows-agent` で実行させます。

---

<!-- _class: tight -->

## 11. エージェント用 TCP ポートを設定する

Jenkins サーバーで操作します。

1. `Manage Jenkins → Security` を開く
2. エージェント用 TCP ポートを固定値にする
3. ほかの用途で使っていなければ `50000` にする
4. 保存する
5. Windows ファイアウォールで同じ TCP ポートの受信を許可する
6. 接続元を、エージェントを動かす PC に限定する。同一サーバーをエージェントにする場合は、そのサーバーの IP アドレスにする

起動コマンドは、CISetup に入力した Jenkins URL へ接続します。同一サーバーで動かす場合も接続先は `localhost` ではないため、受信規則を作り、接続元をそのサーバーの IP アドレスにします。

---

<!-- _class: tight -->

## 12. エージェント起動コマンドをコピーする

「Jenkins サーバー初回設定」の下で操作します。

1. 「エージェント PC で実行するコマンド」が表示されていることを確認する
2. エージェント作業フォルダがエージェント PC 上の `C:\Jenkins\workspace` であることを確認する
3. 「起動コマンドをコピー」を押す
4. エージェント PC へコマンドを安全な方法で渡す

起動コマンドにはエージェント接続用の secret が含まれます。資料や作業記録へ貼り付けません。

---

<!-- _class: tight -->

## 13. エージェント PC を準備する

1. Java 21 または 25 をインストールする
2. `java -version` でメジャー版が `21` または `25` であることを確認する
3. CISetup の「.NET SDK」で指定した .NET SDK をインストールする
4. Git をインストールする
5. `C:\Jenkins\workspace` を作成する
6. CISetup を使える場合は「環境をスキャン」を押す

環境スキャンは、Git for Windows、.NET SDK、Java、Jenkins（この PC）の4項目です。別 PC のエージェントでは「Jenkins（この PC）」が未検出で問題ありません。起動コマンドには「Java 11+ 必要」と表示されますが、この手順ではサーバーとそろえて Java 21 または 25 を使います。

---

<!-- _class: tight -->

## 14. エージェントを起動する

エージェント PC の PowerShell で操作します。

1. `agent.jar` を保存する `C:\Jenkins\workspace` へ移動する
2. コピーした起動コマンドを貼り付けて実行する
3. `agent.jar` が同フォルダへ保存されたことを確認する
4. エラーで止まらず、接続処理の表示が続いていることを確認する
5. PowerShell を開いたままにする
6. Jenkins の `Manage Jenkins → Nodes` で `windows-agent` がオンラインであることを確認する

オンラインにならない場合は、Jenkins URL、HTTP とエージェント用 TCP ポート、Java、Nodes 画面を確認します。

---

<!-- _class: tight -->

## 15. 再接続と実行アカウント

PowerShell を閉じる、サインアウトする、またはエージェント PC を再起動すると、`windows-agent` はオフラインになります。

1. 設定用 PC で CISetup を開く
2. 上書きされる設定を確認し、「Jenkins サーバーを初期設定」を押す
3. 起動コマンドをコピーし直す
4. エージェント PC の `C:\Jenkins\workspace` で実行する
5. `Manage Jenkins → Nodes` でオンラインを確認する

ジョブは、起動コマンドを実行した Windows ユーザーの権限で動きます。共有フォルダには、そのユーザーのアクセス権が必要です。常時起動の設定はこの手順の範囲外です。

---

<!-- _class: tight -->

## 16. 完了を確認する

次の4点を確認します。

1. 初期設定欄の「実行ログ」に、`OK: all plugins already installed` の行と必須プラグイン7個の ID があり、Plugins 画面で7個が有効である
2. 組み込みノードの実行数が `0` である
3. `Manage Jenkins → Nodes` で `windows-agent` がオンラインである
4. CISetup の接続テストで次の文が表示される

> Jenkins への接続に成功しました。

4点を確認できれば、初回セットアップは完了です。次は、対象プロジェクトの Git URL などを入力し、CI ジョブを作成します。
