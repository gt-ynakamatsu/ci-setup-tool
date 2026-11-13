"""JENKINS-SERVER-SETUP.marp.md の図（SVG）を docs/images へ書き出す。

python docs/tools/make_jenkins_setup_figures.py
"""

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "images"
FONT = "'Yu Gothic', 'YuGothic', 'Meiryo', sans-serif"
MONO = "Consolas, 'BIZ UDGothic', 'MS Gothic', monospace"
PATH = "Consolas, 'Yu Gothic', sans-serif"
NOTE = "#3c3c3c"
BLUE = "#003894"
RED = "#e60012"
GRAY = "#595757"
INK = "#231815"
PALE = "#eef2f9"


def svg(width: int, height: int, body: str, font: str = FONT) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{font}">\n'
        "<defs>"
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>'
        "</defs>\n"
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>\n'
        f"{body}</svg>\n"
    )


def text(x, y, s, size=20, fill=INK, weight="400", anchor="start", family=None) -> str:
    if family is None and "\\" in s:
        family = PATH
    fam = f' font-family="{family}"' if family else ""
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
        f'text-anchor="{anchor}"{fam} xml:space="preserve">{escape(s)}</text>\n'
    )


def rect(x, y, w, h, fill="none", stroke="none", sw=2, rx=0) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}"/>\n'
    )


def measure(s: str, size: float) -> float:
    return sum(size if ord(c) > 0x7F else size * 0.55 for c in s)


def badge(cx, cy, label, fill=BLUE, r=20) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>\n' + text(
        cx, cy + 8, label, size=22, fill="#ffffff", weight="700", anchor="middle"
    )


def arrow(x1, y1, x2, y2, width=4) -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{BLUE}" '
        f'stroke-width="{width}" marker-end="url(#arrow)"/>\n'
    )


def flow() -> str:
    body = ""
    for x, w, label, color in (
        (20, 250, "確認と準備", GRAY),
        (290, 510, "サーバーで実行", BLUE),
        (820, 760, "設定用 PC の CISetup で確認", BLUE),
    ):
        body += rect(x, 20, w, 44, fill=color)
        body += text(x + w / 2, 50, label, 22, "#ffffff", "700", "middle")
    steps = (
        (20, 250, "事前確認", ["Jenkins が", "入っていない", "ことを確認"], ["「対象」の条件"]),
        (290, 245, "実行", ["管理者", "PowerShell で", "スクリプト実行"], ["完了まで待つ"]),
        (555, 245, "完了表示", ["==> 完了 と", "プラグイン7個", "を確認"], ["URL・ユーザー・", "API Token を控える"]),
        (820, 240, "CISetup", ["⑤ Jenkins への", "接続 へ入力"], ["設定用 PC で", "アイコンから起動"]),
        (1080, 240, "接続テスト", ["成功の", "メッセージ", "を確認"], ["接続成功"]),
        (1340, 240, "エージェント", ["Nodes 画面で", "オンライン", "を確認"], ["windows-agent"]),
    )
    for i, (x, w, title, lines, notes) in enumerate(steps, start=1):
        body += rect(x, 96, w, 270, fill=PALE, stroke=BLUE)
        body += badge(x + 38, 134, str(i), r=24)
        body += text(x + 74, 143, title, 24, INK, "700")
        for j, line in enumerate(lines):
            body += text(x + 20, 196 + j * 34, line, 24)
        for j, note in enumerate(notes):
            body += text(x + 20, 312 + j * 28, note, 22, NOTE)
        if i < len(steps):
            ax = x + w + 3
            body += f'<polygon points="{ax},231 {ax + 14},221 {ax + 14},241" fill="{GRAY}" transform="rotate(180 {ax + 7} 231)"/>\n'
    body += rect(20, 390, 1560, 52, fill="#fdeced") + rect(20, 390, 8, 52, fill=RED)
    body += text(44, 425, "手順3 の完了表示（または MSI 版の案内）まで PowerShell を閉じない。手順6 の確認が終わるまでサインアウトしない", 23)
    body += rect(20, 456, 1560, 52, fill=PALE) + rect(20, 456, 8, 52, fill=BLUE)
    body += text(44, 491, "手順3 のプラグイン確認、手順5 の接続テスト、手順6 のオンライン確認がそろえば、初回セットアップは完了", 23)
    return svg(1600, 525, body)


