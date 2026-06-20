"""Specialist agents for the TaskPilot orchestration pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum

from taskpilot_ai.agents.base import Agent
from taskpilot_ai.agents.react_runtime import build_extraction_packet, build_ingestion_packet
from taskpilot_ai.config import AppConfig
from taskpilot_ai.interfaces.protocols import VectorDeduplicatorProtocol, PrioritizerProtocol
from taskpilot_ai.llm.client import LLMClient, MockLLMClient
from taskpilot_ai.models import FileSource
from taskpilot_ai.orchestration.state import WorkflowState
from taskpilot_ai.tools.source_reader import FileSystemSourceReader, NormalizerSourceReader, SourceReader
from taskpilot_ai.unified_task import Severity, TaskSource, UnifiedTask


# Maps our internal FileSource names to UnifiedTask TaskSource enum values.
_SOURCE_MAP: dict[str, TaskSource] = {
    FileSource.JIRA.value: TaskSource.JIRA,
    FileSource.SERVICENOW.value: TaskSource.SERVICENOW,
    FileSource.OUTLOOK.value: TaskSource.EMAIL,
    FileSource.MEETING_NOTES.value: TaskSource.TRANSCRIPT,
}


def _parse_unified_tasks(llm_output: str, source: FileSource) -> list[UnifiedTask]:
    """Parse LLM JSON response into UnifiedTask objects."""
    try:
        items = json.loads(llm_output)
    except json.JSONDecodeError:
        return []

    unified_source = _SOURCE_MAP.get(source.value, TaskSource.JIRA)
    tasks = []
    for item in items:
        try:
            tasks.append(
                UnifiedTask(
                    task_id=item.get("task_id", "UNKNOWN"),
                    source=unified_source,
                    source_id=item.get("source_id", item.get("task_id", "UNKNOWN")),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    severity=item.get("severity"),
                    deadline=item.get("deadline"),
                    blocked_by=item.get("blocked_by", []),
                    blocks=item.get("blocks", []),
                    business_impact=item.get("business_impact"),
                    extracted=item.get("extracted", False),
                )
            )
        except Exception:
            continue
    return tasks


class AgentMode(str, Enum):
    REACT = "react"


@dataclass(slots=True)
class IngestionAgent(Agent):
    name: str = "ingestion"
    config: AppConfig = field(default_factory=AppConfig)
    reader: SourceReader = field(default_factory=FileSystemSourceReader)
    mode: AgentMode = AgentMode.REACT

    def run(self, state: WorkflowState) -> WorkflowState:
        # Bulk path: Dev1's normalizer handles all parsing and PII scrubbing in one call.
        if isinstance(self.reader, NormalizerSourceReader):
            result = self.reader.load_all()
            for err in result.errors:
                state.trace(self.name, f"Normalizer warning: {err}")
            state.extracted_tasks.extend(result.tasks)
            for src, count in result.source_counts.items():
                state.memory.source_locations[src] = f"data/raw/{src}"
            state.trace(
                self.name,
                f"Normalizer loaded {len(result.tasks)} tasks from {result.source_counts}.",
            )
            return state

        # Per-file path: FileSystemSourceReader reads raw files one at a time.
        for source_config in self.config.sources:
            if not source_config.enabled:
                continue

            source = FileSource(source_config.name)
            result = self.reader.read(
                source=source,
                location=source_config.path,
                retries=source_config.retries,
            )
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
    llm: LLMClient = field(default_factory=MockLLMClient)

    def run(self, state: WorkflowState) -> WorkflowState:
        for file_source_key, document in state.raw_inputs.items():
            packet = build_extraction_packet(document)
            state.memory.react_scratchpad.append(
                f"{self.name}:{file_source_key}:{packet.user_prompt[:120]}"
            )
            response = self.llm.complete(packet.system_prompt, packet.user_prompt)
            tasks = _parse_unified_tasks(response.content, document.source)
            state.extracted_tasks.extend(tasks)
            state.trace(
                self.name,
                f"Extracted {len(tasks)} task(s) from '{file_source_key}' via {response.model}.",
            )

        state.memory.extracted_task_ids.update(t.task_id for t in state.extracted_tasks)
        if not state.raw_inputs:
            state.trace(self.name, "No source documents loaded; skipping LLM extraction.")
        return state


@dataclass(slots=True)
class DeduplicationAgent(Agent):
    name: str = "deduplication"
    engine: VectorDeduplicatorProtocol | None = None

    def run(self, state: WorkflowState) -> WorkflowState:
        if self.engine is not None:
            state.deduplicated_tasks = self.engine.deduplicate(state.extracted_tasks)
            state.trace(
                self.name,
                f"Deduplication via engine reduced to {len(state.deduplicated_tasks)} task(s).",
            )
        else:
            if not state.deduplicated_tasks:
                state.deduplicated_tasks = list(state.extracted_tasks)
            state.trace(self.name, "Passthrough dedup (no engine connected). Dev3 will replace.")
        return state


@dataclass(slots=True)
class PrioritizationAgent(Agent):
    name: str = "prioritization"
    engine: PrioritizerProtocol | None = None

    def run(self, state: WorkflowState) -> WorkflowState:
        if self.engine is not None:
            state.ranked_tasks = self.engine.rank(state.deduplicated_tasks)
        else:
            if not state.ranked_tasks:
                for task in state.deduplicated_tasks:
                    task.priority_score = 0.0
                    task.priority_rationale = "Ranking logic not connected yet. Dev3 will replace."
                state.ranked_tasks = list(state.deduplicated_tasks)

        if state.emergency_mode:
            state.ranked_tasks.sort(
                key=lambda t: (0 if (t.severity or "") == Severity.P1 else 1, -(t.priority_score or 0.0))
            )
            state.trace(self.name, "Emergency mode: P1 tasks sorted to top.")

        state.memory.ranked_task_ids = [t.task_id for t in state.ranked_tasks]
        state.trace(self.name, f"Ranked {len(state.ranked_tasks)} task(s).")
        return state


@dataclass(slots=True)
class PlanningAgent(Agent):
    name: str = "planning"

    def run(self, state: WorkflowState) -> WorkflowState:
        if not state.daily_plan:
            state.daily_plan = [t.title for t in state.ranked_tasks]
        state.trace(self.name, "Built daily plan from ranked tasks.")
        return state
