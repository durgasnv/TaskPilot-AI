# Dev 1 -> Dev 2 Handoff: Agent Architecture

**To:** Dev 2 (Agent Architecture & ReAct Loop Lead)  
**From:** Dev 1 (Data Pipeline & Privacy Lead)  
**Branch:** `dev1-data-foundation`

---

## What Dev 1 Has Delivered

Your agent framework has a ready-to-use data pipeline. You do not need to write any file I/O, JSON parsing, or PII scrubbing — it is all done.

### Entry Point (use this)

```python
from src.pipeline.normalizer import normalize_all_sources
from src.schemas.unified_task import UnifiedTask, TaskSource, Severity, TaskStatus

# One call. Returns all 65 tasks from all 4 sources, PII-scrubbed.
result = normalize_all_sources()

tasks: list[UnifiedTask] = result.tasks
print(f"Loaded {result.total} tasks from {result.source_counts}")
# Output: Loaded 65 tasks from {'jira': 22, 'servicenow': 15, 'email': 21, 'transcript': 6, 'injected': 1}
```

### What Each Task Looks Like

```python
task = tasks[0]

task.task_id          # "JIRA-1001"
task.source           # "jira"
task.source_id        # "JIRA-1001"
task.title            # "Fix file upload timeout on large attachments (>50 MB)"
task.description      # Full PII-scrubbed text
task.severity         # "P1"
task.status           # "open"
task.deadline         # datetime(2026, 6, 20, 17, 0, tzinfo=timezone.utc)
task.assignee         # "dev_alice"
task.blocks           # ["JIRA-1012"]
task.blocked_by       # []
task.labels           # ["upload", "timeout", "customer-escalation", "vp-escalation"]
task.business_impact  # "ACME Corp ($2M ARR) threatening churn. VP of Engineering alerted."
task.extracted        # False  (True = LLM-extracted from unstructured text)
task.raw_text         # None for Jira/SN; populated for emails and meeting transcripts
```

---

## Your Agent's Tool Interface

Your Ingestion Agent should call `normalize_all_sources()` as its primary "load data" tool. Here is a suggested tool wrapper for the ReAct loop:

```python
def tool_load_all_tasks() -> dict:
    """
    Tool: Load all tasks from all data sources.
    Returns a JSON-serialisable dict with tasks and source stats.
    """
    from src.pipeline.normalizer import normalize_all_sources
    result = normalize_all_sources()
    return {
        "total": result.total,
        "source_counts": result.source_counts,
        "tasks": [t.model_dump(mode="json") for t in result.tasks],
        "errors": result.errors,
    }
```

---

## Structured vs. Unstructured Tasks — How to Split

Your Extraction Agent needs to distinguish:

| Condition | Task type | What to do |
|---|---|---|
| `task.extracted == False` and `task.raw_text is None` | Structured (Jira/SN) | Pass directly to dedup and prioritization — no LLM extraction needed |
| `task.extracted == True` or `task.raw_text is not None` | Unstructured (Email/Transcript) | Route to Extraction Agent: send `task.raw_text` to LLM to pull out hidden action items |

**Filter pattern:**
```python
structured = [t for t in tasks if t.raw_text is None]
needs_extraction = [t for t in tasks if t.raw_text is not None]
```

---

## Key Tasks for Demo Scenario

These task_ids are required for the mandatory demo flow. Make sure your agent can locate them by ID:

| task_id | Why it matters |
|---|---|
| `JIRA-1001` | Upload bug — must be in top 3. VP + customer escalation. |
| `SN-INC0001001` | Same issue as JIRA-1001 — must be detected as duplicate |
| `EMAIL-001` | VP escalation email referencing JIRA-1001 — hidden action items in raw_text |
| `EMAIL-002` | ACME Corp customer email — same issue |
| `SN-INC0001011` | GDPR legal deadline TODAY — must rank #1 or #2 |
| `JIRA-1006` | Security credential rotation — noon deadline TODAY |
| `INJECTED-INC0001016` | Dropped during demo — must trigger re-prioritization within 10 seconds |

---

## Injected P1 Detection

Dev 4 watches `data/injected/` for new files. When detected, it calls back into your agent to trigger re-prioritization. Your agent should:

1. Accept a "new task injected" signal from Dev 4
2. Call `normalize_all_sources()` again (it auto-picks up injected files)
3. Re-run the prioritization engine
4. Push the new top-3 list back to Dev 4 for display

---

## What Not to Do

- **Do NOT** call `scrub_text()` yourself on data from `normalize_all_sources()` — it is already scrubbed.
- **Do NOT** read the raw JSON files directly — always use the parsers.
- **Do NOT** mutate `UnifiedTask` objects — treat them as immutable input. Create new objects if the dedup/prioritization engine needs to add fields.
- **Do NOT** use `task.assignee` or `task.reporter` for display in LLM prompts — they are role aliases, not full names. They are safe, but keep them as-is.
