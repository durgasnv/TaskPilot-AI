"""File-reading primitives for the ingestion layer.

TaskRecord and RankedTask have been replaced by UnifiedTask (unified_task.py),
which is the canonical data contract shared across all agents and teammates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FileSource(str, Enum):
    """Maps config source names to their string keys. Internal to the ingestion layer."""
    JIRA = "jira"
    SERVICENOW = "servicenow"
    OUTLOOK = "outlook"
    MEETING_NOTES = "meeting_notes"


@dataclass(slots=True)
class SourceDocument:
    source: FileSource
    content: str
    location: str | None = None
