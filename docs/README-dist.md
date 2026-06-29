# CISetup Configure

社内 CI（Jenkins / Git / Teams / ファイルサーバー）の設定を行うツールです。
**Python のインストールは不要** です。

## いちばん簡単な使い方

1. この zip をフォルダに展開します。
2. **`CISetup.exe`** をダブルクリックします。
3. 画面の案内にしたがって設定し、保存します。

## 同梱物

| ファイル | 内容 |
|----------|------|
| `CISetup.exe` | 本体。ダブルクリックで設定 GUI が起動します |
| `Setup-Project.bat` | プロジェクトに CI ファイルを配置してから GUI を開くショートカット |
| `docs\` | 操作・CI 構築の手順書 |

## プロジェクトへの初回セットアップ

対象プロジェクトのフォルダに CI ファイルを配置したい場合は、次のどちらかを使います。

- `Setup-Project.bat` をダブルクリックし、案内にしたがってプロジェクトフォルダを指定する
- またはコマンドで指定する:

```
CISetup.exe --open    "C:\path\to\YourProject"
CISetup.exe --bootstrap "C:\path\to\YourProject"
```

- `--open` … フォルダを開いて GUI を起動
- `--bootstrap` … GUI を出さずに CI ファイルだけ配置

## 困ったとき

- exe が起動しない: 別フォルダ（社内共有でないローカル）に展開して再実行してください。
- 設定項目の意味: GUI 内の各項目に説明があります。詳しくは `docs\GUI.md` を参照してください。
- CI の構築手順全体: `docs\CI-GUIDE.md` を参照してください。
