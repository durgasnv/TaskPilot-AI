"""CLI entry point — runs the full TaskPilot pipeline and prints the daily plan."""

import sys

from taskpilot_ai.agents.specialists import (
    DeduplicationAgent,
    ExtractionAgent,
    IngestionAgent,
    PlanningAgent,
    PrioritizationAgent,
)
from taskpilot_ai.orchestration.graph import TaskPilotGraph
from taskpilot_ai.orchestration.state import WorkflowState
from taskpilot_ai.tools.source_reader import NormalizerSourceReader


def _build_graph() -> TaskPilotGraph:
    try:
        from src.pipeline.normalizer import normalize_all_sources  # noqa: F401
        reader = NormalizerSourceReader()
    except ImportError:
        from taskpilot_ai.tools.source_reader import FileSystemSourceReader
        reader = FileSystemSourceReader()

    from taskpilot_ai.analytics import TFIDFVectorDeduplicator, ScoringPrioritizer

    return TaskPilotGraph(agents=[
        IngestionAgent(reader=reader),
        ExtractionAgent(),
        DeduplicationAgent(engine=TFIDFVectorDeduplicator(threshold=0.85)),
        PrioritizationAgent(engine=ScoringPrioritizer()),
        PlanningAgent(),
    ])


def main() -> None:
    chat_mode = "--chat" in sys.argv

    print("TaskPilot AI — generating your daily plan...\n")

    graph = _build_graph()
    state = graph.run(WorkflowState())

    source_summary = list(state.raw_inputs.keys()) or sorted(
        {str(t.source) for t in state.extracted_tasks}
    )
    extracted = len(state.extracted_tasks)
    deduped = len(state.deduplicated_tasks)
    removed = extracted - deduped

    print(f"Sources loaded : {source_summary}")
    print(f"Tasks extracted: {extracted}")
    print(f"After dedup    : {deduped} ({removed} duplicates merged)")
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
    if state.ranked_tasks:
        print("── Top 5 Priority Rationale ────────────────────")
        for t in state.ranked_tasks[:5]:
            print(f"  [{t.severity}] {t.title[:60]}")
            print(f"    Score: {t.priority_score} | {t.priority_rationale}")
        print()

    if chat_mode:
        from taskpilot_ai.chat import run_chat
        run_chat(state)
    else:
        print("Tip: run with --chat to ask questions about your tasks.")
        print()

    print(f"Execution traces ({len(state.traces)}):")
    for trace in state.traces:
        print(f"  [{trace.step}] {trace.detail}")


if __name__ == "__main__":
    main()
