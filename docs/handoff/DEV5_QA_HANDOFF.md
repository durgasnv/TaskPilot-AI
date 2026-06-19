# Dev 1 -> Dev 5 Handoff: QA Automation & Metrics

**To:** Dev 5 (QA Automation & Release Lead)  
**From:** Dev 1 (Data Pipeline & Privacy Lead)  
**Branch:** `dev1-data-foundation`

---

## Dev 1 Baseline — Run This First

```bash
python tests/test_pipeline.py
```

Expected output:
```
TOTAL: 73 passed, 0 failed out of 73 checks
All checks passed. Dev 1 pipeline is ready.
```

If any check fails, **stop and notify Dev 1** — the pipeline foundation is broken and downstream tests will give false results.

---

## What Dev 1 Has Provided for Your Harness

### Ground Truth File

```python
import json
from src.utils.file_loader import TEST_DIR

with (TEST_DIR / "ground_truth_duplicates.json").open() as f:
    gt = json.load(f)

duplicate_pairs = gt["duplicate_pairs"]       # 12 known pairs
extracted_tasks = gt["extracted_only_tasks"]["items"]  # 16 email/transcript-only tasks
target_accuracy = ">=90% precision and recall"
threshold = 0.85                              # similarity threshold
```

### Prioritization Expected Output

```python
with (TEST_DIR / "prioritization_test_data.json").open() as f:
    pt = json.load(f)

expected_ranking = pt["expected_top_10_ranking"]   # list of {rank, task_id, rationale, score_range}
edge_cases = pt["scoring_edge_cases"]
demo_validation = pt["demo_scenario_validation"]
```

---

## Metrics to Measure

### 1. Deduplication Accuracy

```python
def compute_dedup_metrics(predicted_merged_pairs: list, ground_truth_pairs: list) -> dict:
    gt_set = {(p["canonical_task"], p["duplicate_task"]) for p in ground_truth_pairs}
    pred_set = set(predicted_merged_pairs)

    tp = len(gt_set & pred_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {"precision": precision, "recall": recall, "f1": f1}

# Target: precision >= 0.90, recall >= 0.90
```

### 2. Extraction Coverage

16 tasks exist ONLY in email/meeting text. The LLM extraction agent must find them.

```python
def compute_extraction_coverage(discovered_tasks: list, expected_items: list) -> float:
    found = 0
    for expected in expected_items:
        keyword = expected["action"][:30].lower()  # first 30 chars as signal
        for task in discovered_tasks:
            if keyword in (task.title or "").lower() or keyword in (task.description or "").lower():
                found += 1
                break
    return found / len(expected_items)

# Target: >= 0.95 (95% of hidden action items discovered)
```

### 3. Prioritization Accuracy

```python
def check_top_3_ranking(actual_top_3: list[UnifiedTask], expected_ranking: list) -> dict:
    expected_top_3_ids = {e["task_id"] for e in expected_ranking[:3]}
    actual_top_3_ids = {t.task_id for t in actual_top_3}
    overlap = expected_top_3_ids & actual_top_3_ids
    return {
        "correct_in_top_3": len(overlap),
        "expected": list(expected_top_3_ids),
        "actual": list(actual_top_3_ids),
        "pass": len(overlap) >= 2,  # at least 2 of 3 must match
    }
```

### 4. End-to-End Latency

```python
import time

start = time.time()
# Run: load → extract → dedup → prioritize → plan
elapsed = time.time() - start

assert elapsed < 60, f"E2E latency {elapsed:.1f}s exceeds 60s target"
```

### 5. Hallucination Check

Every task in the output must have a traceable source:

```python
def check_no_hallucination(output_tasks: list[UnifiedTask], source_tasks: list[UnifiedTask]) -> list:
    source_ids = {t.task_id for t in source_tasks}
    phantom = [t.task_id for t in output_tasks if t.task_id not in source_ids
               and not t.task_id.startswith("INJECTED")]
    return phantom  # must be empty list

# Pass if: len(check_no_hallucination(...)) == 0
```

---

## Demo Scenario Validation Script

Run this against a live demo session:

```python
DEMO_STEPS = [
    # Step 1: Ingest
    {"check": "all 4 sources loaded", "field": "source_counts", "condition": lambda r: all(k in r for k in ["jira", "servicenow", "email", "transcript"])},
    # Step 2: Extract
    {"check": "at least 2 action items extracted from emails", "condition": lambda tasks: sum(1 for t in tasks if t.extracted and t.source == "email") >= 2},
    # Step 3: Deduplicate
    {"check": "JIRA-1001 and SN-INC0001001 merged", "condition": lambda merged_pairs: ("JIRA-1001", "SN-INC0001001") in merged_pairs},
    # Step 4: Prioritize
    {"check": "top 3 contain P1 tasks", "condition": lambda top3: all(t.severity == "P1" for t in top3)},
    # Step 5: Daily plan exists
    {"check": "daily plan has >= 5 items", "condition": lambda plan: len(plan) >= 5},
    # Step 6: Conversational query answered
    {"check": "priority_rationale non-empty for top task", "condition": lambda top: bool(top.priority_rationale)},
    # Step 7: P1 injection
    {"check": "injected task reaches rank #1 within 10 seconds", "timeout_seconds": 10},
]
```

---

## Data Counts (for your baseline)

| Source | Count | P1 tasks | Tasks with deadlines | Cross-system dups |
|---|---|---|---|---|
| Jira | 22 | 3 | 22 | 8 (paired with SN/email) |
| ServiceNow | 15 | 6 | 15 | 8 |
| Email | 21 | 9 | 21 (received_at) | 5 |
| Transcript | 6 | 1 | 6 (meeting date) | 3 (same issues) |
| **Total** | **64** | **19** | **64** | **12 pairs** |

(+1 injected P1 when `data/injected/p1_emergency.json` is present = 65 total)

---

## Key Test Scenarios to Automate

1. **Schema validation:** All 65 normalized tasks pass `UnifiedTask.model_validate()`
2. **PII scrub verification:** No raw phone/email in any task's `description` or `raw_text`
3. **Duplicate detection:** JIRA-1001 / SN-INC0001001 / EMAIL-001 / EMAIL-002 cluster merges
4. **Extraction coverage:** All 16 email/meeting-only action items discoverable
5. **Priority ordering:** GDPR / security rotation / upload bug appear in top 3
6. **Injection latency:** P1 injection triggers re-rank within 10 seconds
7. **Rationale completeness:** Every top-10 task has `priority_rationale` non-null
8. **No phantom tasks:** No output task_id that doesn't trace to a source file

---

## Backup Demo Recording Requirement

Per the hackathon risk plan: record a full demo run locally at HD resolution before the live presentation. The video must cover all 7 steps of the demo scenario above. Save as `demo_backup.mp4` in the repo root (gitignored).
