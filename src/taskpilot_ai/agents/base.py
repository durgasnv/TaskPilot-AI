"""Base abstractions for TaskPilot agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from taskpilot_ai.orchestration.state import WorkflowState


class Agent(ABC):
    name: str

    @abstractmethod
    def run(self, state: WorkflowState) -> WorkflowState:
        """Apply one responsibility to the workflow state."""

