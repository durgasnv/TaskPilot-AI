# Interface Contracts (Day 3 — Task 1)

## What This Is
`src/taskpilot_ai/interfaces/protocols.py` defines four Python `Protocol`
classes — one per teammate whose code needs to plug into the orchestration
backbone Dev2 owns.

## Why It Exists
Dev1, Dev3, and Dev4 are building independent pieces. Without a formal
contract, each dev would make their own assumptions about method names,
argument types, and return shapes. When their branches merge, the join
points would break.

A `typing.Protocol` solves this at zero runtime cost: Python checks
compatibility structurally (duck typing), so a teammate's class qualifies
as long as it has the right method signature — it does not need to import
or inherit from anything in this file.

## The Four Contracts

### ScrubberProtocol (for Dev1)
```
scrub(document: SourceDocument) -> SourceDocument
```
Dev1 receives raw file content and returns the same document with PII
stripped. The `IngestionAgent` will call this between loading a file and
writing it to `WorkflowState.raw_inputs`.

### VectorDeduplicatorProtocol (for Dev3)
```
deduplicate(tasks: list[TaskRecord]) -> list[TaskRecord]
```
Dev3 runs ChromaDB/FAISS similarity over extracted tasks and collapses
duplicates. `DeduplicationAgent` will call this and store the result in
`WorkflowState.deduplicated_tasks`.

### PrioritizerProtocol (for Dev3)
```
rank(tasks: list[TaskRecord]) -> list[RankedTask]
```
Dev3 applies the multi-factor scoring formula (deadline + severity +
dependency depth) and returns `RankedTask` objects, each with a float
score and a plain-English rationale string. `PrioritizationAgent` calls
this and stores results in `WorkflowState.ranked_tasks`.

### NotifierProtocol (for Dev4)
```
notify(message: str, channel: str = "cli") -> None
```
Dev4 implements push notifications (Slack, CLI banner, webhook). The
event monitor (Day 3 Task 4) calls this when a P1 emergency file is
detected at runtime.

## How the Merge Will Work
Each teammate writes a class whose methods match the signatures above.
Dev2 passes that instance into the relevant agent at construction time.
If no implementation is passed, agents fall back to placeholder logic so
the pipeline keeps running. No teammate needs to modify `specialists.py`,
`state.py`, or `graph.py`.

## runtime_checkable
All four protocols are decorated with `@runtime_checkable`. This means
you can write `isinstance(obj, ScrubberProtocol)` in tests or assertions
to verify that a provided object actually satisfies the contract before
running the pipeline.
