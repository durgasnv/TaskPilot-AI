# Dev 2 Day 1 Scaffold

## Goal
Create the initial multi-agent topology and state contract before real source files exist.

## What This Scaffold Covers
- A Python package layout under `src/taskpilot_ai`
- A deterministic orchestration loop in `orchestration/graph.py`
- Specialist agent placeholders for ingestion, extraction, deduplication, prioritization, and planning
- Shared workflow state and memory objects in `orchestration/state.py`
- A smoke-test entry point in `main.py`

## Why This Can Proceed Before Dev 1
Dev 1 owns the source files and parsers, but Dev 2 can still define:
- The order agents run in
- The state they read and write
- The memory variables persisted between steps
- The interfaces that ingestion adapters must satisfy later

## Expected Next Integration
- Dev 1 plugs parsed source payloads into `WorkflowState.raw_inputs`
- Dev 3 replaces placeholder ranking with real scoring logic
- Dev 4 connects conversational and alerting routes to the orchestration graph
