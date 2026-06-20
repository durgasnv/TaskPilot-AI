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


def _parse_args() -> dict:
    args = sys.argv[1:]
    return {
        "chat": "--chat" in args,
        "monitor": "--monitor" in args,
        "slack_webhook": next(
            (args[i + 1] for i, a in enumerate(args) if a == "--slack-webhook" and i + 1 < len(args)),
            None,
        ),
    }


def main() -> None:
    opts = _parse_args()

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

    if opts["chat"]:
        from taskpilot_ai.chat import run_chat
        run_chat(state)
    elif opts["monitor"]:
        _start_monitor(graph, opts["slack_webhook"])
    else:
        print("Tip: run with --chat to ask questions, --monitor to watch for P1 injections.")
        print()

    if not opts["monitor"]:
        print(f"Execution traces ({len(state.traces)}):")
        for trace in state.traces:
            print(f"  [{trace.step}] {trace.detail}")


def _start_monitor(graph: "TaskPilotGraph", slack_webhook: str | None) -> None:
    from taskpilot_ai.events.monitor import FileDropMonitor
    from taskpilot_ai.interfaces.notifiers import build_notifier

    notifier = build_notifier(slack_webhook)
    monitor = FileDropMonitor(notifier=notifier)

    print("── P1 Monitor active ───────────────────────────")
    print("  Watching data/injected/ for new files (Ctrl+C to stop).\n")

    try:
        monitor.start(graph_runner=graph.run)
    except KeyboardInterrupt:
        monitor.stop()
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
