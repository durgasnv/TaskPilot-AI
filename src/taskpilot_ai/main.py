"""CLI entry point — runs the full TaskPilot pipeline and prints the daily plan."""

from taskpilot_ai.agents.specialists import IngestionAgent, ExtractionAgent, DeduplicationAgent, PrioritizationAgent, PlanningAgent
from taskpilot_ai.orchestration.graph import TaskPilotGraph
from taskpilot_ai.orchestration.state import WorkflowState
from taskpilot_ai.tools.source_reader import NormalizerSourceReader


def _build_graph() -> TaskPilotGraph:
    """
    Build the pipeline. Tries Dev1's NormalizerSourceReader (full parser + PII scrubbing)
    first; falls back to FileSystemSourceReader + MockLLMClient if the normalizer
    isn't available (e.g. running in isolation without src/ on the path).
    """
    try:
        from src.pipeline.normalizer import normalize_all_sources  # noqa: F401 — import check only
        reader = NormalizerSourceReader()
    except ImportError:
        from taskpilot_ai.tools.source_reader import FileSystemSourceReader
        reader = FileSystemSourceReader()

    return TaskPilotGraph(agents=[
        IngestionAgent(reader=reader),
        ExtractionAgent(),
        DeduplicationAgent(),
        PrioritizationAgent(),
        PlanningAgent(),
    ])


def main() -> None:
    print("TaskPilot AI — generating your daily plan...\n")

    graph = _build_graph()
    state = graph.run(WorkflowState())

    source_summary = list(state.raw_inputs.keys()) or list(
        {t.source for t in state.extracted_tasks}
    )
    print(f"Sources loaded : {source_summary}")
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
    for trace in state.traces:
        print(f"  [{trace.step}] {trace.detail}")


if __name__ == "__main__":
    main()
