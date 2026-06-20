import json
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
from taskpilot_ai.models import FileSource, SourceDocument, detect_source
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


class AdaptiveInputTests(unittest.TestCase):
    """Tests that the system handles arbitrary / unexpected file formats."""

    # ── detect_source ────────────────────────────────────────────────────────

    def test_detect_source_identifies_jira(self) -> None:
        content = json.dumps({"board": {}, "issues": [{"id": "J-1", "title": "Bug"}]})
        self.assertEqual(detect_source(content), FileSource.JIRA)

    def test_detect_source_identifies_servicenow(self) -> None:
        content = json.dumps({"records": [{"number": "INC001", "short_description": "Down"}]})
        self.assertEqual(detect_source(content), FileSource.SERVICENOW)

    def test_detect_source_identifies_servicenow_single_incident(self) -> None:
        content = json.dumps({"incident": {"number": "INC001", "short_description": "Critical outage"}})
        self.assertEqual(detect_source(content), FileSource.SERVICENOW)

    def test_detect_source_identifies_outlook(self) -> None:
        content = json.dumps({"emails": [{"id": "E1", "subject": "Bug report"}]})
        self.assertEqual(detect_source(content), FileSource.OUTLOOK)

    def test_detect_source_falls_back_to_injected_for_unknown(self) -> None:
        self.assertEqual(detect_source("not json at all"), FileSource.INJECTED)
        self.assertEqual(detect_source(json.dumps({"random": "data"})), FileSource.INJECTED)

    # ── MockLLMClient content extraction ─────────────────────────────────────

    def test_mock_llm_extracts_from_incident_wrapper(self) -> None:
        """The P1 emergency file format: {"incident": {...}} should be parsed."""
        llm = MockLLMClient()
        content = json.dumps({
            "incident": {
                "number": "INC9999",
                "short_description": "Payment gateway DOWN",
                "severity": "P1",
                "sla_due": "2026-06-20T09:00:00Z",
                "business_impact": "$10k/min revenue loss",
            }
        })
        response = llm.complete("system", f"Source: injected\nSource content:\n{content}")
        tasks = json.loads(response.content)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], "INC9999")
        self.assertIn("Payment gateway DOWN", tasks[0]["title"])
        self.assertEqual(tasks[0]["severity"], "P1")

    def test_mock_llm_extracts_from_flat_json_list(self) -> None:
        """A bare JSON array of task-like objects should each become a task."""
        llm = MockLLMClient()
        content = json.dumps([
            {"id": "T1", "title": "Fix login bug", "priority": "high"},
            {"id": "T2", "title": "Update docs", "priority": "low"},
        ])
        response = llm.complete("system", f"Source: injected\nSource content:\n{content}")
        tasks = json.loads(response.content)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["task_id"], "T1")
        self.assertEqual(tasks[0]["severity"], "P2")  # "high" → P2
        self.assertEqual(tasks[1]["severity"], "P4")  # "low" → P4

    def test_mock_llm_extracts_from_plain_text(self) -> None:
        """A plain text file (email body, .txt) becomes a single task."""
        llm = MockLLMClient()
        response = llm.complete(
            "system",
            "Source: injected\nSource content:\nFix the authentication bug before the release"
        )
        tasks = json.loads(response.content)
        self.assertEqual(len(tasks), 1)
        self.assertIn("Fix the authentication bug", tasks[0]["title"])
        self.assertEqual(tasks[0]["extracted"], True)

    def test_mock_llm_extracts_from_arbitrary_json_object(self) -> None:
        """A single JSON object with no known wrapper is treated as one task."""
        llm = MockLLMClient()
        content = json.dumps({
            "name": "Deploy hotfix",
            "urgency": "critical",
            "details": "Patch the memory leak in the worker process",
        })
        response = llm.complete("system", f"Source: injected\nSource content:\n{content}")
        tasks = json.loads(response.content)
        self.assertEqual(len(tasks), 1)
        self.assertIn("Deploy hotfix", tasks[0]["title"])
        self.assertEqual(tasks[0]["severity"], "P1")  # "critical" → P1

    # ── End-to-end: dropped file processed by full pipeline ──────────────────

    def test_event_monitor_injects_file_content_into_pipeline(self) -> None:
        """A file dropped into watch_dir should appear in raw_inputs and produce extracted tasks."""
        import tempfile
        captured: list[WorkflowState] = []

        def fake_runner(state: WorkflowState) -> WorkflowState:
            # Run extraction only so we can inspect what was injected
            state = ExtractionAgent().run(state)
            captured.append(state)
            return state

        incident = {
            "incident": {
                "number": "INC-DEMO",
                "short_description": "CRITICAL: Database unreachable",
                "severity": "P1",
                "business_impact": "All users affected",
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FileDropMonitor(watch_dir=Path(tmpdir), poll_interval=0, graph_runner=fake_runner)
            monitor.seed()
            (Path(tmpdir) / "demo_incident.json").write_text(json.dumps(incident))
            monitor.start(max_iterations=1)

        self.assertEqual(len(captured), 1)
        state = captured[0]
        self.assertTrue(state.emergency_mode)
        self.assertIn(FileSource.INJECTED.value, state.raw_inputs)
        self.assertGreater(len(state.extracted_tasks), 0)
        titles = [t.title for t in state.extracted_tasks]
        self.assertTrue(any("Database unreachable" in t for t in titles))

    def test_full_pipeline_with_injected_p1_emergency_file(self) -> None:
        """The actual data/injected/p1_emergency.json file should be extracted as a P1 task."""
        p1_file = Path("data/injected/p1_emergency.json")
        if not p1_file.exists():
            self.skipTest("data/injected/p1_emergency.json not present")

        content = p1_file.read_text(encoding="utf-8")
        state = WorkflowState(emergency_mode=True)
        state.raw_inputs[FileSource.INJECTED.value] = SourceDocument(
            source=FileSource.INJECTED,
            content=content,
            location=str(p1_file),
        )
        state = TaskPilotGraph().run(state)

        self.assertGreater(len(state.extracted_tasks), 0)
        severities = [t.severity for t in state.extracted_tasks]
        self.assertIn("P1", severities)
        # Emergency mode must put the P1 at the top of the daily plan
        self.assertEqual(state.ranked_tasks[0].severity, "P1")


if __name__ == "__main__":
    unittest.main()
