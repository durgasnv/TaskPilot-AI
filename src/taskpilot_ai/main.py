"""CLI entry point for local orchestration smoke tests."""

from taskpilot_ai.orchestration.graph import TaskPilotGraph
from taskpilot_ai.orchestration.state import WorkflowState


def main() -> None:
    graph = TaskPilotGraph()
    state = graph.run(WorkflowState())
    print("TaskPilot graph executed.")
    print(f"Agents run: {len(state.traces)}")


if __name__ == "__main__":
    main()

