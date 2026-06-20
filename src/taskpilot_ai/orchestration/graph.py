"""Simple orchestration loop for the initial agent topology."""

from __future__ import annotations

from dataclasses import dataclass, field

from taskpilot_ai.agents.base import Agent
from taskpilot_ai.agents.registry import build_default_agent_stack
from taskpilot_ai.orchestration.state import WorkflowState


@dataclass(slots=True)
class TaskPilotGraph:
    agents: list[Agent] = field(default_factory=build_default_agent_stack)

    def run(self, initial_state: WorkflowState | None = None) -> WorkflowState:
        state = initial_state or WorkflowState()
        for agent in self.agents:
            state = agent.run(state)
        return state

