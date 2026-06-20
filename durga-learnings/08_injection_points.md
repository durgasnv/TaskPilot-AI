# Injection Points in Specialist Agents (Day 3 — Task 5)

## What This Is
`DeduplicationAgent` and `PrioritizationAgent` in `specialists.py` now
accept optional protocol implementations that Dev3 will provide.

`WorkflowState` gained one new field: `emergency_mode: bool = False`.

## How the Injection Pattern Works

```python
# Default (placeholder) — runs now, no external code needed
DeduplicationAgent()
PrioritizationAgent()

# With Dev3's implementation plugged in
DeduplicationAgent(engine=ChromaDBDeduplicator())
PrioritizationAgent(engine=ScoringEngine())
```

The agent checks `if self.engine is not None` at the top of `run()`:
- If an engine is present → delegate to it, trust its output
- If not → fall back to current placeholder logic

This means the full pipeline runs correctly at all times, with or without
Dev3's code.

## DeduplicationAgent
```
engine: VectorDeduplicatorProtocol | None = None
```
When Dev3 provides their ChromaDB/FAISS implementation:
- `engine.deduplicate(state.extracted_tasks)` is called
- The returned list (shorter, with duplicates merged) is written to
  `state.deduplicated_tasks`
- A trace entry records how many tasks remain after dedup

## PrioritizationAgent
```
engine: PrioritizerProtocol | None = None
```
When Dev3 provides their scoring formula:
- `engine.rank(state.deduplicated_tasks)` is called
- The returned `list[RankedTask]` (each with a float score + rationale
  string) is written to `state.ranked_tasks`

### Emergency Mode Sort
Both the engine path and the placeholder path check `state.emergency_mode`.
If `True`, the ranked list is re-sorted so all P1-severity tasks appear
first, regardless of score. This implements the mid-demo P1 injection
scenario without requiring Dev3's engine to know about emergency mode.

## WorkflowState.scrubbed_inputs Type Fix
The field type was changed from `dict[str, object]` (too loose) to
`dict[str, SourceDocument]`. This matches what Dev1's scrubber will
actually write there and makes type-checking useful.

## Test Update
`test_missing_source_files_do_not_break_graph` was updated to use a
custom `AppConfig` pointing to nonexistent paths. The real `data/` files
now exist (from Task 3), so the original test (which asserted
`raw_inputs == {}`) would have failed falsely. The new version isolates
the "missing files" scenario explicitly using a helper function
`_graph_with_missing_sources()`.

## How Dev3 Connects Their Code
Dev3 writes their class, then passes it into the registry:

```python
# In agents/registry.py or main.py — Dev3 modifies this when ready
from dev3_dedup import ChromaDBDeduplicator
from dev3_priority import ScoringEngine

def build_default_agent_stack():
    return [
        IngestionAgent(),
        ExtractionAgent(),
        DeduplicationAgent(engine=ChromaDBDeduplicator()),
        PrioritizationAgent(engine=ScoringEngine()),
        PlanningAgent(),
    ]
```

No changes needed to `specialists.py`, `state.py`, or `graph.py`.
