"""Agent registry for the default orchestration path."""

from taskpilot_ai.agents.base import Agent
from taskpilot_ai.agents.specialists import (
    DeduplicationAgent,
    ExtractionAgent,
    IngestionAgent,
    PlanningAgent,
    PrioritizationAgent,
)


def build_default_agent_stack() -> list[Agent]:
    return [
        IngestionAgent(),
        ExtractionAgent(),
        DeduplicationAgent(),
        PrioritizationAgent(),
        PlanningAgent(),
    ]

