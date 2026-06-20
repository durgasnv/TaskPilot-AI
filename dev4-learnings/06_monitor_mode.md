# Monitor Mode (--monitor CLI Flag)

## What This Is

Dev 4 added a `--monitor` flag to `src/taskpilot_ai/main.py` that starts the
`FileDropMonitor` after the initial pipeline run completes.

## How to Run

```bash
# Terminal alerts only
python -m taskpilot_ai.main --monitor

# With Slack webhook
python -m taskpilot_ai.main --monitor --slack-webhook https://hooks.slack.com/services/...

# Or via environment variable
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
python -m taskpilot_ai.main --monitor
```

## Argument Parsing

A small `_parse_args()` function reads `sys.argv` directly:

```python
def _parse_args() -> dict:
    args = sys.argv[1:]
    return {
        "chat": "--chat" in args,
        "monitor": "--monitor" in args,
        "slack_webhook": next(
            (args[i + 1] for i, a in enumerate(args)
             if a == "--slack-webhook" and i + 1 < len(args)),
            None,
        ),
    }
```

Why not `argparse`: the existing code used `"--chat" in sys.argv` directly.
Keeping the same pattern avoids introducing a new module for three flags.

## The Monitor Startup Function

```python
def _start_monitor(graph, slack_webhook):
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
```

Key points:
- Imports are inside the function — they only load when `--monitor` is used
- The same `graph` object built earlier is reused as the `graph_runner`
- `KeyboardInterrupt` is caught so Ctrl+C gives a clean shutdown message

## Full Execution Flow with --monitor

```
1. python -m taskpilot_ai.main --monitor
2. Pipeline runs: ingest → extract → dedup → prioritize → plan
3. Daily plan is printed to terminal
4. Monitor starts: seeds seen-files, enters poll loop (every 5s)
5. User drops a .json file into data/injected/
6. Alert 1: "New file detected..."
7. Pipeline re-runs with emergency_mode=True
8. Alert 2: "NEW P1 DETECTED: ..."
9. Ctrl+C → "Monitor stopped."
```

## Execution Traces Suppressed in Monitor Mode

When `--monitor` is active, execution traces are not printed after the initial run:

```python
if not opts["monitor"]:
    print(f"Execution traces ({len(state.traces)}):")
    for trace in state.traces:
        print(f"  [{trace.step}] {trace.detail}")
```

Why: in monitor mode the terminal output must stay clean so P1 alerts are easy
to spot. Trace output would bury the alert in noise.

## Main Concepts To Remember

- Import heavy modules inside the function that needs them, not at the top of the file
- Reuse the already-built graph object — don't build a second one
- Always handle `KeyboardInterrupt` in long-running CLI loops for a clean exit
- Suppress verbose output (traces) in interactive/monitor modes to keep the UI readable
- `build_notifier()` centralises the CLI-vs-Slack decision — callers don't need to know
</content>
