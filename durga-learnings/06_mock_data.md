# Data Files (Day 3 — Task 3)

## What This Is
The `data/` directory holds all source data consumed by the pipeline,
structured exactly as Dev1's contracts specify.

| File | Format | Source | Content |
|---|---|---|---|
| `data/raw/jira_board.json` | JSON `{"issues": [...]}` | Dev1 | 22 Jira sprint issues |
| `data/raw/servicenow_defects.json` | JSON `{"records": [...]}` | Dev1 | 15 ServiceNow incidents |
| `data/raw/outlook_inbox.json` | JSON `{"emails": [...]}` | Dev1 | 21 emails with hidden action items |
| `data/raw/meeting_transcripts.json` | JSON `{"meetings": [...]}` | Dev1 | 6 meeting transcripts |
| `data/injected/p1_emergency.json` | JSON `{"incident": {...}}` | Dev1 | Demo P1 drop file |
| `data/test/ground_truth_duplicates.json` | JSON | Dev1 | Duplicate pairs for Dev3/Dev5 |
| `data/test/prioritization_test_data.json` | JSON | Dev1 | Scoring test data for Dev3/Dev5 |

## Who Owns These Files
Dev1 owns all files under `data/`. We pulled them directly from
`origin/main` using `git checkout origin/main -- data/` to ensure we
always work with the exact same files Dev1 shipped — not stubs.

## Two Ways the Pipeline Reads Data

### Path A: FileSystemSourceReader (default, dev/test)
`config.py` maps each source name to its file path. `IngestionAgent`
loops over configs, reads each file as raw text via `FileSystemSourceReader`,
and stores `SourceDocument` objects in `WorkflowState.raw_inputs`.
`ExtractionAgent` then calls `MockLLMClient` on each document to produce
`UnifiedTask` objects. This path works offline with no API key.

### Path B: NormalizerSourceReader (production)
`IngestionAgent` detects a `NormalizerSourceReader` and calls
`normalize_all_sources()` once. Dev1's parsers handle all four files,
apply PII scrubbing, and return 65 `UnifiedTask` objects directly into
`WorkflowState.extracted_tasks`. The `ExtractionAgent` is then only
invoked for tasks where `raw_text is not None` (emails and transcripts
that need LLM action-item extraction). This is the path used at demo time.

## P1 Injection File
`data/injected/p1_emergency.json` is the file that gets dropped mid-demo
to trigger re-prioritization. The event monitor (`events/monitor.py`)
watches `data/injected/` and fires when any new `.json` file appears.
Dev1's normalizer auto-picks up injected files on re-run.

## Demo Key Task IDs
These IDs must survive the full pipeline for the mandatory demo flow:

| task_id | Why it matters |
|---|---|
| `JIRA-1001` | Upload bug — must be in top 3 |
| `SN-INC0001001` | Duplicate of JIRA-1001 — Dev3 must detect this |
| `EMAIL-001` | VP escalation — hidden action items in raw_text |
| `SN-INC0001011` | GDPR legal deadline today — must rank #1 or #2 |
| `INJECTED-INC0001016` | Dropped mid-demo — triggers re-prioritization |
