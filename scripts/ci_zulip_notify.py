"""Publish bounded GitHub Actions results through the existing Zulip adapter.

Reads only GitHub-provided environment variables; no repository modification,
no PR merge, no deployment. Safe no-op when Zulip is unconfigured.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.zulip_notifier import publish_research_update


def main() -> int:
    event = os.getenv("GITHUB_EVENT_NAME", "")
    conclusion = os.getenv("CI_CONCLUSION", os.getenv("WORKFLOW_CONCLUSION", ""))
    status = "HISTORICAL"
    result = publish_research_update(
        stream="ci-testing",
        topic="GitHub-Actions" if "pull" not in event else "Build-results",
        message_type="ci_result",
        data_status=status,
        source="github_actions",
        content=(
            f"Workflow={os.getenv('GITHUB_WORKFLOW', 'unknown')} "
            f"event={event} branch={os.getenv('GITHUB_REF_NAME', 'unknown')} "
            f"sha={os.getenv('GITHUB_SHA', 'unknown')[:12]} "
            f"conclusion={conclusion or 'in_progress'} "
            f"run={os.getenv('GITHUB_RUN_URL') or os.getenv('GITHUB_SERVER_URL', '')}/"
            f"{os.getenv('GITHUB_REPOSITORY', '')}/actions/runs/{os.getenv('GITHUB_RUN_ID', '')}"
        ),
        evidence=[os.getenv("GITHUB_SHA", "")[:12]],
    )
    print(json.dumps({"status": result.get("status"), "credentials_exposed": False}))
    return 0  # never fail CI because a communication channel is down


if __name__ == "__main__":
    raise SystemExit(main())
