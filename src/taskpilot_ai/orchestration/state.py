"""State and memory objects for the orchestration loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from taskpilot_ai.models import SourceDocument
from taskpilot_ai.unified_task import UnifiedTask


@dataclass(slots=True)
class AgentMemory:
    last_user_question: str | None = None
    source_checksums: dict[str, str] = field(default_factory=dict)
    source_locations: dict[str, str] = field(default_factory=dict)
    extracted_task_ids: set[str] = field(default_factory=set)
    ranked_task_ids: list[str] = field(default_factory=list)
    alerts_sent: list[str] = field(default_factory=list)
    react_scratchpad: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionTrace:
    step: str
    detail: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class WorkflowState:
    raw_inputs: dict[str, SourceDocument] = field(default_factory=dict)
    scrubbed_inputs: dict[str, SourceDocument] = field(default_factory=dict)
    extracted_tasks: list[UnifiedTask] = field(default_factory=list)
    deduplicated_tasks: list[UnifiedTask] = field(default_factory=list)
    ranked_tasks: list[UnifiedTask] = field(default_factory=list)
    daily_plan: list[str] = field(default_factory=list)
    traces: list[ExecutionTrace] = field(default_factory=list)
    memory: AgentMemory = field(default_factory=AgentMemory)
    emergency_mode: bool = False
    # Feature 1: multi-agent roster
    agents_roster: list[dict] = field(default_factory=list)
    # Feature 3: team dashboard
    team_view: dict = field(default_factory=dict)
    # Feature 5: calendar-aware plan
    calendar_blocks: list[dict] = field(default_factory=list)

    def trace(self, step: str, detail: str) -> None:
        self.traces.append(ExecutionTrace(step=step, detail=detail))
