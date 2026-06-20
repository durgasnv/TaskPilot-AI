"""File-reading primitives for the ingestion layer.

TaskRecord and RankedTask have been replaced by UnifiedTask (unified_task.py),
which is the canonical data contract shared across all agents and teammates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum


class FileSource(str, Enum):
    """Maps config source names to their string keys. Internal to the ingestion layer."""
    JIRA = "jira"
    SERVICENOW = "servicenow"
    OUTLOOK = "outlook"
    MEETING_NOTES = "meeting_notes"
    INJECTED = "injected"  # runtime-dropped files of unknown or mixed format


def detect_source(content: str) -> FileSource:
    """
    Best-effort guess of a file's source type from its content.
    Used by the event monitor when a file is dropped at runtime.
    Falls back to INJECTED if no known schema is detected.
    """
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return FileSource.INJECTED

    if isinstance(data, dict):
        # Top-level wrapper keys used by each source
        if "issues" in data or "board" in data:
            return FileSource.JIRA
        if "records" in data or "incidents" in data:
            return FileSource.SERVICENOW
        if "emails" in data or "mailbox" in data:
            return FileSource.OUTLOOK
        if "meetings" in data or "transcript" in data:
            return FileSource.MEETING_NOTES

        # Single-record wrappers like {"incident": {...}} or {"issue": {...}}
        for key in ("incident", "record"):
            if key in data and isinstance(data[key], dict):
                inner = data[key]
                if "short_description" in inner or "number" in inner:
                    return FileSource.SERVICENOW
        for key in ("issue", "ticket"):
            if key in data and isinstance(data[key], dict):
                inner = data[key]
                if "summary" in inner or "key" in inner:
                    return FileSource.JIRA

    if isinstance(data, list) and data:
        first = data[0] if isinstance(data[0], dict) else {}
        if "key" in first or "story_points" in first:
            return FileSource.JIRA
        if "number" in first and "short_description" in first:
            return FileSource.SERVICENOW
        if "subject" in first or "from" in first:
            return FileSource.OUTLOOK

    return FileSource.INJECTED


@dataclass(slots=True)
class SourceDocument:
    source: FileSource
    content: str
    location: str | None = None
