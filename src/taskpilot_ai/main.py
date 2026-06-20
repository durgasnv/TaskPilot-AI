"""CLI entry point — runs the full TaskPilot pipeline and prints the daily plan."""

from taskpilot_ai.orchestration.graph import TaskPilotGraph
from taskpilot_ai.orchestration.state import WorkflowState


def main() -> None:
    print("TaskPilot AI — generating your daily plan...\n")

    graph = TaskPilotGraph()
    state = graph.run(WorkflowState())

    print(f"Sources loaded : {list(state.raw_inputs.keys()) or 'none (use NormalizerSourceReader for real data)'}")
    print(f"Tasks extracted: {len(state.extracted_tasks)}")
    print(f"After dedup    : {len(state.deduplicated_tasks)}")
    print()

    print("── Daily Plan ──────────────────────────────────")
    if state.daily_plan:
        for i, title in enumerate(state.daily_plan, 1):
            task = next((t for t in state.ranked_tasks if t.title == title), None)
            severity = f"[{task.severity}]" if task and task.severity else ""
            print(f"  {i}. {severity} {title}")
    else:
        print("  (no tasks — check source data)")

    print()
    print(f"Execution traces: {len(state.traces)}")
    if any(state.traces):
        for trace in state.traces:
            print(f"  [{trace.step}] {trace.detail}")


if __name__ == "__main__":
    main()
