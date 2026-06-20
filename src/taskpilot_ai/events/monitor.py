"""
Event polling monitor that watches the data directory for new files.

When a new file is detected it re-runs the full orchestration graph with
emergency_mode=True so the prioritization agent can fast-path P1 tasks.
Dev4 plugs a NotifierProtocol implementation here to route alerts to Slack,
CLI, or webhooks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from taskpilot_ai.interfaces.protocols import NotifierProtocol
from taskpilot_ai.orchestration.state import WorkflowState


class _CLINotifier:
    """Default notifier: prints to stdout. Dev4 replaces with their implementation."""

    def notify(self, message: str, channel: str = "cli") -> None:
        print(f"[TASKPILOT ALERT] {message}")


@dataclass
class FileDropMonitor:
    """
    Polls a directory on a fixed interval. When a new file appears:
    1. Fires the on_new_file callback with the new Path
    2. Calls notifier.notify() with a human-readable alert
    3. Triggers the graph_runner callable to re-run orchestration

    Args:
        watch_dir:    Directory to monitor. Defaults to 'data/'.
        poll_interval: Seconds between scans. Default 5.
        notifier:     NotifierProtocol implementation. Defaults to CLI print.
        graph_runner: Callable that accepts a WorkflowState and returns one.
                      Defaults to None — callers must provide this at start().
    """

    watch_dir: Path = field(default_factory=lambda: Path("data/injected"))
    poll_interval: float = 5.0
    notifier: NotifierProtocol = field(default_factory=_CLINotifier)
    graph_runner: Callable[[WorkflowState], WorkflowState] | None = None

    _seen_files: set[Path] = field(default_factory=set, init=False, repr=False)
    _seeded: bool = field(default=False, init=False, repr=False)
    _running: bool = field(default=False, init=False, repr=False)

    def _scan(self) -> list[Path]:
        """Return any files in watch_dir not seen in a previous scan."""
        if not self.watch_dir.exists():
            return []
        current = set(self.watch_dir.iterdir())
        new_files = [p for p in current if p not in self._seen_files and p.is_file()]
        self._seen_files = current
        return new_files

    def _handle_new_file(self, path: Path) -> WorkflowState | None:
        """Fire alert and re-run the orchestration graph in emergency mode."""
        alert = (
            f"New file detected: '{path.name}'. "
            "Triggering emergency re-prioritization."
        )
        self.notifier.notify(alert)

        if self.graph_runner is None:
            return None

        state = WorkflowState(emergency_mode=True)
        result = self.graph_runner(state)
        return result

    def start(
        self,
        graph_runner: Callable[[WorkflowState], WorkflowState] | None = None,
        max_iterations: int | None = None,
    ) -> None:
        """
        Begin polling. Blocks the calling thread.

        Args:
            graph_runner:   Optional override for self.graph_runner.
            max_iterations: Stop after this many poll cycles (useful in tests).
                            None means run forever.
        """
        if graph_runner is not None:
            self.graph_runner = graph_runner

        self._running = True

        # Seed only on first call so that resuming does not lose accumulated state.
        if not self._seeded:
            self.seed()

        iterations = 0
        while self._running:
            new_files = self._scan()
            for path in new_files:
                self._handle_new_file(path)

            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
            time.sleep(self.poll_interval)

    def seed(self) -> None:
        """Explicitly seed seen-files from the current directory contents.
        Call this before start() when you want a clean baseline."""
        if self.watch_dir.exists():
            self._seen_files = set(self.watch_dir.iterdir())
        self._seeded = True

    def stop(self) -> None:
        self._running = False
