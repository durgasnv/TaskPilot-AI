"""
Normalization layer.

Orchestrates all four parsers and returns a single deduplicated list of
UnifiedTask objects ready for the embedding / dedup engine (Dev 3) and
the agent framework (Dev 2).

Entry point: normalize_all_sources()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.parsers.email_parser import parse_emails
from src.parsers.jira_parser import parse_jira
from src.parsers.meeting_parser import parse_meetings
from src.parsers.servicenow_parser import parse_servicenow
from src.schemas.unified_task import UnifiedTask


class NormalizationResult:
    """Structured return value from normalize_all_sources."""

    def __init__(
        self,
        tasks: List[UnifiedTask],
        source_counts: Dict[str, int],
        errors: List[str],
    ) -> None:
        self.tasks = tasks
        self.source_counts = source_counts
        self.errors = errors

    @property
    def total(self) -> int:
        return len(self.tasks)

    def to_dict(self) -> dict:
        return {
            "total_tasks": self.total,
            "source_counts": self.source_counts,
            "errors": self.errors,
            "tasks": [t.model_dump(mode="json") for t in self.tasks],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


def normalize_all_sources(
    jira_path: str | Path = "data/raw/jira_board.json",
    servicenow_path: str | Path = "data/raw/servicenow_defects.json",
    email_path: str | Path = "data/raw/outlook_inbox.json",
    meeting_path: str | Path = "data/raw/meeting_transcripts.json",
    injected_path: Optional[str | Path] = "data/injected",
) -> NormalizationResult:
    """
    Parse all data sources and return a single unified task list.

    Each parser failure is logged to ``errors`` without crashing the pipeline
    so partial results remain usable during development.

    Args:
        jira_path: Path to Jira board JSON.
        servicenow_path: Path to ServiceNow defects JSON.
        email_path: Path to Outlook inbox JSON.
        meeting_path: Path to meeting transcripts JSON.
        injected_path: Directory to scan for injected P1 files (demo use).

    Returns:
        NormalizationResult containing all tasks and metadata.
    """
    all_tasks: List[UnifiedTask] = []
    source_counts: Dict[str, int] = {}
    errors: List[str] = []

    # --- Jira ---
    try:
        jira_tasks = parse_jira(jira_path)
        all_tasks.extend(jira_tasks)
        source_counts["jira"] = len(jira_tasks)
    except Exception as exc:
        errors.append(f"jira: {exc}")
        source_counts["jira"] = 0

    # --- ServiceNow ---
    try:
        sn_tasks = parse_servicenow(servicenow_path)
        all_tasks.extend(sn_tasks)
        source_counts["servicenow"] = len(sn_tasks)
    except Exception as exc:
        errors.append(f"servicenow: {exc}")
        source_counts["servicenow"] = 0

    # --- Email ---
    try:
        email_tasks = parse_emails(email_path)
        all_tasks.extend(email_tasks)
        source_counts["email"] = len(email_tasks)
    except Exception as exc:
        errors.append(f"email: {exc}")
        source_counts["email"] = 0

    # --- Meeting Transcripts ---
    try:
        meeting_tasks = parse_meetings(meeting_path)
        all_tasks.extend(meeting_tasks)
        source_counts["transcript"] = len(meeting_tasks)
    except Exception as exc:
        errors.append(f"transcript: {exc}")
        source_counts["transcript"] = 0

    # --- Injected P1 files (demo) ---
    if injected_path:
        injected_dir = Path(injected_path)
        injected_count = 0
        if injected_dir.exists():
            for json_file in injected_dir.glob("*.json"):
                try:
                    injected = _parse_injected_p1(json_file)
                    if injected:
                        all_tasks.append(injected)
                        injected_count += 1
                except Exception as exc:
                    errors.append(f"injected/{json_file.name}: {exc}")
        source_counts["injected"] = injected_count

    return NormalizationResult(
        tasks=all_tasks,
        source_counts=source_counts,
        errors=errors,
    )


def _parse_injected_p1(file_path: Path) -> Optional[UnifiedTask]:
    """
    Parse any file dropped into data/injected/ as a P1 task.
    Handles: {"incident": {...}}, {"issue": {...}}, flat dicts,
    JSON arrays, and plain text files.
    """
    from src.pipeline.privacy import scrub_text
    from src.schemas.unified_task import Severity, TaskSource, TaskStatus
    from datetime import datetime

    content = file_path.read_text(encoding="utf-8")

    # Try JSON first
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Plain text — first line becomes the title
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        title = lines[0][:200] if lines else "Injected P1 Incident"
        return UnifiedTask(
            task_id=f"INJECTED-{file_path.stem.upper()}",
            source=TaskSource.SERVICENOW,
            source_id=file_path.stem,
            title=scrub_text(title),
            description=scrub_text(" ".join(lines[1:])[:2000]),
            severity=Severity.P1,
            status=TaskStatus.OPEN,
            extracted=True,
            business_impact="Injected at runtime.",
        )

    # Unwrap single-record wrappers: {"incident": {...}}, {"issue": {...}}, etc.
    record: dict = {}
    if isinstance(data, dict):
        for key in ("incident", "issue", "ticket", "task", "record", "item", "bug"):
            if key in data and isinstance(data[key], dict):
                record = data[key]
                break
        if not record:
            record = data  # bare dict — treat the whole thing as the record
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        record = data[0]  # take the first item from an array
    else:
        return None

    # Map common field names to UnifiedTask fields
    task_id = str(
        record.get("number") or record.get("id") or record.get("key")
        or record.get("task_id") or record.get("ref") or file_path.stem
    )
    title = str(
        record.get("short_description") or record.get("title") or record.get("summary")
        or record.get("subject") or record.get("name") or "Injected P1 Incident"
    )[:200]
    description = str(
        record.get("description") or record.get("body") or record.get("details") or ""
    )[:2000]
    business_impact = str(record.get("business_impact") or record.get("impact") or "")

    raw_deadline = record.get("sla_due") or record.get("deadline") or record.get("due_date")
    deadline = None
    if raw_deadline:
        try:
            deadline = datetime.fromisoformat(str(raw_deadline).replace("Z", "+00:00"))
        except ValueError:
            pass

    raw_created = record.get("opened_at") or record.get("created_at")
    created_at = None
    if raw_created:
        try:
            created_at = datetime.fromisoformat(str(raw_created).replace("Z", "+00:00"))
        except ValueError:
            pass

    return UnifiedTask(
        task_id=f"INJECTED-{task_id}",
        source=TaskSource.SERVICENOW,
        source_id=task_id,
        title=scrub_text(title),
        description=scrub_text(description),
        deadline=deadline,
        created_at=created_at,
        severity=Severity.P1,
        status=TaskStatus.OPEN,
        labels=record.get("tags", []),
        assignee=scrub_text(str(record.get("assigned_to", ""))),
        extracted=False,
        business_impact=scrub_text(business_impact),
    )
