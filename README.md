# TaskPilot-AI
An Agentic AI Assistant That Conquers Engineer Task Overload

## Current Status
Day 1 and Day 2 Dev 2 scaffolds are in place under `src/taskpilot_ai` with:
- agent topology placeholders
- shared workflow state and memory objects
- a simple orchestration loop
- file-reading tool abstractions
- ReAct prompt scaffolding for ingestion and extraction
- a smoke test in `tests/test_graph.py`

## Dev 2 Notes
- `docs/1100_agent_foundation.md`: initial architecture foundation
- `docs/1200_ingestion_and_extraction_design.md`: ingestion and extraction design
- `durga-learnings/`: Dev 2 implementation notes, concepts, and next tasks

## Local Run
```bash
python -m taskpilot_ai.main
```
