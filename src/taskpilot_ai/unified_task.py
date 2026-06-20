"""
Canonical data contract for TaskPilot AI.
Every parser must produce objects conforming to UnifiedTask.
No raw, PII-carrying text should ever reach an LLM — the privacy
layer must scrub description/raw_text before this object is handed off.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    P1 = "P1"  # Critical — SLA < 1 business day
    P2 = "P2"  # High     — SLA < 3 business days
    P3 = "P3"  # Medium   — SLA < 1 sprint
    P4 = "P4"  # Low      — best effort


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TaskSource(str, Enum):
    JIRA = "jira"
    SERVICENOW = "servicenow"
    EMAIL = "email"
    TRANSCRIPT = "transcript"


class UnifiedTask(BaseModel):
    """
    Canonical task object shared across all agents and components.
    Stable contract: field names and types must not change without team sign-off.
    """

    # --- Identity ---
    task_id: str = Field(
        ...,
        description="Globally unique ID within TaskPilot (e.g. 'JIRA-1234', 'SN-0045', 'EMAIL-003').",
    )
    source: TaskSource = Field(..., description="Origin system.")
    source_id: str = Field(
        ..., description="Original identifier in the source system."
    )

    # --- Core content (PII-scrubbed before population) ---
    title: str = Field(..., min_length=1, description="Short, actionable summary.")
    description: str = Field(
        default="", description="Full detail text — must be PII-scrubbed."
    )

    # --- Scheduling ---
    deadline: Optional[datetime] = Field(
        default=None, description="Hard deadline in UTC. None = no SLA."
    )
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)

    # --- Classification ---
    severity: Optional[Severity] = Field(default=None)
    status: TaskStatus = Field(default=TaskStatus.OPEN)
    labels: List[str] = Field(default_factory=list)

    # --- Assignment ---
    assignee: Optional[str] = Field(
        default=None,
        description="Role alias or scrubbed name. Never raw employee PII.",
    )
    reporter: Optional[str] = Field(default=None)
    team: Optional[str] = Field(default=None)

    # --- Dependency graph ---
    blocks: List[str] = Field(
        default_factory=list,
        description="task_ids this task blocks (downstream dependents).",
    )
    blocked_by: List[str] = Field(
        default_factory=list,
        description="task_ids that must complete before this task can proceed.",
    )

    # --- Extraction metadata ---
    extracted: bool = Field(
        default=False,
        description="True if this task was LLM-extracted from unstructured text.",
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="Original unstructured text snippet (PII-scrubbed). Used for traceability.",
    )
    extraction_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="LLM confidence score for extracted tasks (0.0–1.0).",
    )

    # --- Cross-system correlation ---
    duplicate_of: Optional[str] = Field(
        default=None,
        description="task_id of the canonical task if this one is a duplicate.",
    )
    related_tasks: List[str] = Field(
        default_factory=list,
        description="task_ids that are semantically related but not exact duplicates.",
    )

    # --- Prioritization support ---
    business_impact: Optional[str] = Field(
        default=None,
        description="Free-text business impact note (e.g. 'VP escalation', 'Customer SLA breach').",
    )
    priority_score: Optional[float] = Field(
        default=None,
        description="Computed absolute priority score. Populated by the prioritization engine.",
    )
    priority_rationale: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of the priority score.",
    )

    @field_validator("task_id")
    @classmethod
    def task_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("task_id must not be blank.")
        return v.strip()

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank.")
        return v.strip()

    model_config = {"use_enum_values": True}
