"""C# 版との JSON 互換・各モジュールの整合を確認するスモークテスト。

実行: リポジトリルートから `python tools/smoke_test.py`
（カレントディレクトリに依存しないようパスはルート基準で解決する）
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cisetup import (
    config_repository,
    environment_scan,
    git_service,
    help_texts,
    jenkins_client,
    teams_service,
)
from cisetup.ci_preset_catalog import PRESETS, find_preset
from cisetup.models import (
    config_from_dict,
    config_to_dict,
    secrets_from_dict,
    secrets_to_dict,
)
from cisetup.project_setup import looks_like_test_project

errors = []


def check(name, cond):
    print(("OK  " if cond else "FAIL") + " " + name)
    if not cond:
        errors.append(name)


# 1. camelCase JSON round-trip (C# 互換)
example = json.loads(
    (ROOT / "bundled_templates" / "cisetup.config.example.json").read_text(encoding="utf-8-sig")
)
cfg = config_from_dict(example)
check("config.jenkins.agentLabel 読み込み", cfg.jenkins.agent_label == "windows")
check("config.storage.useDateSubfolder 読み込み", cfg.storage.use_date_subfolder is True)
check("config.jenkins.buildTimeoutMinutes 読み込み", cfg.jenkins.build_timeout_minutes == 30)
roundtrip = config_to_dict(cfg)
check("camelCase キー保持 (solutionFile)", "solutionFile" in roundtrip["project"])
check("camelCase キー保持 (useDateSubfolder)", "useDateSubfolder" in roundtrip["storage"])
check("camelCase キー保持 (buildTimeoutMinutes)", "buildTimeoutMinutes" in roundtrip["jenkins"])
check("JSON 値が一致", roundtrip == example)

# secrets round-trip
secrets_example = json.loads(
    (ROOT / "bundled_templates" / "cisetup.secrets.local.example.json").read_text(encoding="utf-8-sig")
)
sec = secrets_from_dict(secrets_example)
sec_round = secrets_to_dict(sec)
check("secrets camelCase キー保持", all(k in sec_round for k in secrets_example))

# 2. preset
check("preset 検索", find_preset("python").id == "python")
check("preset 件数", len(PRESETS) == 6)

# 3. test project naming (C# と同じく endswith のみ)
check("Foo.Tests はテスト", looks_like_test_project("Foo.Tests"))
check("Contest はテストでない", not looks_like_test_project("Contest"))

# 4. teams payload
payload = teams_service.build_test_card_payload(cfg)
data = json.loads(payload)
check("teams payload type=message", data["type"] == "message")
check("teams payload にカード", data["attachments"][0]["contentType"].endswith("card.adaptive"))

# 5. jenkins error formatter / jnlp
check("401 整形", "401" in jenkins_client.format_jenkins_error(401, ""))
jnlp = "<jnlp><application-desc><argument>-secret</argument><argument>abc123</argument></application-desc></jnlp>"
check("JNLP secret 抽出", jenkins_client.extract_agent_secret(jnlp) == "abc123")

# 6. git secrets guard
check("secrets ステージ検出", git_service.contains_staged_secrets("cisetup/cisetup.secrets.local.json"))
check("通常ファイルは非検出", not git_service.contains_staged_secrets("cisetup/cisetup.config.json"))

# 7. save_all -> camelCase ファイル生成 + Jenkinsfile
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "YourProject.sln").write_text("dummy", encoding="utf-8")
    (root / "src" / "YourProject").mkdir(parents=True)
    (root / "src" / "YourProject" / "YourProject.csproj").write_text("<Project/>", encoding="utf-8")
    repo = config_repository.ConfigRepository()
    cfg.git.repository_url = "https://git.example.com/x.git"
    repo.save_all(root, cfg, sec)
    saved = json.loads((root / "CISetup" / "cisetup.config.json").read_text(encoding="utf-8"))
    check("保存 JSON が camelCase", "agentLabel" in saved["jenkins"])
    jf = (root / "CISetup" / "Jenkinsfile").read_text(encoding="utf-8")
    check("Jenkinsfile にラベル反映", "label 'windows'" in jf)
    check("Jenkinsfile が CISetup/scripts 参照", "./CISetup/scripts/" in jf)
    check("Jenkinsfile に cron", "cron(spec: '0 0 * * *'" in jf and "Asia/Tokyo" in jf)
    check("Jenkinsfile に Checkout retry", "retry(3)" in jf)
    check("Jenkinsfile に BOM なし", not jf.startswith("\ufeff"))
    logs, releases, tests = repo.build_preview_paths(cfg)
    check("preview UNC パス", logs.startswith("\\\\fileserver\\ci"))
    check("preview tests パス", tests.endswith("\\tests") or "\\tests\\" in tests)

# 8. env scan は実行できる（結果は環境依存）
results = environment_scan.scan()
check("環境スキャン 4 項目", len(results) == 4)

# 9. help texts
check("ヘルプ文言あり", len(help_texts.AGENT_LABEL) > 0)

print()
print("FAILED:" + str(errors) if errors else "ALL PASSED")
