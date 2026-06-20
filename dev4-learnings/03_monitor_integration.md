# Monitor Integration (Post-Rerank Alert)

## What This Is

`src/taskpilot_ai/events/monitor.py` already contained `FileDropMonitor` (Dev 2's work).
It detected new files and fired a generic "file detected" alert, then re-ran the graph.

Dev 4's task was to add a **second, richer alert** after the re-rank completes — showing
the new top task, its business impact, and the SLA deadline.

## What the Handoff Required

```
"NEW P1 DETECTED: {task.title}
Business impact: {task.business_impact}
SLA deadline: {format_deadline(task.deadline)}
Re-prioritizing your task list..."
```

## What Was Added

In `_handle_new_file`, after the graph re-runs:

```python
new_state = self.graph_runner(state)

if new_state and new_state.ranked_tasks:
    top = new_state.ranked_tasks[0]

    if top.deadline:
        dl_tz = top.deadline if top.deadline.tzinfo else top.deadline.replace(tzinfo=timezone.utc)
        remaining = dl_tz - datetime.now(timezone.utc)
        hrs = int(remaining.total_seconds() // 3600)
        deadline_str = f"{top.deadline.strftime('%b %d %H:%M UTC')} ({hrs}h remaining)"
    else:
        deadline_str = "no deadline set"

    self.notifier.notify(
        f"NEW P1 DETECTED: {top.title}\n"
        f"  Business impact: {top.business_impact or 'N/A'}\n"
        f"  SLA deadline: {deadline_str}\n"
        f"  Re-prioritizing complete — new #1 task above."
    )

return new_state
```

## Two-Alert Flow

When a file is dropped into `data/injected/`:

```
Alert 1 (immediate):
  "New file detected: 'p1_emergency.json'. Triggering emergency re-prioritization."

  [graph re-runs here — takes a few seconds]

Alert 2 (after re-rank):
  "NEW P1 DETECTED: Fix file upload timeout on large attachments (>50 MB)
   Business impact: ACME Corp VP escalation...
   SLA deadline: Jun 20 17:00 UTC (0h remaining)
   Re-prioritizing complete — new #1 task above."
```

This gives the demo audience two visible moments: the detection event and the result.

## How timezone-aware Datetime Works

`task.deadline` may or may not have timezone info attached (`tzinfo`).
When it does not, we attach UTC manually before computing the remaining time:

```python
dl_tz = top.deadline if top.deadline.tzinfo else top.deadline.replace(tzinfo=timezone.utc)
```

This prevents a `TypeError: can't subtract offset-naive and offset-aware datetimes`
crash at runtime — a common Python datetime pitfall.

## Main Concepts To Remember

- The monitor calls `notifier.notify()` twice: once on detection, once after re-rank
- Always make datetime objects timezone-aware before subtracting them
- Return the new state from `_handle_new_file` so callers can inspect the result
- Keep the second alert message human-readable — it is shown live during the demo
</content>
