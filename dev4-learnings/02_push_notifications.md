# Push Notifications

## What This Is

`src/taskpilot_ai/interfaces/notifiers.py` contains the two notification implementations
Dev 4 was responsible for: `CLINotifier` and `SlackNotifier`.

## CLINotifier

Prints a clearly visible bordered alert to the terminal so it stands out from normal log output.

```python
class CLINotifier:
    _BORDER = "=" * 60

    def notify(self, message: str, channel: str = "cli") -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        print(f"\n{self._BORDER}")
        print(f"  !! TASKPILOT ALERT [{ts}] !!")
        print(f"  {message}")
        print(f"{self._BORDER}\n", flush=True)
```

Why `flush=True`: alerts are time-sensitive. Without flush, the output might sit in the
buffer for seconds before appearing — unacceptable during a live demo.

## SlackNotifier

Posts a message to a Slack incoming-webhook URL using Python's standard library `urllib`.

```python
class SlackNotifier:
    def __init__(self, webhook_url: str | None = None) -> None:
        self._url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        self._cli = CLINotifier()

    def notify(self, message: str, channel: str = "cli") -> None:
        self._cli.notify(message, channel)  # always echo to terminal too

        if not self._url:
            return

        payload = json.dumps({"text": f":rotating_light: *TaskPilot Alert*\n{message}"}).encode()
        req = urllib.request.Request(self._url, data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
        except (urllib.error.URLError, OSError) as exc:
            print(f"[SlackNotifier] webhook delivery failed: {exc}")
```

Key design decisions:

1. **No new dependencies** — uses `urllib` from the standard library, not `requests`.
   This keeps `requirements.txt` clean.

2. **Always echoes to CLI** — even when a Slack webhook is configured, the alert also
   prints to the terminal. Operators watching the process always see alerts.

3. **Never raises** — webhook failures are caught and printed. The pipeline must keep
   running even if Slack is down.

4. **5-second timeout** — prevents the monitor's poll loop from hanging if the
   webhook endpoint is slow.

## Environment Variable Configuration

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../xxx"
python -m taskpilot_ai.main --monitor
```

No code changes needed to switch from CLI-only to Slack+CLI alerts.

## Main Concepts To Remember

- Use `flush=True` for time-sensitive terminal output
- Prefer stdlib (`urllib`) over third-party (`requests`) when the task is simple
- Dual output (CLI + Slack) ensures no alert is ever invisible to operators
- Catch network errors and print them — never let a broken webhook crash the main loop
- Read webhook URL from environment so the code works in any deployment without changes
</content>
