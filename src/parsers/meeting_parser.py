"""
Meeting transcript parser.

Input:  data/raw/meeting_transcripts.json
Output: list[UnifiedTask]

Each meeting becomes ONE UnifiedTask representing the meeting itself.
Pre-extracted action items are surfaced in raw_text and description.

The raw transcript text is included in raw_text so the LLM Extraction
Agent can independently discover additional buried action items that the
pre-declared list may have missed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.pipeline.privacy import scrub_text
from src.schemas.unified_task import Severity, TaskSource, TaskStatus, UnifiedTask


def _parse_dt(date_str: str, time_str: str) -> Optional[datetime]:
    try:
        combined = f"{date_str}T{time_str.replace(' UTC', '+00:00')}"
        if "+" not in combined and "Z" not in combined:
            combined += "+00:00"
        return datetime.fromisoformat(combined)
    except (ValueError, TypeError):
        return None


def _build_transcript_text(transcript: List[Dict[str, str]]) -> str:
    lines = []
    for turn in transcript:
        speaker = turn.get("speaker", "unknown")
        text = turn.get("text", "")
        lines.append(f"[{speaker}]: {text}")
    return "\n".join(lines)


def _parse_meeting(meeting: Dict[str, Any]) -> UnifiedTask:
    meeting_id = meeting.get("id", "MTG-???")
    title = meeting.get("title", "Meeting")
    date_str = meeting.get("date", "")
    time_str = meeting.get("time", "00:00 UTC")
    attendees = meeting.get("attendees", [])
    action_items = meeting.get("extracted_action_items", [])
    transcript = meeting.get("transcript", [])

    transcript_text = _build_transcript_text(transcript)
    raw_text_parts = [
        f"Meeting: {title}",
        f"Date: {date_str} {time_str}",
        f"Attendees: {', '.join(attendees)}",
        "",
        "Transcript:",
        transcript_text,
    ]
    if action_items:
        raw_text_parts += ["", "Pre-extracted action items:"]
        raw_text_parts += [f"- {item}" for item in action_items]

    description_parts = [f"Meeting on {date_str}: {title}"]
    if action_items:
        description_parts.append("Action items:")
        description_parts += [f"  • {item}" for item in action_items]

    # Infer severity based on meeting type keywords
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["p1", "incident", "war room", "emergency", "critical"]):
        severity = Severity.P1
    elif any(kw in title_lower for kw in ["security", "compliance", "audit"]):
        severity = Severity.P2
    else:
        severity = Severity.P3

    return UnifiedTask(
        task_id=meeting_id,
        source=TaskSource.TRANSCRIPT,
        source_id=meeting_id,
        title=scrub_text(title),
        description=scrub_text("\n".join(description_parts)),
        created_at=_parse_dt(date_str, time_str),
        severity=severity,
        status=TaskStatus.OPEN,
        labels=["meeting", "action-items"],
        assignee=attendees[0] if attendees else None,
        reporter=attendees[0] if attendees else None,
        extracted=True,
        raw_text=scrub_text("\n".join(raw_text_parts)),
        business_impact=scrub_text(
            "; ".join(action_items[:2]) if action_items else ""
        ),
    )


def parse_meetings(
    file_path: str | Path = "data/raw/meeting_transcripts.json",
) -> List[UnifiedTask]:
    """
    Parse the meeting transcripts JSON file and return a list of UnifiedTask objects.

    Args:
        file_path: Path to the transcripts JSON file.

    Returns:
        List of UnifiedTask objects, one per meeting.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON structure is invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Meeting transcript file not found: {path.resolve()}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    meetings: List[Dict[str, Any]] = data.get("meetings", [])
    if not meetings:
        raise ValueError(f"No meetings found in file: {path}")

    tasks = []
    for meeting in meetings:
        try:
            tasks.append(_parse_meeting(meeting))
        except Exception as exc:
            raise ValueError(
                f"Failed to parse meeting {meeting.get('id', '?')}: {exc}"
            ) from exc

    return tasks
