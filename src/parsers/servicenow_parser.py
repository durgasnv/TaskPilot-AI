"""
ServiceNow incident parser.

Input:  data/raw/servicenow_defects.json
Output: list[UnifiedTask]

Maps ServiceNow priority strings (e.g. "1 - Critical") to canonical Severity.
The 'number' field (e.g. "INC0001001") becomes the task_id prefix "SN-".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.pipeline.privacy import scrub_text
from src.schemas.unified_task import Severity, TaskSource, TaskStatus, UnifiedTask

_SEVERITY_MAP: Dict[str, Optional[Severity]] = {
    "1 - Critical": Severity.P1,
    "1": Severity.P1,
    "2 - High": Severity.P2,
    "2": Severity.P2,
    "3 - Moderate": Severity.P3,
    "3": Severity.P3,
    "4 - Low": Severity.P4,
    "4": Severity.P4,
    "P1": Severity.P1,
    "P2": Severity.P2,
    "P3": Severity.P3,
    "P4": Severity.P4,
}

_STATUS_MAP: Dict[str, TaskStatus] = {
    "open": TaskStatus.OPEN,
    "in progress": TaskStatus.IN_PROGRESS,
    "resolved": TaskStatus.RESOLVED,
    "closed": TaskStatus.CLOSED,
    "new": TaskStatus.OPEN,
    "work in progress": TaskStatus.IN_PROGRESS,
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


def _parse_record(record: Dict[str, Any]) -> UnifiedTask:
    number = record.get("number", "UNKNOWN")
    task_id = f"SN-{number}"
    status_str = (record.get("state") or "open").lower()

    severity_str = record.get("severity") or record.get("priority", "")
    # Extract leading digit from "1 - Critical" style strings
    if severity_str and severity_str[0].isdigit():
        severity_key = severity_str
    else:
        severity_key = severity_str

    return UnifiedTask(
        task_id=task_id,
        source=TaskSource.SERVICENOW,
        source_id=number,
        title=scrub_text(record.get("short_description", "")),
        description=scrub_text(record.get("description", "")),
        deadline=_parse_dt(record.get("sla_due")),
        created_at=_parse_dt(record.get("opened_at")),
        updated_at=_parse_dt(record.get("updated_at")),
        severity=_SEVERITY_MAP.get(severity_key),
        status=_STATUS_MAP.get(status_str, TaskStatus.OPEN),
        labels=record.get("tags", []),
        assignee=scrub_text(record.get("assigned_to", "")),
        reporter=scrub_text(record.get("opened_by", "")),
        team=record.get("category"),
        blocks=[],
        blocked_by=[record.get("related_jira")] if record.get("related_jira") else [],
        extracted=False,
        business_impact=scrub_text(record.get("business_impact", "")),
        related_tasks=[record["related_jira"]] if record.get("related_jira") else [],
    )


def parse_servicenow(
    file_path: str | Path = "data/raw/servicenow_defects.json",
) -> List[UnifiedTask]:
    """
    Parse a ServiceNow incidents JSON file and return a list of UnifiedTask objects.

    Args:
        file_path: Path to the ServiceNow JSON file.

    Returns:
        List of UnifiedTask objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON structure is invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ServiceNow data file not found: {path.resolve()}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    records: List[Dict[str, Any]] = data.get("records", [])
    if not records:
        raise ValueError(f"No records found in ServiceNow file: {path}")

    tasks = []
    for record in records:
        try:
            tasks.append(_parse_record(record))
        except Exception as exc:
            raise ValueError(
                f"Failed to parse ServiceNow record {record.get('number', '?')}: {exc}"
            ) from exc

    return tasks