def architecture() -> str:
    b = ""
    b += rect(10, 160, 280, 300, fill=PALE, stroke=GRAY)
    b += rect(10, 160, 280, 50, fill=GRAY)
    b += text(150, 195, "設定用 PC", 26, "#ffffff", "700", "middle")
    b += rect(28, 236, 244, 200, fill="#ffffff", stroke=BLUE)
    b += text(150, 282, "CISetup.exe", 26, BLUE, "700", "middle")
    b += text(150, 328, "⑤ Jenkins への接続", 22, INK, "400", "middle")
    b += text(150, 368, "URL・ユーザー名", 21, NOTE, "400", "middle")
    b += text(150, 398, "API Token", 21, NOTE, "400", "middle")

    b += arrow(295, 330, 548, 330)
    b += text(420, 300, "HTTP", 24, BLUE, "700", "middle")
    b += text(420, 368, "http://ci-server:8080/", 21, INK, "400", "middle", family=PATH)
    b += text(420, 398, "ポートは -Port の値", 21, NOTE, "400", "middle")

    b += rect(555, 20, 1025, 600, fill="#ffffff", stroke=BLUE, sw=3)
    b += rect(555, 20, 1025, 52, fill=BLUE)
    b += text(1067, 56, "Jenkins サーバー（Windows）", 26, "#ffffff", "700", "middle")

    b += rect(575, 92, 440, 214, fill=PALE, stroke=BLUE)
    b += text(595, 132, "Jenkins LTS 2.580.2", 26, BLUE, "700")
    for j, s in enumerate(("WAR を java -jar で起動", "ホーム: C:\\jenkins", "組み込みノードの実行数 0")):
        b += text(595, 172 + j * 34, s, 22)
    b += text(595, 284, "受信規則 CISetup Jenkins HTTP", 21, NOTE)

    b += rect(1125, 92, 435, 214, fill=PALE, stroke=BLUE)
    b += text(1145, 132, "windows-agent", 26, BLUE, "700")
    for j, s in enumerate(("インバウンド接続・ラベルなし", "作業フォルダ:", "C:\\Jenkins\\workspace")):
        b += text(1145, 172 + j * 34, s, 22)
    b += text(1145, 284, "ビルドはここで実行される", 21, NOTE)

    b += arrow(1121, 200, 1021, 200)
    b += text(1070, 180, "TCP 50000", 18, BLUE, "700", "middle")
    b += text(1070, 232, "127.0.0.1", 20, NOTE, "400", "middle")

    b += text(575, 346, "導入または再利用するツール（ない場合だけ導入）", 22, INK, "700")
    for x, title, note in (
        (575, "Git for Windows", "新規導入時 2.47.1.2"),
        (907, "Java 21 または 25", "新規導入時 Temurin 21.0.13+9"),
        (1240, ".NET SDK", "-DotNetSdk で指定（既定 8.0）"),
    ):
        b += rect(x, 362, 320, 84, fill="#f4f4f4", stroke="#d9d9d9", sw=1)
        b += text(x + 18, 396, title, 22, INK, "700")
        b += text(x + 18, 430, note, 20, NOTE)

    b += text(575, 488, "タスク スケジューラ（サーバー起動時に SYSTEM で起動）", 22, INK, "700")
    for x, title, note in (
        (575, "CISetup Jenkins", "C:\\jenkins\\start-jenkins.bat"),
        (1075, "CISetup Jenkins Agent", "C:\\Jenkins\\workspace\\start-agent.bat"),
    ):
        b += rect(x, 504, 485, 92, fill="#f4f4f4", stroke="#d9d9d9", sw=1)
        b += text(x + 18, 540, title, 22, INK, "700")
        b += text(x + 18, 576, note, 20, NOTE)
    return svg(1600, 640, b)


def completion() -> str:
    hidden = "●●●●●●●●（表示された値）"
    lines = [
        ("==> 完了", None),
        ("Jenkins URL : http://ci-server:8080/", "1"),
        ("ユーザー    : admin", "2"),
        ("パスワード  : " + hidden, None),
        ("API Token   : " + hidden, "3"),
        ("プラグイン  : OK: plugins active (workflow-aggregator, git, credentials-binding, "
         "plain-credentials, parameterized-trigger, naginator, timestamper)", "P"),
        ("エージェント: windows-agent", "A"),
        ("作業フォルダ: C:\\Jenkins\\workspace", None),
        ("起動スクリプト: C:\\jenkins\\start-jenkins.bat", None),
        ("パスワードの保存先: C:\\jenkins\\cisetup-admin-password.txt", None),
        ("CISetup の「⑤ Jenkins への接続」に Jenkins URL、ユーザー名、API Token を入れ、"
         "接続テストが成功すれば使えます。", None),
        ("エージェントラベルは空欄にしてください。組み込みノードの実行数は 0 です。", None),
        ("（このあと、再起動後の起動、ログの場所、SYSTEM での実行などの案内が4行続く）", "G"),
    ]
    w, top, step, size = 1600, 106, 36, 18
    h = top + step * len(lines) + 30
    b = rect(0, 0, w, h, fill="#012456")
    b += rect(0, 0, w, 44, fill="#f3f3f3")
    b += text(20, 29, "管理者: Windows PowerShell", 17, INK, family=FONT)
    yellow = "#ffd200"
    for i, (s, mark) in enumerate(lines):
        y = top + i * step
        if mark == "G":
            b += text(24, y, s, size, "#9aa7b8", family=FONT)
            continue
        color = "#9aa7b8" if hidden in s else "#ffffff"
        if hidden in s:
            head, _ = s.split(hidden)
            b += text(24, y, head, size, "#ffffff", family=MONO)
            b += text(24 + measure(head, size), y, hidden, size, color, family=MONO)
        else:
            b += text(24, y, s, size, "#ffffff", family=MONO)
        if mark:
            width = measure(s, size) + 16
            b += rect(14, y - size - 4, width, size + 14, stroke=yellow, sw=3)
            if mark in "123":
                b += badge(width + 44, y - 6, mark, fill=yellow, r=18).replace(
                    'fill="#ffffff" font-weight="700"', f'fill="{INK}" font-weight="700"'
                )
    b += rect(980, 66, 590, 170, fill="#ffffff", stroke=yellow, sw=3)
    b += text(1000, 104, "CISetup「⑤ Jenkins への接続」へ入力", 23, INK, "700", family=FONT)
    for j, s in enumerate(("1 → Jenkins URL", "2 → ユーザー名", "3 → API Token")):
        b += text(1020, 144 + j * 32, s, 22, INK, family=FONT)
    ay = top + 6 * step
    b += text(360, ay, "← Nodes 画面で確認する名前", 21, yellow, "700", family=FONT)
    b += text(880, ay, "↑ プラグイン ID が7個あることを確認", 21, yellow, "700", family=FONT)
    return svg(w, h + 30, b, font=MONO)


