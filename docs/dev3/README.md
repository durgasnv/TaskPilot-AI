# Dev 3 Analytics Module — Overview

**Owner:** Dev 3 (Analytics & Math Logic Lead)  
**Location:** `src/taskpilot_ai/analytics/`  
**Tests:** `tests/test_analytics.py`

---

## What This Module Does

Provides two engines that replace the keyword-based fallbacks in the pipeline:

| Engine | File | Replaces | Plugs into |
|---|---|---|---|
| `TFIDFVectorDeduplicator` | `deduplicator.py` | `_basic_keyword_dedup()` | `DeduplicationAgent(engine=...)` |
| `ScoringPrioritizer` | `prioritizer.py` | `_score_task()` fallback | `PrioritizationAgent(engine=...)` |

Both are wired in `src/taskpilot_ai/main.py`:

```python
from taskpilot_ai.analytics import TFIDFVectorDeduplicator, ScoringPrioritizer

DeduplicationAgent(engine=TFIDFVectorDeduplicator(threshold=0.85))
PrioritizationAgent(engine=ScoringPrioritizer())
```

---

## Pipeline Position

```
[Ingestion] → [Extraction] → [Deduplication ← TFIDFVectorDeduplicator]
                                   ↓
                           [Prioritization ← ScoringPrioritizer]
                                   ↓
                             [Planning → Daily Plan]
```

---

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package exports |
| `deduplicator.py` | Hybrid TF-IDF + keyword vector deduplication engine |
| `prioritizer.py` | 4-factor scoring engine with auditable rationale |

---

## Dependencies

- `numpy` (already available — used for TF-IDF matrix math)
- No `torch`, `chromadb`, or `sentence-transformers` required

---

## See Also

- [`deduplicator.md`](deduplicator.md) — algorithm walkthrough, parameters, how merge works
- [`prioritizer.md`](prioritizer.md) — scoring formula, all weight tables, rationale format
- [`DEV3_ANALYTICS_HANDOFF.md`](../handoff/DEV3_ANALYTICS_HANDOFF.md) — original spec from Dev 1
