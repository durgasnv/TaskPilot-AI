# Event Polling Monitor (Day 3 — Task 4)

## What This Is
`src/taskpilot_ai/events/monitor.py` implements `FileDropMonitor` — a
polling loop that watches the `data/` directory and re-runs the full
orchestration graph whenever a new file appears.

This is the Day 3 Dev2 requirement: "detect a sudden file insertion
(simulating a surprise emergency bug) and trigger a state recalculation."

## How It Works

```
FileDropMonitor.start()
  │
  ├─ Seeds _seen_files with everything already in data/   (no false alerts)
  │
  └─ Loop every poll_interval seconds:
       _scan() → finds files not in _seen_files
       for each new file:
         notifier.notify(alert_message)
         graph_runner(WorkflowState(emergency_mode=True))
```

The key detail is **seeding**: on startup the monitor records every file
already in `data/` as "already seen." Only files that appear *after* the
monitor starts trigger an alert. This prevents the existing four source
files from firing alerts on every restart.

## emergency_mode Flag
`WorkflowState` has a new field: `emergency_mode: bool = False`.

When the monitor triggers a re-run it sets `emergency_mode=True`. The
`PrioritizationAgent` (once Dev3 connects their scoring logic) will check
this flag and boost any P1 tasks to the top of the ranked list regardless
of their normal score. This implements the "mid-demo P1 injection" scenario
from the acceptance criteria.

## NotifierProtocol Hook
The monitor accepts any object that matches `NotifierProtocol`:
```python
class NotifierProtocol(Protocol):
    def notify(self, message: str, channel: str = "cli") -> None: ...
```

The default `_CLINotifier` just prints to stdout. Dev4 replaces it with
their Slack webhook or push notification implementation by passing their
class at construction:

```python
monitor = FileDropMonitor(notifier=Dev4SlackNotifier())
```

## graph_runner Callable
The monitor does not import `TaskPilotGraph` directly. Instead it accepts
any callable that takes a `WorkflowState` and returns a `WorkflowState`.
This keeps the monitor decoupled from the graph — useful for testing and
for future cases where the runner might be async or distributed.

Usage in `main.py`:
```python
from taskpilot_ai.events.monitor import FileDropMonitor
from taskpilot_ai.orchestration.graph import TaskPilotGraph

graph = TaskPilotGraph()
monitor = FileDropMonitor(poll_interval=5)
monitor.start(graph_runner=graph.run)  # blocks the thread
```

## Demo Scenario
During the hackathon demo:
1. The full pipeline runs → daily plan displayed
2. Presenter drops `data/p1_emergency.json` into the `data/` folder
3. Monitor detects it within `poll_interval` seconds
4. Alert prints: `"New file detected: 'p1_emergency.json'. Triggering emergency re-prioritization."`
5. Graph re-runs with `emergency_mode=True`
6. New ranked list is output with the P1 task at the top

## max_iterations Parameter
`start(max_iterations=N)` stops after N poll cycles. This is used in
tests so the monitor does not block the test process forever.
