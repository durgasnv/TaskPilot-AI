# Daily Plan Format

## What This Is

The daily plan output in `src/taskpilot_ai/main.py` was upgraded to match the format
specified in `docs/handoff/DEV4_INTERFACE_HANDOFF.md`.

## Before (Dev 2's baseline)

```
── Daily Plan ──────────────────────────────────
  1. [P1] Fix file upload timeout on large attachments (>50 MB)
  2. [P1] CRITICAL: Production payment processing DOWN
  ...
── Top 5 Priority Rationale ────────────────────
  [P1] Fix file upload timeout on large attachments (>50 MB)
    Score: 0.94 | P1 severity | due in 0h (critical)
```

## After (Dev 4's format)

```
=== TaskPilot Daily Plan — Saturday, June 20, 2026 ===

#1 [P1] Fix file upload timeout on large attachments (>50 MB)
   Source: Jira | Due: TODAY 17:00 UTC (0h remaining)
   Why: P1 severity | due in 0h (critical) | business impact: $ (×1.5)

#2 [P1] CRITICAL: Production payment processing DOWN
   Source: Servicenow | Due: OVERDUE (30h ago)
   Why: P1 severity | OVERDUE by 30h | business impact: revenue loss (×1.5)

--- ALERT ---
SRE-Team is overloaded (3 x P2). Review task redistribution.
```

## Key Functions Added

### `_format_deadline(deadline, now)`

Converts a raw UTC datetime into a human-readable string:

```python
def _format_deadline(deadline, now):
    if not deadline:
        return "no deadline"
    dl = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    hours = (dl - now).total_seconds() / 3600
    if hours < 0:
        return f"OVERDUE ({abs(int(hours))}h ago)"
    if dl.date() == now.date():
        return f"TODAY {dl.strftime('%H:%M UTC')} ({int(hours)}h remaining)"
    return f"{dl.strftime('%b %d %H:%M UTC')} ({int(hours)}h remaining)"
```

### `_print_daily_plan(state)`

Iterates `state.daily_plan` (list of titles), looks up the full `UnifiedTask` object
from `state.ranked_tasks` using a title-keyed dict, and prints each entry with
source, deadline, and rationale.

The Alert section at the bottom:
- Shows up to 3 blocked tasks with their blockers
- Detects overloaded assignees (assignees with 2+ P2 tasks) using `collections.Counter`

## Why a Dict Lookup Instead of Linear Search

```python
task_map = {t.title: t for t in state.ranked_tasks}
```

`state.daily_plan` can have up to 45 entries. Looking up each title with
`next(t for t in ranked_tasks if t.title == title)` inside a loop is O(n²).
Building a dict once and looking up in O(1) keeps the display fast even at scale.

## Main Concepts To Remember

- Always normalize datetimes to UTC before displaying time-remaining values
- Three display cases for deadlines: OVERDUE, TODAY, and future date
- Use `Counter` from `collections` to detect overloaded assignees in one pass
- A title-keyed dict avoids repeated linear scans over the task list
- Separate the display logic into its own function so `main()` stays readable
</content>
