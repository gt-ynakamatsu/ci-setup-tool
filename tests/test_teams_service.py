from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from cisetup import teams_service
from cisetup.models import CISetupConfig


def test_normalize_url():
    assert teams_service.normalize_url("  http://x\n ") == "http://x"


def test_validate_url_empty():
    with pytest.raises(ValueError):
        teams_service.validate_url("")


def test_validate_url_bad_scheme():
    with pytest.raises(ValueError):
        teams_service.validate_url("ftp://x")


def test_validate_url_rejects_relative():
    # C# の Uri.TryCreate(Absolute) 相当: スキーム無しの相対 URL は拒否
    with pytest.raises(ValueError):
        teams_service.validate_url("example.com/path")


def test_validate_url_ok():
    teams_service.validate_url("https://x")


def _cfg():
    cfg = CISetupConfig()
    cfg.project.name = "MyApp"
    cfg.jenkins.job_name = "MyApp-CI"
    cfg.git.branch = "main"
    cfg.storage.analysis_url = "https://a"
    cfg.storage.release_url = "https://r"
    cfg.storage.tests_url = "https://t"
    cfg.storage.logs_url = "https://l"
    return cfg


def test_build_test_card_payload():
    data = json.loads(teams_service.build_test_card_payload(_cfg()))
    assert data["type"] == "message"
    card = data["attachments"][0]["content"]
    assert card["type"] == "AdaptiveCard"
    # 4 つの URL がアクションになる
    titles = [a["title"] for a in card["actions"]]
    assert "解析レポート (HTML)" in titles
    assert "ユニットテストログを開く" in titles
    assert len(card["actions"]) == 4
    body_text = " ".join(
        b.get("text", "") for b in card["body"] if b.get("type") == "TextBlock"
    )
    assert "すべてのテストが成功しました" in body_text
    assert "CalculatorTests" not in body_text


def test_build_test_card_payload_no_actions():
    cfg = CISetupConfig()
    cfg.project.name = "X"
    data = json.loads(teams_service.build_test_card_payload(cfg))
    card = data["attachments"][0]["content"]
    assert "actions" not in card


def test_build_test_card_payload_multiple_urls():
    cfg = CISetupConfig()
    cfg.project.name = "X"
    cfg.storage.release_urls = ["https://r1", "https://r2"]
    cfg.storage.analysis_urls = ["https://a"]
    data = json.loads(teams_service.build_test_card_payload(cfg))
    card = data["attachments"][0]["content"]
    titles = [a["title"] for a in card["actions"]]
    # 解析は 1 件 → 連番なし、成果物は 2 件 → 連番付き
    assert "解析レポート (HTML)" in titles
    assert "成果物フォルダを開く (1)" in titles
    assert "成果物フォルダを開く (2)" in titles
    urls = [a["url"] for a in card["actions"]]
    assert "https://r1" in urls and "https://r2" in urls


def test_error_hint_trigger_disabled():
    hint = teams_service._build_error_hint("error WorkflowTriggerIsNotEnabled")
    assert "オフ" in hint


def test_error_hint_not_found():
    hint = teams_service._build_error_hint("WorkflowNotFound")
    assert "見つかりません" in hint


def test_error_hint_empty():
    assert teams_service._build_error_hint("") == ""


def test_format_response_body():
    assert teams_service._format_response_body("") == "（応答ボディなし）"
    assert teams_service._format_response_body("x" * 500).endswith("...")


def test_send_test_success(monkeypatch):
    class Resp:
        status = 200

        def read(self):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: Resp())
    msg = teams_service.send_test("https://hook", _cfg())
    assert "HTTP 200" in msg


def test_send_test_http_error(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(
            "https://hook", 400, "bad", {}, io.BytesIO(b"WorkflowTriggerIsNotEnabled")
        )

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(ValueError, match="オフ"):
        teams_service.send_test("https://hook", _cfg())
