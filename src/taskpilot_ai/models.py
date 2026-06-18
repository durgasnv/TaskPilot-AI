"""Shared models used across the agent system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TaskSource(str, Enum):
    JIRA = "jira"
    SERVICENOW = "servicenow"
    OUTLOOK = "outlook"
    MEETING_NOTES = "meeting_notes"


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    title: str
    description: str
    source: TaskSource
    created_at: datetime | None = None
    deadline: datetime | None = None
    severity: str | None = None
    dependencies: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RankedTask:
    task: TaskRecord
    score: float
    rationale: str

