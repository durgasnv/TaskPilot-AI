# Agent Foundation

## Purpose
This document explains the Day 1 architecture work for Dev 2. The goal was to create a stable multi-agent skeleton before real data files, real LLM calls, or real UI wiring existed.

## Feature: Python Project Scaffold
### What it is
A `src/`-based Python package rooted at `src/taskpilot_ai`.

### Why it exists
It gives the team a clean place to add modules without mixing source code, tests, and docs in the repo root.

### How it works
The package is defined in `pyproject.toml`. Source code lives under `src/taskpilot_ai`, so imports are explicit and scalable as the codebase grows.

## Feature: Agent Topology
### What it is
A fixed execution order for the core agents:
`ingestion -> extraction -> deduplication -> prioritization -> planning`

### Why it exists
Without a defined order, each teammate could make incompatible assumptions about when data is available.

### How it works
`src/taskpilot_ai/orchestration/graph.py` creates a `TaskPilotGraph` that loops through the registered agents one by one. Each agent receives the same `WorkflowState`, updates its own part, and returns the updated state.

## Feature: Shared Workflow State
### What it is
A single state object that carries source inputs, extracted tasks, ranked tasks, plan output, execution traces, and memory.

### Why it exists
Agents need a consistent contract for reading and writing data. This prevents direct coupling between one agent's internals and another's implementation.

### How it works
`src/taskpilot_ai/orchestration/state.py` defines `WorkflowState`. Every stage reads from and writes to this object instead of inventing separate local formats.

## Feature: Agent Memory
### What it is
Persistent lightweight memory attached to the workflow.

### Why it exists
Some information is not final output but still matters across steps, such as extracted IDs, source locations, or prompt scratchpad entries.

### How it works
`AgentMemory` is nested inside `WorkflowState`. Agents update it as they run. This is where later agentic behaviors such as re-checks, change detection, or alert suppression can hook in.

## Feature: Specialist Agents
### What it is
Separate classes for ingestion, extraction, deduplication, prioritization, and planning.

### Why it exists
Each major responsibility needs its own module so different developers can work independently and so the logic stays testable.

### How it works
`src/taskpilot_ai/agents/specialists.py` contains one class per responsibility. Right now, some are placeholders, but the responsibility boundary is already established.

## Feature: Smoke-Test Execution Path
### What it is
A minimal runnable path plus tests.

### Why it exists
Scaffolding that cannot execute is just theory. The team needs proof that the baseline architecture actually runs.

### How it works
`src/taskpilot_ai/main.py` runs the graph. `tests/test_graph.py` validates that the pipeline executes and that the branch stays stable as new Dev 2 work is added.

