# How TaskPilot AI Works — Full System Walkthrough

This is the master guide. Read this first. The other docs (01–08) go deeper on individual pieces.

---

## The Problem We're Solving

A software engineering team has tasks scattered across four places:
- **Jira** — bug tickets and feature requests
- **ServiceNow** — incident reports
- **Outlook** — emails with requests buried inside them
- **Meeting transcripts** — action items mentioned in standups

Every morning, an engineer has to manually check all four, figure out what's most urgent, and decide what to work on. TaskPilot AI does this automatically.

---

## The Big Picture

Raw files → **5 agents run in sequence** → Daily plan printed to screen

```
[Jira JSON]       ─┐
[ServiceNow JSON] ─┤─► IngestionAgent ─► ExtractionAgent ─► DeduplicationAgent ─► PrioritizationAgent ─► PlanningAgent
[Outlook JSON]    ─┤
[Meeting JSON]    ─┘
```

Each agent takes a **WorkflowState** object, does its job, adds to it, and passes it to the next agent. The final state contains the ranked daily plan.

---

## What Each Agent Does

### 1. IngestionAgent (`agents/specialists.py`)

**Job:** Read the raw source files from disk.

It loops through the four configured source files (`data/raw/`) and reads each one. If a file is missing or broken, it skips it and logs the error — it never crashes the whole pipeline.

After this step, `WorkflowState.raw_inputs` contains the raw file content as `SourceDocument` objects, one per source.

```
raw_inputs = {
    "jira":          SourceDocument(content="...22 jira issues..."),
    "servicenow":    SourceDocument(content="...15 incidents..."),
    "outlook":       SourceDocument(content="...21 emails..."),
    "meeting_notes": SourceDocument(content="...6 meetings..."),
}
```

---

### 2. ExtractionAgent (`agents/specialists.py`)

**Job:** Turn raw text into structured task objects using an LLM.

For each document in `raw_inputs`, it builds a prompt (using `prompts/extraction.py`) and sends it to the LLM. The LLM returns a JSON array of tasks.

Right now we use `MockLLMClient` which returns fake but realistic JSON without needing a real API key. When the real LLM is connected, you swap it in — nothing else changes.

After this step, `WorkflowState.extracted_tasks` contains a list of `UnifiedTask` objects.

```
extracted_tasks = [
    UnifiedTask(task_id="JIRA-001", title="Fix payment gateway timeout", severity="P1"),
    UnifiedTask(task_id="SN-003",   title="Production DB pool exhausted", severity="P1"),
    UnifiedTask(task_id="EMAIL-01", title="Respond to VP escalation",    severity="P2"),
    ...
]
```

---

### 3. DeduplicationAgent (`agents/specialists.py`)

**Job:** Remove duplicate tasks that appear in multiple sources.

Example: A production outage might be reported as a Jira ticket AND a ServiceNow incident. They're the same task. This agent merges them.

Right now it's a passthrough (keeps all tasks as-is) because Dev3 hasn't plugged in their vector similarity engine yet. The injection point is ready — Dev3 just needs to pass an object that matches `VectorDeduplicatorProtocol`.

After this step, `WorkflowState.deduplicated_tasks` has the cleaned list.

---

### 4. PrioritizationAgent (`agents/specialists.py`)

**Job:** Score and sort tasks by urgency.

It assigns a `priority_score` (float) and a `priority_rationale` (plain English explanation) to each task. The default logic is a placeholder — Dev3 will replace it with logic that factors in deadline proximity, severity, and dependency depth.

One special feature: **emergency mode**. If `WorkflowState.emergency_mode = True`, all P1-severity tasks are forced to the top of the list regardless of score. This is used when a critical file is detected mid-session.

After this step, `WorkflowState.ranked_tasks` is sorted by priority.

---

### 5. PlanningAgent (`agents/specialists.py`)

**Job:** Build the final daily plan.

It takes the ordered `ranked_tasks` list and extracts the titles into `WorkflowState.daily_plan`. This is what gets printed to the user.

```
daily_plan = [
    "Fix payment gateway timeout on checkout",
    "Production DB connection pool exhausted",
    "Respond to VP escalation on upload latency",
    ...
]
```

---

## The Data Contract — UnifiedTask (`unified_task.py`)

Every agent speaks the same language. The universal currency is `UnifiedTask` — a Pydantic model with fields that every part of the pipeline agrees on.

Key fields:

| Field | What it is |
|---|---|
| `task_id` | Unique ID like `JIRA-001`, `SN-003`, `EMAIL-01` |
| `source` | Where it came from: `jira`, `servicenow`, `email`, `transcript` |
| `title` | One-line summary of the task |
| `severity` | P1 (critical) → P4 (low) |
| `deadline` | When it must be done (ISO datetime or null) |
| `blocked_by` | List of task_ids this task is waiting on |
| `blocks` | List of task_ids that can't start until this is done |
| `priority_score` | Float set by PrioritizationAgent |
| `priority_rationale` | Plain English explanation of the score |
| `duplicate_of` | Set by DeduplicationAgent if this task is a copy |

Pydantic validates all of this automatically — if you try to create a `UnifiedTask` with a blank `task_id` or an invalid severity, it raises an error immediately.

---

## The Shared State — WorkflowState (`orchestration/state.py`)

`WorkflowState` is the object that gets passed from agent to agent. Think of it as a baton in a relay race — each runner (agent) picks it up, adds to it, and passes it forward.