def cisetup() -> str:
    b = rect(10, 10, 1040, 580, fill="#ffffff", stroke="#c8c8c8", sw=2)
    b += rect(10, 10, 1040, 40, fill="#f3f3f3")
    b += text(30, 37, "CISetup", 18)
    b += rect(40, 66, 980, 506, fill="#f7f9fd", stroke="#9db4dc", sw=2)
    b += text(64, 110, "⑤ Jenkins への接続", 28, "#1a73e8", "700")
    b += text(64, 146, "設定を登録する Jenkins サーバーです。URL・ユーザー名・API Token を入れ、", 19, GRAY)
    b += text(64, 172, "「接続テスト」で確認します。", 19, GRAY)
    rows = (
        ("Jenkins URL", "http://ci-server:8080/", "1"),
        ("ユーザー名", "admin", "2"),
        ("API Token", "完了表示の API Token を貼り付ける", "3"),
    )
    for i, (label, value, mark) in enumerate(rows):
        y = 196 + i * 62
        b += text(64, y + 31, label, 22)
        b += f'<circle cx="232" cy="{y + 23}" r="13" fill="#ffffff" stroke="#7aa0d8" stroke-width="2"/>\n'
        b += text(232, y + 30, "?", 17, "#1a73e8", "700", "middle")
        b += rect(260, y, 700, 46, fill="#ffffff", stroke="#7a7a7a", sw=1.5)
        b += text(276, y + 31, value, 22, GRAY if mark == "3" else INK)
        b += badge(990, y + 23, mark, r=20)
    b += text(64, 406, "Jenkins URL は普段ブラウザで開くトップ URL（例: http://localhost:8086/）。", 18, "#6e6e6e")
    b += text(64, 432, "API Token は 右上のユーザー名 → Configure → API Token → Add new Token で発行。", 18, "#6e6e6e")
    b += text(64, 460, "↑ 画面のヒント文。この手順では完了表示の URL と API Token を使う", 18, BLUE, "700")
    b += rect(260, 484, 160, 52, fill="#dce8f6", stroke="#b8cde8", sw=1)
    b += text(340, 518, "接続テスト", 22, INK, "400", "middle")
    b += badge(452, 510, "4", r=20)

    b += arrow(482, 510, 1094, 510)
    b += rect(1100, 360, 470, 210, fill="#ffffff", stroke="#c8c8c8", sw=2)
    b += rect(1100, 360, 470, 42, fill="#f3f3f3")
    b += text(1118, 389, "接続成功", 19)
    b += '<circle cx="1150" cy="458" r="24" fill="#1a73e8"/>\n'
    b += text(1150, 468, "i", 28, "#ffffff", "700", "middle")
    b += text(1188, 466, "Jenkins への接続に成功しました。", 22)
    b += rect(1440, 510, 106, 42, fill="#f3f3f3", stroke="#9a9a9a", sw=1)
    b += text(1493, 538, "OK", 20, INK, "400", "middle")
    b += text(1100, 330, "このメッセージが出れば接続テストは成功", 23, BLUE, "700")
    return svg(1600, 600, b)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in (
        ("jenkins-setup-flow.svg", flow),
        ("jenkins-setup-architecture.svg", architecture),
        ("jenkins-setup-completion.svg", completion),
        ("jenkins-setup-cisetup.svg", cisetup),
    ):
        (OUT / name).write_text(build(), encoding="utf-8")
        print(OUT / name)


if __name__ == "__main__":
    main()
