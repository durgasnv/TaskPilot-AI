"""Initial specialist agents for the Day 1 scaffold."""

from __future__ import annotations

from dataclasses import dataclass

from taskpilot_ai.agents.base import Agent
from taskpilot_ai.models import RankedTask
from taskpilot_ai.orchestration.state import WorkflowState


@dataclass(slots=True)
class IngestionAgent(Agent):
    name: str = "ingestion"

    def run(self, state: WorkflowState) -> WorkflowState:
        state.trace(self.name, "Accepted source payloads into orchestration state.")
        return state


@dataclass(slots=True)
class ExtractionAgent(Agent):
    name: str = "extraction"

    def run(self, state: WorkflowState) -> WorkflowState:
        state.memory.extracted_task_ids.update(task.task_id for task in state.extracted_tasks)
        state.trace(self.name, "Recorded extracted task identifiers in memory.")
        return state


@dataclass(slots=True)
class DeduplicationAgent(Agent):
    name: str = "deduplication"

    def run(self, state: WorkflowState) -> WorkflowState:
        if not state.deduplicated_tasks:
            state.deduplicated_tasks = list(state.extracted_tasks)
        state.trace(self.name, "Prepared deduplicated task set for prioritization.")
        return state


@dataclass(slots=True)
class PrioritizationAgent(Agent):
    name: str = "prioritization"

    def run(self, state: WorkflowState) -> WorkflowState:
        if not state.ranked_tasks:
            state.ranked_tasks = [
                RankedTask(
                    task=task,
                    score=0.0,
                    rationale="Ranking logic not connected yet.",
                )
                for task in state.deduplicated_tasks
            ]
        state.memory.ranked_task_ids = [entry.task.task_id for entry in state.ranked_tasks]
        state.trace(self.name, "Generated ranked task placeholders and memory pointers.")
        return state


@dataclass(slots=True)
class PlanningAgent(Agent):
    name: str = "planning"

    def run(self, state: WorkflowState) -> WorkflowState:
        if not state.daily_plan:
            state.daily_plan = [entry.task.title for entry in state.ranked_tasks]
        state.trace(self.name, "Built daily plan from ranked tasks.")
        return state

