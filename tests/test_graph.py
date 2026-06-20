import unittest
from pathlib import Path
from unittest.mock import MagicMock

from taskpilot_ai.agents.specialists import (
    DeduplicationAgent,
    ExtractionAgent,
    IngestionAgent,
    PlanningAgent,
    PrioritizationAgent,
)
from taskpilot_ai.config import AppConfig, SourceConfig
from taskpilot_ai.events.monitor import FileDropMonitor
from taskpilot_ai.interfaces.protocols import (
    NotifierProtocol,
    PrioritizerProtocol,
    ScrubberProtocol,
    VectorDeduplicatorProtocol,
)
from taskpilot_ai.llm.client import MockLLMClient
from taskpilot_ai.models import FileSource, SourceDocument
from taskpilot_ai.orchestration.graph import TaskPilotGraph
from taskpilot_ai.orchestration.state import WorkflowState
from taskpilot_ai.prompts.extraction import build_react_user_prompt
from taskpilot_ai.tools.source_reader import FileSystemSourceReader
from taskpilot_ai.unified_task import Severity, TaskSource, UnifiedTask


def _graph_with_missing_sources() -> TaskPilotGraph:
    missing_config = AppConfig(
        sources=[
            SourceConfig(name="jira", path="data/nonexistent_jira.json"),
            SourceConfig(name="servicenow", path="data/nonexistent_sn.json"),
        ]
    )
    return TaskPilotGraph(agents=[
        IngestionAgent(config=missing_config),
        ExtractionAgent(),
        DeduplicationAgent(),
        PrioritizationAgent(),
        PlanningAgent(),
    ])


class PipelineTests(unittest.TestCase):

    def test_default_graph_runs_all_five_agents(self) -> None:
        state = TaskPilotGraph().run(WorkflowState())
        trace_steps = [t.step for t in state.traces]
        for step in ("ingestion", "extraction", "deduplication", "prioritization", "planning"):
            self.assertIn(step, trace_steps)

    def test_missing_source_files_do_not_crash_graph(self) -> None:
        state = _graph_with_missing_sources().run(WorkflowState())
        self.assertEqual(state.raw_inputs, {})
        self.assertTrue(
            any("Skipped source" in t.detail for t in state.traces if t.step == "ingestion")
        )

    def test_extraction_produces_unified_task_objects(self) -> None:
        state = TaskPilotGraph().run(WorkflowState())
        self.assertGreater(len(state.extracted_tasks), 0)
        for task in state.extracted_tasks:
            self.assertIsInstance(task, UnifiedTask)
            self.assertTrue(task.task_id.strip())
            self.assertTrue(task.title.strip())

    def test_extraction_covers_all_four_sources(self) -> None:
        state = TaskPilotGraph().run(WorkflowState())
        sources_seen = {t.source for t in state.extracted_tasks}
        self.assertIn(TaskSource.JIRA, sources_seen)
        self.assertIn(TaskSource.SERVICENOW, sources_seen)
        self.assertIn(TaskSource.EMAIL, sources_seen)
        self.assertIn(TaskSource.TRANSCRIPT, sources_seen)

    def test_prioritization_sets_score_and_rationale(self) -> None:
        state = TaskPilotGraph().run(WorkflowState())
        for task in state.ranked_tasks:
            self.assertIsNotNone(task.priority_score)
            self.assertIsNotNone(task.priority_rationale)

    def test_daily_plan_matches_ranked_task_titles(self) -> None:
        state = TaskPilotGraph().run(WorkflowState())
        expected = [t.title for t in state.ranked_tasks]
        self.assertEqual(state.daily_plan, expected)

    def test_emergency_mode_sorts_p1_tasks_to_top(self) -> None:
        state = WorkflowState(emergency_mode=True)
        state = TaskPilotGraph().run(state)
        if state.ranked_tasks:
            self.assertEqual(state.ranked_tasks[0].severity, Severity.P1)

    def test_react_prompt_contains_source_and_content(self) -> None:
        prompt = build_react_user_prompt(
            SourceDocument(
                source=FileSource.OUTLOOK,
                content="Please fix the payment bug before Friday.",
                location="data/raw/outlook_inbox.json",
            )
        )
        self.assertIn("Source: outlook", prompt)
        self.assertIn("Action", prompt)
        self.assertIn("Please fix the payment bug before Friday.", prompt)

    def test_reader_retries_and_reports_missing_file(self) -> None:
        result = FileSystemSourceReader().read(
            FileSource.JIRA, "data/nonexistent.json", retries=1
        )
        self.assertIsNone(result.document)
        self.assertIn("Missing source file", result.error or "")

    def test_mock_llm_returns_content_for_each_source(self) -> None:
        llm = MockLLMClient()
        for source_key in ("jira", "servicenow", "outlook", "meeting_notes"):
            response = llm.complete("system", f"Source: {source_key}\nsome content")
            self.assertIn("task_id", response.content)

    def test_deduplication_engine_injection(self) -> None:
        mock_engine = MagicMock(spec=VectorDeduplicatorProtocol)
        mock_engine.deduplicate.return_value = []
        agent = DeduplicationAgent(engine=mock_engine)
        state = WorkflowState(extracted_tasks=[
            UnifiedTask(task_id="T1", source=TaskSource.JIRA, source_id="T1", title="Task 1")
        ])
        result = agent.run(state)
        mock_engine.deduplicate.assert_called_once()
        self.assertEqual(result.deduplicated_tasks, [])

    def test_prioritization_engine_injection(self) -> None:
        ranked = [UnifiedTask(
            task_id="T1", source=TaskSource.JIRA, source_id="T1",
            title="T", priority_score=9.5, priority_rationale="High urgency."
        )]
        mock_engine = MagicMock(spec=PrioritizerProtocol)
        mock_engine.rank.return_value = ranked
        agent = PrioritizationAgent(engine=mock_engine)
        state = WorkflowState(deduplicated_tasks=[
            UnifiedTask(task_id="T1", source=TaskSource.JIRA, source_id="T1", title="T")
        ])
        result = agent.run(state)
        mock_engine.rank.assert_called_once()
        self.assertEqual(result.ranked_tasks[0].priority_score, 9.5)

    def test_protocols_are_runtime_checkable(self) -> None:
        class GoodScrubber:
            def scrub(self, document: SourceDocument) -> SourceDocument:
                return document

        class BadScrubber:
            pass

        self.assertIsInstance(GoodScrubber(), ScrubberProtocol)
        self.assertNotIsInstance(BadScrubber(), ScrubberProtocol)

    def test_event_monitor_detects_new_file(self) -> None:
        import tempfile
        calls: list[str] = []

        class CapturingNotifier:
            def notify(self, message: str, channel: str = "cli") -> None:
                calls.append(message)

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FileDropMonitor(
                watch_dir=Path(tmpdir),
                poll_interval=0,
                notifier=CapturingNotifier(),
            )
            # Seed baseline (empty dir), then drop a file, then run one scan cycle.
            monitor.seed()
            (Path(tmpdir) / "p1_emergency.json").write_text('{"incident": {}}')
            monitor.start(max_iterations=1)

        self.assertEqual(len(calls), 1)
        self.assertIn("p1_emergency.json", calls[0])


if __name__ == "__main__":
    unittest.main()
