"""CLI entry point — runs the full TaskPilot pipeline and prints the daily plan."""

import os
import sys
from collections import Counter
from datetime import datetime, timezone

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
    from taskpilot_ai.llm.client import AnthropicLLMClient, GroqLLMClient, MockLLMClient

    if os.environ.get("GROQ_API_KEY"):
        llm = GroqLLMClient()
        print("LLM: GroqCloud (llama-3.3-70b-versatile) — free tier")
    elif os.environ.get("ANTHROPIC_API_KEY"):
        llm = AnthropicLLMClient()
        print("LLM: Anthropic (claude-opus-4-8) — paid")
    else:
        llm = MockLLMClient()
        print("LLM: Mock (no API key set)")

    return TaskPilotGraph(agents=[
        IngestionAgent(reader=reader),
        ExtractionAgent(llm=llm),
        DeduplicationAgent(engine=TFIDFVectorDeduplicator(threshold=0.85)),
        PrioritizationAgent(engine=ScoringPrioritizer()),
        PlanningAgent(),
    ])



def _format_deadline(deadline: "datetime | None", now: datetime) -> str:
    if not deadline:
        return "no deadline"
    dl = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    hours = (dl - now).total_seconds() / 3600
    if hours < 0:
        return f"OVERDUE ({abs(int(hours))}h ago)"
    if dl.date() == now.date():
        return f"TODAY {dl.strftime('%H:%M UTC')} ({int(hours)}h remaining)"
    return f"{dl.strftime('%b %d %H:%M UTC')} ({int(hours)}h remaining)"


def _print_daily_plan(state: "WorkflowState") -> None:
    now = datetime.now(timezone.utc)
    day_str = now.strftime("%A, %B %d, %Y")
    print(f"\n=== TaskPilot Daily Plan — {day_str} ===\n")

    if not state.daily_plan:
        print("  (no tasks — check source data)\n")
        return

    task_map = {t.title: t for t in state.ranked_tasks}
    for i, title in enumerate(state.daily_plan, 1):
        task = task_map.get(title)
        sev = f"[{task.severity}]" if task and task.severity else ""
        print(f"#{i} {sev} {title}")
        if task:
            src = str(task.source).capitalize()
            due = _format_deadline(task.deadline, now)
            print(f"   Source: {src} | Due: {due}")
            if task.priority_rationale:
                print(f"   Why: {task.priority_rationale}")
        print()

    # Alert section: blocked tasks + overloaded assignees
    alerts: list[str] = []
    blocked = [t for t in state.ranked_tasks if t.blocked_by]
    for t in blocked[:3]:
        alerts.append(f"{t.title[:55]} — blocked by: {', '.join(t.blocked_by)}")
    assignee_p2: Counter = Counter(
        t.assignee for t in state.ranked_tasks
        if t.assignee and str(t.severity) == "P2"
    )
    for assignee, count in assignee_p2.most_common(3):
        if count >= 2:
            alerts.append(f"{assignee} is overloaded ({count} x P2). Review task redistribution.")

    if alerts:
        print("--- ALERT ---")
        for alert in alerts:
            print(alert)
        print()


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

    _print_daily_plan(state)

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