```
WorkflowState
├── raw_inputs          — dict of SourceDocuments (set by IngestionAgent)
├── extracted_tasks     — list of UnifiedTask (set by ExtractionAgent)
├── deduplicated_tasks  — list of UnifiedTask (set by DeduplicationAgent)
├── ranked_tasks        — list of UnifiedTask, sorted (set by PrioritizationAgent)
├── daily_plan          — list of task titles (set by PlanningAgent)
├── traces              — log of every step taken (set by all agents)
├── memory              — scratchpad for intermediate reasoning
└── emergency_mode      — bool: True forces P1s to top
```

The `traces` list is especially useful for debugging. Every agent calls `state.trace("agent_name", "what I did")` so you can see exactly what happened at each step.

---

## How Teammates Plug In (Protocols — `interfaces/protocols.py`)

We designed this so each teammate can build their piece independently without needing to touch our code. We define **Protocol classes** — these are like a contract that says "if your class has this method, it works with our system."

| Protocol | Who implements it | What it does |
|---|---|---|
| `ScrubberProtocol` | Dev1 | Takes a SourceDocument, returns one with PII removed |
| `VectorDeduplicatorProtocol` | Dev3 | Takes a list of UnifiedTask, returns deduplicated list |
| `PrioritizerProtocol` | Dev3 | Takes a list of UnifiedTask, returns them ranked |
| `NotifierProtocol` | Dev4 | Sends an alert message (Slack, CLI, webhook) |

To plug in Dev3's deduplicator:
```python
from dev3_module import Dev3Deduplicator

graph = TaskPilotGraph(agents=[
    IngestionAgent(),
    ExtractionAgent(),
    DeduplicationAgent(engine=Dev3Deduplicator()),  # ← just pass it here
    PrioritizationAgent(),
    PlanningAgent(),
])
```

Dev3 doesn't import anything from our code. We don't import anything from Dev3. The Protocol is the handshake.

---

## The LLM Abstraction (`llm/client.py`)

We don't hard-code a specific LLM. Instead we define `LLMClient` as an abstract base class with one method: `complete(system_prompt, user_prompt) -> LLMResponse`.

`MockLLMClient` is our fake implementation — it returns deterministic JSON without calling any API. This lets the whole pipeline run and be tested with zero API keys or internet access.

When it's time to use a real LLM:
```python
ExtractionAgent(llm=OpenAIClient(model="gpt-4o"))
```

Nothing else in the pipeline changes.

---

## The Event Monitor (`events/monitor.py`)

This is the demo feature. `FileDropMonitor` watches the `data/injected/` directory on a polling loop (every 5 seconds).

**The scenario:** During a live demo, someone drops a P1 incident file into `data/injected/`. The monitor detects it immediately, fires a `NotifierProtocol.notify()` alert, then re-runs the entire pipeline with `emergency_mode=True`. The output shows the P1 task forced to the top of the daily plan.

How seeding works (important detail): When the monitor starts, it first records all files currently in the directory as "already seen." This is the baseline. Only files that appear AFTER that point trigger alerts. Without this, every file already in the folder would fire an alert on startup.

---

## How the Retry Logic Works (`tools/source_reader.py`)

`FileSystemSourceReader.read()` doesn't just fail immediately if a file is missing. It retries up to `SourceConfig.retries` times (default: 2) with a 0.5-second wait between attempts.

Why? In a real system, source files might be written by another process. If we check just before the write finishes, we'd get a false "missing file" error. Retrying gives the writer time to finish.

---

## How to Run It

```bash
cd TaskPilot-AI
python -m taskpilot_ai.main
```

You'll see:
1. Which sources were loaded
2. How many tasks were extracted and deduplicated
3. The full daily plan with severity labels
4. Every execution trace

To run the tests:
```bash
python -m pytest tests/test_graph.py -v
```

---

## File Map — Where Everything Lives

```
src/taskpilot_ai/
├── main.py                      ← entry point, run this
├── unified_task.py              ← the shared data contract (UnifiedTask)
├── models.py                    ← SourceDocument, FileSource enum
├── config.py                    ← AppConfig, SourceConfig (paths + retries)
│
├── agents/
│   ├── base.py                  ← Agent abstract base class
│   ├── specialists.py           ← all 5 agents live here
│   ├── react_runtime.py         ← builds ReAct-style prompt packets
│   └── registry.py              ← builds the default agent stack
│
├── orchestration/
│   ├── graph.py                 ← TaskPilotGraph: runs agents in sequence
│   └── state.py                 ← WorkflowState, AgentMemory, ExecutionTrace
│
├── interfaces/
│   └── protocols.py             ← contracts for teammates (Scrubber, Deduplicator, etc.)
│
├── llm/
│   └── client.py                ← LLMClient ABC + MockLLMClient
│
├── prompts/
│   └── extraction.py            ← prompt builders for ingestion and extraction
│
├── tools/
│   └── source_reader.py         ← FileSystemSourceReader, NormalizerSourceReader
│
└── events/
    └── monitor.py               ← FileDropMonitor (watches data/injected/)
```

---

## The Learning Sequence

If you want to understand this codebase from scratch, read in this order:

1. `unified_task.py` — understand what a task looks like
2. `orchestration/state.py` — understand how state flows
3. `agents/specialists.py` — read each agent top to bottom
4. `orchestration/graph.py` — see how agents are chained
5. `interfaces/protocols.py` — understand how teammates connect
6. `llm/client.py` — understand the LLM abstraction
7. `events/monitor.py` — understand the P1 injection demo

The detailed learning logs in this folder (01–08) explain each of these with more depth and the "why" behind each decision.
