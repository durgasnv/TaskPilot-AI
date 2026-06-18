import unittest

from taskpilot_ai.orchestration.graph import TaskPilotGraph
from taskpilot_ai.orchestration.state import WorkflowState
from taskpilot_ai.prompts.extraction import build_react_user_prompt
from taskpilot_ai.tools.source_reader import FileSystemSourceReader
from taskpilot_ai.models import SourceDocument, TaskSource


class TaskPilotGraphTests(unittest.TestCase):
    def test_default_graph_executes_full_day1_pipeline(self) -> None:
        state = TaskPilotGraph().run(WorkflowState())

        trace_steps = [trace.step for trace in state.traces]

        self.assertGreaterEqual(trace_steps.count("ingestion"), 1)
        self.assertIn("extraction", trace_steps)
        self.assertIn("deduplication", trace_steps)
        self.assertIn("prioritization", trace_steps)
        self.assertIn("planning", trace_steps)

    def test_missing_source_files_do_not_break_graph(self) -> None:
        state = TaskPilotGraph().run(WorkflowState())

        self.assertEqual(state.raw_inputs, {})
        self.assertTrue(
            any("Skipped source" in trace.detail for trace in state.traces if trace.step == "ingestion")
        )

    def test_react_prompt_contains_grounding_and_source_context(self) -> None:
        prompt = build_react_user_prompt(
            SourceDocument(
                source=TaskSource.OUTLOOK,
                content="Please fix the payment bug before Friday.",
                location="data/outlook.txt",
            )
        )

        self.assertIn("Source: outlook", prompt)
        self.assertIn("Action", prompt)
        self.assertIn("Please fix the payment bug before Friday.", prompt)

    def test_reader_reports_missing_file(self) -> None:
        result = FileSystemSourceReader().read(TaskSource.JIRA, "data/missing.json")

        self.assertIsNone(result.document)
        self.assertIn("Missing source file", result.error or "")


if __name__ == "__main__":
    unittest.main()
