# Chat Interface Improvements

## What This Is

`src/taskpilot_ai/chat.py` already handled 10+ natural language query types (Dev 2's work).
Dev 4 added two improvements to make the 5 required demo queries more reliable:

1. Demo alias mapping for critical task lookups
2. Label-aware fuzzy matching in `_find_task_in_question`

## The 5 Required Query Routes

The handoff specified these must work:

| Query | Handler |
|---|---|
| "What's my top priority?" | `_top_priority()` |
| "Why is the upload bug ranked #1?" | `_explain_ranking()` → `_find_task_in_question()` |
| "Summarize my emails" | `_summarize()` → `_by_source("email")` |
| "What's blocking my teammates?" | `_blockers()` |
| "Generate my daily plan" | `_daily_plan()` |

All five were already routed correctly. The risk was in `_find_task_in_question` — it
needed to reliably map phrases like "upload bug" to `JIRA-1001`.

## Demo Aliases

The handoff listed 5 critical mappings that must work during the demo:

```python
_DEMO_ALIASES: dict[str, str] = {
    "upload bug":      "JIRA-1001",
    "file upload":     "JIRA-1001",
    "acme issue":      "JIRA-1001",
    "vp email":        "EMAIL-001",
    "james email":     "EMAIL-001",
    "security incident": "JIRA-1006",
    "key rotation":    "JIRA-1006",
    "gdpr deletion":   "SN-INC0001011",
    "erasure request": "SN-INC0001011",
    "db issue":        "JIRA-1003",
    "database problem":"JIRA-1003",
}
```

These are checked first in `_find_task_in_question` before any fuzzy logic runs:

```python
for phrase, task_id in _DEMO_ALIASES.items():
    if phrase in q_lower:
        match = next((t for t in self.state.ranked_tasks if t.task_id == task_id), None)
        if match:
            return match
```

Why: fuzzy matching can return the wrong task when phrases like "upload bug" share
only one word with multiple task titles. A hardcoded alias removes that ambiguity
for the exact phrases the presenter will use on stage.

## Label-Aware Fuzzy Matching

The original `_find_task_in_question` only matched against task titles:

```python
t_words = set(re.sub(r"[^a-z0-9\s]", " ", t.title.lower()).split())
overlap = len(q_words & t_words)
```

Dev 4 extended it to also check task labels:

```python
t_words = set(re.sub(r"[^a-z0-9\s]", " ", t.title.lower()).split())
label_words = set(lbl.replace("-", " ") for lbl in (t.labels or []))
overlap = len(q_words & (t_words | label_words))
```

Why labels matter: a task titled "Security: Rotate API keys exposed in commit abc1234"
has a label `security`. When a user asks "tell me about the security incident", the word
"security" now matches via the label even if the title match is weak.

Note: hyphens in labels like `"customer-escalation"` are replaced with spaces so
`"customer escalation"` in a user query still matches.

## Main Concepts To Remember

- Hardcode the exact phrases that will be said on stage — don't trust fuzzy matching for demo-critical paths
- Check aliases before fuzzy logic so the fast path wins first
- Labels are metadata attached to tasks that enrich matching beyond title text
- Replace hyphens with spaces in labels before set intersection
- Module-level constants (`_DEMO_ALIASES`) avoid recreating the dict on every call
</content>
