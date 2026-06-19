# Dev 1 -> Dev 3 Handoff: Analytics & Math Logic

**To:** Dev 3 (Analytics, Embedding Dedup, Prioritization Lead)  
**From:** Dev 1 (Data Pipeline & Privacy Lead)  
**Branch:** `dev1-data-foundation`

---

## What Dev 1 Has Delivered for You

### 1. The Pydantic Schema (your source of truth)

```python
from src.schemas.unified_task import UnifiedTask, Severity, TaskStatus, TaskSource
```

Import this. Do not redefine these types. Your Pydantic validators must reference `UnifiedTask` directly.

### 2. 65 normalized tasks ready for embedding

```python
from src.pipeline.normalizer import normalize_all_sources

result = normalize_all_sources()
tasks = result.tasks  # List[UnifiedTask], all scrubbed
```

### 3. Ground truth duplicates for accuracy validation

```python
import json
from src.utils.file_loader import TEST_DIR

with (TEST_DIR / "ground_truth_duplicates.json").open() as f:
    gt = json.load(f)

pairs = gt["duplicate_pairs"]       # 12 known duplicate pairs
threshold = gt["_meta"]["similarity_threshold"]  # 0.85
target_accuracy = gt["_meta"]["target_accuracy"] # ">=90% precision and recall"
```

### 4. Expected prioritization output for engine validation

```python
with (TEST_DIR / "prioritization_test_data.json").open() as f:
    pt = json.load(f)

expected_top_10 = pt["expected_top_10_ranking"]
scoring_formula = pt["_meta"]["scoring_formula"]
severity_weights = pt["_meta"]["severity_weights"]  # P1=1.0, P2=0.7, P3=0.4, P4=0.1
deadline_bands = pt["_meta"]["deadline_urgency_bands"]
business_multipliers = pt["_meta"]["business_impact_multipliers"]
```

---

## Fields to Use for Embedding (Deduplication)

Concatenate these fields per task to build the embedding input string:

```python
def build_embedding_text(task: UnifiedTask) -> str:
    parts = [task.title]
    if task.description:
        parts.append(task.description[:500])  # truncate for embedding efficiency
    if task.labels:
        parts.append(" ".join(task.labels))
    if task.business_impact:
        parts.append(task.business_impact)
    return " ".join(parts)
```

**Do not include** `task.raw_text` in embeddings — it is too long and contains transcript noise. Use `description` instead.

---

## Fields to Use for Prioritization Scoring

```python
task.deadline         # datetime | None — compute hours_until_deadline from now
task.severity         # "P1" | "P2" | "P3" | "P4" | None
task.status           # "blocked" tasks get a -0.15 penalty on dependency_impact
task.blocks           # list of task_ids — count of downstream dependents
task.blocked_by       # non-empty = task is currently blocked
task.business_impact  # string — search for keywords to assign business_impact_multiplier
task.labels           # search for "vp-escalation", "customer-escalation", "legal", etc.
```

### Scoring Formula

```
priority_score =
    (deadline_urgency   * 0.40)
  + (severity_weight    * 0.35)
  + (dependency_impact  * 0.15)
  + (business_impact_m  * 0.10)
```

### Deadline Urgency Bands (reference: 2026-06-19T09:00:00Z)

| hours_until_deadline | urgency |
|---|---|
| < 0 (overdue) | 1.0 |
| 0 – 4 h | 1.0 |
| 4 – 24 h | 0.9 |
| 24 – 48 h | 0.75 |
| 48 h – 1 week | 0.5 |
| > 1 week or None | 0.2 |

### Business Impact Keyword Multipliers

Scan `task.business_impact` and `task.labels`:

| Keyword | Multiplier |
|---|---|
| revenue_loss, $, payment down | 1.5 |
| gdpr, legal, compliance, audit | 1.4 |
| vp-escalation, executive | 1.3 |
| customer-escalation, churn | 1.2 |
| (none of the above) | 1.0 |

---

## Known Duplicate Pairs — The Must-Pass Demo Case

The dedup engine MUST merge these (they all refer to the ACME Corp file upload P1):

| task_id | Source |
|---|---|
| `JIRA-1001` | Jira |
| `SN-INC0001001` | ServiceNow |
| `EMAIL-001` | Email (VP escalation) |
| `EMAIL-002` | Email (customer escalation from ACME) |

After merging, one canonical `UnifiedTask` should have:
- `task_id = "JIRA-1001"` (canonical)
- `duplicate_of` set to `"JIRA-1001"` on the three merged records
- Combined `labels` from all sources
- `business_impact` enriched from the email's dollar figure

---

## Extracted-Only Tasks (no Jira ID)

16 tasks in the ground truth are sourced ONLY from emails/meetings with no Jira counterpart. These MUST appear in your ranked output. Do not filter tasks simply because `source == "email"` or `source == "transcript"`.

Highest-priority extracted-only task (must appear in top 5):
- Source: `EMAIL-001`, `EMAIL-005`, `MTG-002`
- Content: "Send RCA document to VP James by 08:00 today" — OVERDUE, VP-directed

---

## Prioritization Output Contract

For each ranked task, produce:
```python
task.priority_score     # float 0.0–1.0
task.priority_rationale # string: "P1 severity + VP escalation + deadline in 3 hours (SLA expires 12:00 UTC)"
```

The rationale string MUST include:
1. Severity label
2. Deadline in human-readable form (not ISO timestamp)
3. Business impact keyword if applicable
4. Dependency note if applicable (e.g. "Unblocks JIRA-1003 (P1)")

---

## Edge Cases to Handle

See `data/test/prioritization_test_data.json` → `scoring_edge_cases`:

1. Blocked P1 vs unblocked P2 — unblocked P2 that unblocks the P1 ranks higher
2. Extracted email task with no Jira ID — must appear in ranked list
3. Score tie — tiebreaker: closest deadline > highest severity > most blocks > alphabetical task_id
4. `status == "resolved"` or `"closed"` — exclude from ranked output
5. `deadline == None` — apply 0.2 urgency weight (do not exclude)
