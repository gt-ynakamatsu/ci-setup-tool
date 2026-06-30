from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.parse
import urllib.request

from .models import CISetupConfig


def normalize_url(url: str) -> str:
    return url.strip().replace("\r", "").replace("\n", "")


def _is_absolute_http_url(url: str) -> bool:
    """C# の Uri.TryCreate(Absolute) + http/https スキーム判定の同等処理。"""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def validate_url(url: str) -> None:
    if not url.strip():
        raise ValueError("Teams Webhook URL を入力してください。")
    if not _is_absolute_http_url(url):
        raise ValueError(
            "Webhook URL の形式が正しくありません。\nhttps:// で始まる URL を貼り付けてください。"
        )


def _fact(title: str, value: str) -> dict:
    return {"title": title, "value": value}


def _open_url(title: str, url: str) -> dict:
    return {"type": "Action.OpenUrl", "title": title, "url": url}


def _open_url_actions(title: str, urls: list[str]) -> list[dict]:
    """複数 URL をそれぞれボタン化する。2 件以上なら連番を付けて区別する。"""
    cleaned = [u.strip() for u in urls if u and u.strip()]
    if not cleaned:
        return []
    if len(cleaned) == 1:
        return [_open_url(title, cleaned[0])]
    return [_open_url(f"{title} ({i})", url) for i, url in enumerate(cleaned, start=1)]


def build_test_card_payload(config: CISetupConfig) -> str:
    """本番通知と同じ見た目のテストカードを生成する（C# BuildTestCardPayload 相当）。"""
    project_name = config.project.name.strip() or "CISetup"
    display_name = config.jenkins.job_name.strip() or project_name

    facts = [
        _fact("プロジェクト", project_name),
        _fact("ジョブ / ビルド", f"{display_name} #(テスト)"),
        _fact("日時", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    if config.git.branch.strip():
        facts.append(_fact("ブランチ", config.git.branch.strip()))
    facts.append(_fact("コミット", "0000000"))

    body = [
        {
            "type": "Container",
            "style": "good",
            "bleed": True,
            "items": [
                {
                    "type": "TextBlock",
                    "size": "Large",
                    "weight": "Bolder",
                    "text": "✅ テスト通知（送信プレビュー）",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "spacing": "None",
                    "isSubtle": True,
                    "text": f"{display_name} #(テスト)",
                    "wrap": True,
                },
            ],
        },
        {"type": "FactSet", "facts": facts},
        {
            "type": "TextBlock",
            "weight": "Bolder",
            "color": "Good",
            "wrap": True,
            "text": "静的解析  高 0 ・ 中 0 ・ 低 0（サンプル）",
        },
        {
            "type": "TextBlock",
            "weight": "Bolder",
            "color": "Good",
            "wrap": True,
            "text": "ユニットテスト  成功 2 / 失敗 0 / 合計 2（サンプル）",
        },
        {
            "type": "TextBlock",
            "isSubtle": True,
            "wrap": True,
            "text": "すべてのテストが成功しました",
        },
        {
            "type": "TextBlock",
            "isSubtle": True,
            "wrap": True,
            "text": "これは CISetup GUI からのテスト送信です。下のボタンが設定した出力先 URL に対応します。",
        },
    ]

    actions: list[dict] = []
    for title, urls in (
        ("解析レポート (HTML)", config.storage.analysis_urls),
        ("成果物フォルダを開く", config.storage.release_urls),
        ("ユニットテストログを開く", config.storage.tests_urls),
        ("ログフォルダを開く", config.storage.logs_urls),
    ):
        actions.extend(_open_url_actions(title, urls))

    card: dict = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "msteams": {"width": "Full"},
    }
    if actions:
        card["actions"] = actions

    envelope = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }
        ],
    }
    return json.dumps(envelope, ensure_ascii=False)


def _build_error_hint(body: str) -> str:
    if not body.strip():
        return ""
    lowered = body.lower()
    if "workflowtriggerisnotenabled" in lowered or "trigger is not enabled" in lowered:
        return (
            "【原因】Power Automate のフロー（ワークフロー）がオフ（無効）です。\n"
            "【対処】Power Automate でこのフローを開き、右上の「オンにする」を押してください。\n"
            "  リクエスト自体は正常に届いています。フローを有効化すれば成功します。\n\n"
        )
    if "workflownotfound" in lowered or "triggernotfound" in lowered:
        return (
            "【原因】フローまたはトリガーが見つかりません（削除/再作成で URL が変わった可能性）。\n"
            "【対処】Power Automate でフローのトリガー URL を取得し直し、貼り替えてください。\n\n"
        )
    return ""


def _format_response_body(body: str) -> str:
    if not body.strip():
        return "（応答ボディなし）"
    return body.strip() if len(body) <= 400 else body[:400] + "..."


def send_test(webhook_url: str, config: CISetupConfig, timeout: float = 30.0) -> str:
    webhook_url = normalize_url(webhook_url)
    validate_url(webhook_url)

    payload = build_test_card_payload(config).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ValueError(
            f"Teams 通知に失敗しました (HTTP {exc.code})\n\n"
            + _build_error_hint(body)
            + _format_response_body(body)
        ) from exc

    return (
        f"HTTP {status} で送信しました。\n\n"
        "Teams チャンネルに「完成イメージ」のカードが届くか確認してください。\n"
        "解析レポート / 成果物 / ユニットテストログ / ログ の各ボタンが設定した出力先 URL に対応します。\n\n"
        "届かない場合:\n"
        "• Power Automate ワークフローが「オン」になっているか\n"
        "• URL が最新か（再作成で URL が変わります）\n"
        "• 社内ネットワークから api.powerplatform.com へ出られるか"
        + ("" if not body.strip() else f"\n\n応答:\n{_format_response_body(body)}")
    )
