# Agent Foundation

## Summary
Day 1 was about creating the architecture that every later feature depends on. The goal was not to solve the whole problem, but to make sure the project has a clean execution path and shared contracts.

## What We Built
### Project scaffold
We created a Python package under `src/taskpilot_ai` and added `pyproject.toml`.

Why:
This keeps the codebase organized from the beginning.

How:
Modules are grouped by responsibility: `agents`, `orchestration`, `models`, and later `tools` and `prompts`.

### Orchestration graph
We added `TaskPilotGraph` in `src/taskpilot_ai/orchestration/graph.py`.

Why:
The system needs one place that decides the order of execution.

How:
The graph takes a `WorkflowState` and passes it through each agent in sequence.

### Workflow state
We added `WorkflowState` and `AgentMemory` in `src/taskpilot_ai/orchestration/state.py`.

Why:
Agents should not pass random dictionaries around. They need a shared, stable contract.

How:
The state object stores raw inputs, scrubbed inputs, extracted tasks, ranked tasks, daily plan, traces, and memory.

### Specialist agents
We added separate agent classes for ingestion, extraction, deduplication, prioritization, and planning.

Why:
Each agent should own one responsibility. This keeps the design testable and team-friendly.

How:
Each agent class implements `run(state)` and updates only the portion of the workflow it owns.

### Baseline testability
We added `src/taskpilot_ai/main.py` and `tests/test_graph.py`.

Why:
Architecture work should be executable and verifiable, not just described.

How:
The main module runs the graph and the test validates the pipeline contract.

## Main Concepts To Remember
- Agent topology: the order agents run in
- Shared state: the data contract between agents
- Memory: lightweight cross-step memory for agent behavior
- Separation of concerns: one module, one job
- Interface-first design: define contracts before integrations
