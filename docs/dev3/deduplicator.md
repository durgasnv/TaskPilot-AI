# TFIDFVectorDeduplicator — Algorithm & Design

**File:** `src/taskpilot_ai/analytics/deduplicator.py`  
**Implements:** `VectorDeduplicatorProtocol` from `src/taskpilot_ai/interfaces/protocols.py`

---

## Problem

65 tasks are ingested from 4 sources (Jira, ServiceNow, Email, Meetings). Many describe
the same real-world incident with different vocabulary:

- `JIRA-1001`: "Fix file upload timeout on large attachments"
- `SN-INC0001001`: "Production file upload completely broken for ACME Corp tenant"
- `EMAIL-001`: "URGENT: ACME Corp file upload completely down — VP escalation"

All three refer to the same P1 incident. They must be merged into one canonical task.

---

## Algorithm

### Step 1: Build embedding text per task

```python
embedding_text = title + description[:500] + labels + business_impact
```

Truncating description to 500 chars avoids noise from long transcript texts.

### Step 2: Tokenize and build TF-IDF matrix

- Remove stopwords and short tokens (len <= 2)
- Compute term-frequency per document, normalise by doc length
- Compute smoothed IDF: `log((N+1)/(df+1)) + 1`
- L2-normalise each row → cosine similarity = dot product

### Step 3: Three merge conditions (any one triggers a merge)

| Condition | TF-IDF threshold | Title keyword overlap | Use case |
|---|---|---|---|
| 1 (near-exact) | >= 0.85 | any | Near-identical text in two sources |
| 2 (same-issue) | >= 0.15 | >= 2 shared title keywords | Cross-source, different wording |
| 3 (high-sim) | >= 0.50 | >= 1 shared title keyword | Security incidents with synonyms |

Condition 2 is the key one for the ACME Corp demo case: "file" + "upload" overlap in
titles across JIRA, ServiceNow, and Email, even though descriptions differ.

### Step 4: Choose canonical, merge fields

Priority order: `jira (0) > servicenow (1) > email (2) > transcript (3)`

The lower-priority source gets `duplicate_of = canonical.task_id` and is dropped
from the output. The canonical task is enriched in-place:
- `labels` merged (deduped)
- `business_impact` appended (up to 300 chars)
- `deadline` taken from duplicate if canonical has none
- `blocks` list merged

---

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `threshold` | 0.85 | Min TF-IDF cosine sim for condition 1 |
| `tfidf_min_for_boost` | 0.15 | Min TF-IDF for condition 2 |
| `keyword_min_overlap` | 2 | Min shared title keywords for condition 2 |

---

## Demo Results (65 tasks from live data)

```
Tasks extracted : 65
After dedup     : 36 (29 merged)

Must-pass ACME cluster:
  SN-INC0001001 -> JIRA-1001  ✓
  EMAIL-001     -> JIRA-1001  ✓
  EMAIL-002     -> JIRA-1001  ✓
  MTG-002       -> JIRA-1001  ✓

Ground truth recall: 80% (8/10 documented pairs found)
```

---

## Integration

```python
from taskpilot_ai.analytics import TFIDFVectorDeduplicator
from taskpilot_ai.agents.specialists import DeduplicationAgent

agent = DeduplicationAgent(engine=TFIDFVectorDeduplicator(threshold=0.85))
state = agent.run(state)
# state.deduplicated_tasks now has merged unique tasks
```

---

## Upgrade Path

If `sentence-transformers` or `chromadb` becomes available, replace this engine
with one that uses real dense embeddings. The `VectorDeduplicatorProtocol` interface
requires only a single `deduplicate(tasks) -> list[UnifiedTask]` method:

```python
class ChromaDBDeduplicator:
    def deduplicate(self, tasks):
        # embed with sentence-transformers, query chromadb for similar vectors
        ...
```

Then swap in `DeduplicationAgent(engine=ChromaDBDeduplicator())`.
