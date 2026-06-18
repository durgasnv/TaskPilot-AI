"""State and memory objects for the orchestration loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from taskpilot_ai.models import RankedTask, TaskRecord


@dataclass(slots=True)
class AgentMemory:
    last_user_question: str | None = None
    source_checksums: dict[str, str] = field(default_factory=dict)
    extracted_task_ids: set[str] = field(default_factory=set)
    ranked_task_ids: list[str] = field(default_factory=list)
    alerts_sent: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionTrace:
    step: str
    detail: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class WorkflowState:
    raw_inputs: dict[str, object] = field(default_factory=dict)
    scrubbed_inputs: dict[str, object] = field(default_factory=dict)
    extracted_tasks: list[TaskRecord] = field(default_factory=list)
    deduplicated_tasks: list[TaskRecord] = field(default_factory=list)
    ranked_tasks: list[RankedTask] = field(default_factory=list)
    daily_plan: list[str] = field(default_factory=list)
    traces: list[ExecutionTrace] = field(default_factory=list)
    memory: AgentMemory = field(default_factory=AgentMemory)

    def trace(self, step: str, detail: str) -> None:
        self.traces.append(ExecutionTrace(step=step, detail=detail))
