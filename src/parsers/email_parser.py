"""
Outlook email inbox parser.

Input:  data/raw/outlook_inbox.json
Output: list[UnifiedTask]

Each email becomes ONE structured task capturing the email's primary
actionable context.  Hidden action items embedded in the email body are
exposed via the ``raw_text`` field and the ``labels`` list, so the
LLM Extraction Agent can parse them from there.

The parser does NOT call an LLM — it only reads pre-declared
``hidden_action_items`` from the JSON for test/demo purposes.
In production, the Extraction Agent reads ``raw_text`` via LLM.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.pipeline.privacy import scrub_text
from src.schemas.unified_task import Severity, TaskSource, TaskStatus, UnifiedTask

# Heuristic: email labels → severity
_LABEL_SEVERITY_MAP: Dict[str, Severity] = {
    "urgent": Severity.P1,
    "vp": Severity.P1,
    "escalation": Severity.P1,
    "customer-escalation": Severity.P1,
    "security": Severity.P1,
    "legal": Severity.P1,
    "compliance": Severity.P1,
    "p1": Severity.P1,
    "p2": Severity.P2,
    "p3": Severity.P3,
    "p4": Severity.P4,
}


def _infer_severity(labels: List[str]) -> Optional[Severity]:
    for label in labels:
        sev = _LABEL_SEVERITY_MAP.get(label.lower())
        if sev:
            return sev
    return Severity.P3  # default for unclassified emails


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


def _parse_email(email: Dict[str, Any]) -> UnifiedTask:
    email_id = email.get("id", "EMAIL-???")
    subject = email.get("subject", "(no subject)")
    body = email.get("body", "")
    labels = email.get("labels", [])
    hidden_items = email.get("hidden_action_items", [])

    # Combine body + hidden action items into raw_text for LLM extraction
    raw_text_parts = [f"Subject: {subject}", f"Body:\n{body}"]
    if hidden_items:
        raw_text_parts.append(
            "Action Items (pre-identified):\n"
            + "\n".join(f"- {item}" for item in hidden_items)
        )

    # Description is a scrubbed summary of the email for display
    description_parts = [f"Email from: {email.get('from', 'unknown')}"]
    if hidden_items:
        description_parts.append("Action items:")
        description_parts.extend(f"  • {item}" for item in hidden_items)

    return UnifiedTask(
        task_id=email_id,
        source=TaskSource.EMAIL,
        source_id=email_id,
        title=scrub_text(subject),
        description=scrub_text("\n".join(description_parts)),
        deadline=_parse_dt(email.get("received_at")),  # received_at as a reference point
        created_at=_parse_dt(email.get("received_at")),
        severity=_infer_severity(labels),
        status=TaskStatus.OPEN,
        labels=labels,
        assignee="dev_alice",  # recipient / owner of this mailbox
        reporter=scrub_text(email.get("from", "")),
        extracted=False,
        raw_text=scrub_text("\n".join(raw_text_parts)),
        business_impact=scrub_text(
            "; ".join(hidden_items[:2]) if hidden_items else ""
        ),
        related_tasks=(
            [email["related_jira"]] if email.get("related_jira") else []
        ),
    )


def parse_emails(
    file_path: str | Path = "data/raw/outlook_inbox.json",
) -> List[UnifiedTask]:
    """
    Parse the Outlook inbox JSON file and return a list of UnifiedTask objects.

    Args:
        file_path: Path to the inbox JSON file.

    Returns:
        List of UnifiedTask objects, one per email.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON structure is invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Email data file not found: {path.resolve()}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    emails: List[Dict[str, Any]] = data.get("emails", [])
    if not emails:
        raise ValueError(f"No emails found in file: {path}")

    tasks = []
    for email in emails:
        try:
            tasks.append(_parse_email(email))
        except Exception as exc:
            raise ValueError(
                f"Failed to parse email {email.get('id', '?')}: {exc}"
            ) from exc

    return tasks
