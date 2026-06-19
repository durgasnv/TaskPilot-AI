"""
Jira board parser.

Input:  data/raw/jira_board.json
Output: list[UnifiedTask]

Maps Jira severity strings to the canonical Severity enum.
PII scrubbing is applied to description fields before population.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.pipeline.privacy import scrub_text
from src.schemas.unified_task import Severity, TaskSource, TaskStatus, UnifiedTask

# ---------------------------------------------------------------------------
# Severity mapping: Jira uses "P1" / "P2" etc. directly — simple passthrough
# ---------------------------------------------------------------------------

_SEVERITY_MAP: Dict[str, Optional[Severity]] = {
    "P1": Severity.P1,
    "P2": Severity.P2,
    "P3": Severity.P3,
    "P4": Severity.P4,
    "1 - Critical": Severity.P1,
    "2 - High": Severity.P2,
    "3 - Moderate": Severity.P3,
    "4 - Low": Severity.P4,
}

_STATUS_MAP: Dict[str, TaskStatus] = {
    "open": TaskStatus.OPEN,
    "in_progress": TaskStatus.IN_PROGRESS,
    "blocked": TaskStatus.BLOCKED,
    "resolved": TaskStatus.RESOLVED,
    "closed": TaskStatus.CLOSED,
    "in progress": TaskStatus.IN_PROGRESS,
    "done": TaskStatus.RESOLVED,
}


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _parse_issue(issue: Dict[str, Any]) -> UnifiedTask:
    raw_description = issue.get("description", "")
    severity_str = issue.get("severity", "")
    status_str = (issue.get("status") or "open").lower()

    return UnifiedTask(
        task_id=f"JIRA-{issue['id'].replace('JIRA-', '')}",
        source=TaskSource.JIRA,
        source_id=issue["id"],
        title=scrub_text(issue.get("title", "")),
        description=scrub_text(raw_description),
        deadline=_parse_dt(issue.get("deadline")),
        created_at=_parse_dt(issue.get("created_at")),
        updated_at=_parse_dt(issue.get("updated_at")),
        severity=_SEVERITY_MAP.get(severity_str),
        status=_STATUS_MAP.get(status_str, TaskStatus.OPEN),
        labels=issue.get("labels", []),
        assignee=issue.get("assignee"),
        reporter=issue.get("reporter"),
        team=issue.get("team"),
        blocks=issue.get("blocks", []),
        blocked_by=issue.get("blocked_by", []),
        extracted=False,
        business_impact=scrub_text(issue.get("business_impact", "")),
    )


def parse_jira(file_path: str | Path = "data/raw/jira_board.json") -> List[UnifiedTask]:
    """
    Parse a Jira board JSON file and return a list of UnifiedTask objects.

    Args:
        file_path: Path to the Jira JSON file. Defaults to data/raw/jira_board.json.

    Returns:
        List of UnifiedTask objects, one per Jira issue.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON structure is invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Jira data file not found: {path.resolve()}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    issues: List[Dict[str, Any]] = data.get("issues", [])
    if not issues:
        raise ValueError(f"No issues found in Jira file: {path}")

    tasks = []
    for issue in issues:
        try:
            tasks.append(_parse_issue(issue))
        except Exception as exc:
            raise ValueError(
                f"Failed to parse Jira issue {issue.get('id', '?')}: {exc}"
            ) from exc

    return tasks
