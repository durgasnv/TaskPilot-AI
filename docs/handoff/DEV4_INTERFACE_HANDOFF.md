# Dev 1 -> Dev 4 Handoff: Interface & Event System

**To:** Dev 4 (Conversational Interface & Event Poller Lead)  
**From:** Dev 1 (Data Pipeline & Privacy Lead)  
**Branch:** `dev1-data-foundation`

---

## What You Need to Know About the Data Layer

### Where Tasks Come From

```python
from src.pipeline.normalizer import normalize_all_sources

result = normalize_all_sources()
tasks = result.tasks  # 65 UnifiedTask objects
```

Call this at startup and again when a new file appears in `data/injected/`.

### Fields Your Conversational Routes Will Need

```python
task.task_id           # Primary key for lookup — e.g. "JIRA-1001"
task.title             # Display text for task names
task.severity          # "P1"/"P2"/"P3"/"P4" — show in alerts
task.deadline          # datetime — compute "due in X hours" for display
task.status            # "blocked" — show blocking notice
task.blocked_by        # list of task_ids blocking this task
task.blocks            # list of task_ids this task blocks
task.source            # "jira"/"servicenow"/"email"/"transcript" — show source badge
task.business_impact   # Show in "Why is this ranked #1?" explanation
task.priority_score    # Set by Dev 3's engine — use for ordering display
task.priority_rationale # Use verbatim in "Why?" queries — already human-readable
task.raw_text          # For "Summarize email X" queries — pass to LLM
task.extracted         # True = LLM-extracted task — show "From email" badge
```

---

## Event Poller — P1 File Drop Detection

### What to Watch

```python
WATCH_DIRECTORY = "data/injected/"   # relative to repo root
```

Use `watchdog` (Python) or `os.stat()` polling. Any new `.json` file in this directory is a P1 injection event.

### Suggested Poller Implementation

```python
import time
from pathlib import Path
from src.pipeline.normalizer import normalize_all_sources

INJECTED_DIR = Path("data/injected")
SEEN_FILES = set()

def poll_for_injected_p1(callback, interval_seconds=2):
    """
    Poll data/injected/ for new JSON files.
    Calls callback(new_task) when a new file is detected.
    """
    while True:
        current_files = set(INJECTED_DIR.glob("*.json"))
        new_files = current_files - SEEN_FILES
        for f in new_files:
            SEEN_FILES.add(f)
            # Re-run normalization — injected file is auto-picked up
            result = normalize_all_sources()
            injected_tasks = [t for t in result.tasks if "INJECTED" in t.task_id]
            for task in injected_tasks:
                callback(task)
        time.sleep(interval_seconds)
```

### What to Do When a P1 is Detected

1. Call the prioritization engine (Dev 3) to re-rank all tasks
2. Find the new task in the ranked list
3. Push the alert:

```
"NEW P1 DETECTED: {task.title}
Business impact: {task.business_impact}
SLA deadline: {format_deadline(task.deadline)}
Re-prioritizing your task list..."
```

4. Update the displayed daily plan with the new #1 task

**Max latency:** 10 seconds from file drop to visible alert (demo requirement).

---

## Required Conversational Query Routes

The interface must handle these 5 natural language queries as a minimum:

### Query 1: "What's my top priority?"
```python
# Find task with highest priority_score from Dev 3's engine
top = max(tasks, key=lambda t: t.priority_score or 0)
response = f"Your top priority is: {top.title}\n{top.priority_rationale}"
```

### Query 2: "Why is [task] ranked #1?" / "Why is the upload bug my #1?"
```python
# Map "upload bug" -> JIRA-1001 via fuzzy title match
# Return: task.priority_rationale (set by Dev 3)
response = f"{task.title} is ranked #{rank} because:\n{task.priority_rationale}"
```

### Query 3: "Summarize my emails" / "Summarize the VP's email"
```python
# For email tasks: pass task.raw_text to the LLM
# task.raw_text is already PII-scrubbed — safe to send to LLM
vp_email = next(t for t in tasks if "vp" in t.labels and t.source == "email")
# Send vp_email.raw_text to LLM: "Summarize this email in 3 bullet points: {raw_text}"
```

### Query 4: "What's blocking my teammates?" / "Who is blocked?"
```python
blocked = [t for t in tasks if t.status == "blocked"]
# For each: show task.title, task.blocked_by (list of blocker task_ids)
```

### Query 5: "Generate my daily plan" / "What should I work on today?"
```python
# Filter: exclude resolved/closed
# Sort by priority_score descending (set by Dev 3)
plan = sorted(
    [t for t in tasks if t.status not in ("resolved", "closed")],
    key=lambda t: t.priority_score or 0,
    reverse=True
)[:10]  # Top 10
```

---

## Task ID Lookup

Your NL router will need to match user utterances like "the upload bug" to `JIRA-1001`. Suggested approach: fuzzy match on `task.title` and `task.labels`.

Critical mappings for the demo:
| User says | task_id |
|---|---|
| "upload bug", "file upload", "ACME issue" | `JIRA-1001` |
| "VP's email", "James's email" | `EMAIL-001` |
| "security incident", "key rotation" | `JIRA-1006` |
| "GDPR deletion", "erasure request" | `SN-INC0001011` |
| "DB issue", "database problem" | `JIRA-1003` |

---

## Daily Plan Display Format

```
=== TaskPilot Daily Plan — Monday, June 19, 2026 ===

#1 [P1] GDPR right-to-erasure: user [EMPLOYEE_ID] — legal deadline TODAY
   Source: ServiceNow | Due: TODAY 17:00 UTC (8h remaining)
   Why: Legal compliance breach. €20M fine risk. Deadline TODAY.

#2 [P1] Security: Rotate API keys exposed in commit abc1234
   Source: Jira | Due: TODAY 12:00 UTC (3h remaining)
   Why: Active credential exposure. P1. Noon deadline.

#3 [P1] Fix file upload timeout on large attachments (>50 MB)
   Source: Jira | Due: Jun 20 17:00 UTC (32h remaining)
   Why: ACME Corp VP escalation + customer churn risk. $2M ARR.

--- ALERT ---
Carol is overloaded (3 x P2). Review task redistribution.
DBA Ivan: read replica ETA revised to Jun 19 18:00 (was today EOD).
```

---

## What NOT to Use

- **Never** read raw JSON files from `data/raw/` directly — always use `normalize_all_sources()`
- **Never** display `task.source_id` to users (internal system IDs) — use `task.task_id` and `task.title`
- **Never** send raw email body to LLM — always use `task.raw_text` (already scrubbed)
- **Never** hardcode paths to `data/injected/` as strings — use `from src.utils.file_loader import INJECTED_DIR`
