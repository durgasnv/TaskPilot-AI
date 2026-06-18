"""Initial specialist agents for the Day 1 scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from taskpilot_ai.agents.base import Agent
from taskpilot_ai.agents.react_runtime import build_extraction_packet, build_ingestion_packet
from taskpilot_ai.config import AppConfig
from taskpilot_ai.models import RankedTask, TaskSource
from taskpilot_ai.orchestration.state import WorkflowState
from taskpilot_ai.tools.source_reader import FileSystemSourceReader, SourceReader


class AgentMode(str, Enum):
    PASSIVE = "passive"
    REACT = "react"


@dataclass(slots=True)
class IngestionAgent(Agent):
    name: str = "ingestion"
    config: AppConfig = field(default_factory=AppConfig)
    reader: SourceReader = field(default_factory=FileSystemSourceReader)
    mode: AgentMode = AgentMode.REACT

    def run(self, state: WorkflowState) -> WorkflowState:
        for source_config in self.config.sources:
            if not source_config.enabled:
                continue

            source = TaskSource(source_config.name)
            result = self.reader.read(source=source, location=source_config.path)
            if result.document:
                state.raw_inputs[source.value] = result.document
                state.memory.source_locations[source.value] = result.document.location or "inline"
                packet = build_ingestion_packet(result.document)
                state.memory.react_scratchpad.append(
                    f"{self.name}:{source.value}:{packet.system_prompt}"
                )
                state.trace(self.name, f"Loaded source '{source.value}' from file dependency.")
            else:
                state.trace(
                    self.name,
                    f"Skipped source '{source.value}': {result.error}",
                )
        return state


@dataclass(slots=True)
class ExtractionAgent(Agent):
    name: str = "extraction"
    mode: AgentMode = AgentMode.REACT

    def run(self, state: WorkflowState) -> WorkflowState:
        for document in state.raw_inputs.values():
            packet = build_extraction_packet(document)
            state.memory.react_scratchpad.append(
                f"{self.name}:{document.source.value}:{packet.user_prompt[:120]}"
            )
        state.memory.extracted_task_ids.update(task.task_id for task in state.extracted_tasks)
        state.trace(self.name, "Prepared ReAct extraction prompts and recorded task memory.")
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
