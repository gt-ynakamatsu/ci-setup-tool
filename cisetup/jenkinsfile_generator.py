from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

from .models import committed_config, config_to_dict, local_from_config, local_to_dict
from .template_store import bundled_template_dir


def build_agent_declaration(agent_label: str | None) -> str:
    if not agent_label or not agent_label.strip():
        return "any"
    escaped = agent_label.strip().replace("\\", "\\\\").replace("'", "\\'")
    return f"{{\n        label '{escaped}'\n    }}"


def build_triggers_block(cron_trigger_line: str, poll_trigger: str) -> str:
    """Declarative Pipeline の triggers ブロック全体を生成する。

    cron は Jenkins ジョブ XML（TimerTrigger）側。poll はパイプラインがジョブ内蔵のため
    ここで pollSCM する（ジョブに SCM 定義が無いと XML 側 SCMTrigger は効かない）。
    空の `triggers {}` は "triggers can not be empty" になるため、行が無ければブロックごと出さない。
    """
    lines = [line for line in (cron_trigger_line, poll_trigger) if line.strip()]
    if not lines:
        return ""
    body = "\n".join(lines)
    return f"\n    triggers {{\n{body}\n    }}\n"


def _escape_groovy(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("'", "\\'")


def build_git_checkout_groovy(config) -> str:
    """アプリの Git からソースだけを取る checkout（ジョブ SCM に依存しない）。"""
    url = _escape_groovy(config.git.repository_url)
    cred = _escape_groovy(config.git.credential_id)
    branch = _escape_groovy(config.git.branch or "main")
    return f"""                    checkout([
                        $class: 'GitSCM',
                        branches: [[name: '*/{branch}']],
                        extensions: [],
                        userRemoteConfigs: [[
                            url: '{url}',
                            credentialsId: '{cred}'
                        ]]
                    ])"""


def build_cisetup_pack_base64(config) -> str:
    """CI 定義（scripts + config + local）を zip の Base64 にする。Jenkins ジョブへ内蔵する。"""
    committed = committed_config(config)
    local = local_from_config(config)
    local.agent_workspace_path = ""
    buf = io.BytesIO()
    scripts_dir = bundled_template_dir() / "scripts"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ps1 in sorted(scripts_dir.glob("*.ps1")):
            data = ps1.read_bytes()
            if not data.startswith(b"\xef\xbb\xbf"):
                data = b"\xef\xbb\xbf" + data
            zf.writestr(f"scripts/{ps1.name}", data)
        zf.writestr(
            "cisetup.config.json",
            json.dumps(config_to_dict(committed), indent=2, ensure_ascii=False) + "\n",
        )
        zf.writestr(
            "cisetup.local.json",
            json.dumps(local_to_dict(local), indent=2, ensure_ascii=False) + "\n",
        )
    return base64.b64encode(buf.getvalue()).decode("ascii")


def render_jenkinsfile(template: str, config) -> str:
    ci_server = config.jenkins.ci_file_server.replace("\\", "\\\\")
    timezone = config.jenkins.timezone.strip() or "Asia/Tokyo"
    cron_trigger_line = ""
    poll = (config.jenkins.poll_schedule or "").strip()
    poll_trigger = ""
    if poll:
        poll_trigger = (
            f"        pollSCM(scmpoll_spec: '{_escape_groovy(poll)}', ignorePostCommitHooks: true)"
        )
    checkout_retry_count = max(1, config.jenkins.checkout_retry_count)
    triggers_block = build_triggers_block(cron_trigger_line, poll_trigger)

    content = (
        template.lstrip("\ufeff")
        .replace("{{AGENT_DECLARATION}}", build_agent_declaration(config.jenkins.agent_label))
        .replace("{{CRON_SCHEDULE}}", config.jenkins.cron_schedule)
        .replace("{{TIMEZONE}}", timezone)
        .replace("{{TRIGGERS_BLOCK}}", triggers_block)
        .replace("{{CRON_TRIGGER_LINE}}", cron_trigger_line)
        .replace("{{POLL_TRIGGER}}", poll_trigger)
        .replace("{{CI_FILE_SERVER}}", ci_server)
        .replace("{{TEAMS_CREDENTIAL_ID}}", config.jenkins.teams_credential_id)
        .replace("{{BUILD_TIMEOUT}}", str(config.jenkins.build_timeout_minutes))
        .replace("{{LOG_RETENTION}}", str(config.jenkins.log_retention_count))
        .replace("{{CHECKOUT_RETRY_COUNT}}", str(checkout_retry_count))
        .replace("{{GIT_CHECKOUT}}", build_git_checkout_groovy(config))
    )
    if "{{CISETUP_PACK_B64}}" in content:
        content = content.replace("{{CISETUP_PACK_B64}}", build_cisetup_pack_base64(config))
    return content


def generate_jenkinsfile(template: str, output_path: Path, config) -> None:
    content = render_jenkinsfile(template, config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8", newline="\n")
