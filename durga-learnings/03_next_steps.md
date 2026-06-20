# Next Steps — Day 2 Retrospective (All Complete)

This doc was written after Day 2 to track what remained. All items are now done.

## Build Tasks (Done in Day 3)
- [x] Connect a real LLM client to the ReAct prompt packets → `llm/client.py` (`MockLLMClient` + `LLMClient` ABC)
- [x] Define structured extraction output for downstream agents → `prompts/extraction.py` system prompt now includes full JSON schema spec
- [x] Add retry and failure policy for source-loading problems → `FileSystemSourceReader.read()` retries on `OSError`/missing file
- [x] Add event-driven triggers for Day 3 re-prioritization work → `events/monitor.py` (`FileDropMonitor`)

## Team Coordination Tasks (Done in Day 3)
- [x] Confirm final file names and payload shapes with Dev1 → aligned to `data/raw/` paths and `UnifiedTask` from `src/schemas/`
- [x] Confirm output schema expectations with Dev3 → `interfaces/protocols.py` (`VectorDeduplicatorProtocol`, `PrioritizerProtocol`)
- [x] Confirm UI tracing needs with Dev4 → `interfaces/protocols.py` (`NotifierProtocol`), `WorkflowState.traces`
