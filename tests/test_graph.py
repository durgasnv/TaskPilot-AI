import unittest

from taskpilot_ai.orchestration.graph import TaskPilotGraph
from taskpilot_ai.orchestration.state import WorkflowState


class TaskPilotGraphTests(unittest.TestCase):
    def test_default_graph_executes_full_day1_pipeline(self) -> None:
        state = TaskPilotGraph().run(WorkflowState())

        self.assertEqual(
            [trace.step for trace in state.traces],
            [
                "ingestion",
                "extraction",
                "deduplication",
                "prioritization",
                "planning",
            ],
        )


if __name__ == "__main__":
    unittest.main()
