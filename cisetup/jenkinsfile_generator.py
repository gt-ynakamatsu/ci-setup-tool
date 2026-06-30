from __future__ import annotations

from pathlib import Path


def build_agent_declaration(agent_label: str | None) -> str:
    if not agent_label or not agent_label.strip():
        return "any"
    escaped = agent_label.strip().replace("\\", "\\\\").replace("'", "\\'")
    return f"{{\n        label '{escaped}'\n    }}"


def generate_jenkinsfile(template: str, output_path: Path, config) -> None:
    # CI_FILE_SERVER パラメータは単一文字列。複数書き込み先のうち先頭を既定値に使う
    # （個人 ID 入りの値はコミット前に空へ退避されるため通常は空になる）。
    ci_server = config.jenkins.ci_file_server.replace("\\", "\\\\")
    poll = config.jenkins.poll_schedule.strip()
    poll_trigger = (
        ""
        if not poll
        else f"        pollSCM('{poll}')"
    )

    content = (
        template.lstrip("\ufeff")
        .replace("{{AGENT_DECLARATION}}", build_agent_declaration(config.jenkins.agent_label))
        .replace("{{CRON_SCHEDULE}}", config.jenkins.cron_schedule)
        .replace("{{POLL_TRIGGER}}", poll_trigger)
        .replace("{{CI_FILE_SERVER}}", ci_server)
        .replace("{{TEAMS_CREDENTIAL_ID}}", config.jenkins.teams_credential_id)
        .replace("{{BUILD_TIMEOUT}}", str(config.jenkins.build_timeout_minutes))
        .replace("{{LOG_RETENTION}}", str(config.jenkins.log_retention_count))
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8", newline="\n")
