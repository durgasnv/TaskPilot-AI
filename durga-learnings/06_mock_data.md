# Mock Data Files (Day 3 — Task 3)

## What This Is
Four files in `data/` that simulate the four heterogeneous sources the
PRD requires: Jira, ServiceNow, Outlook, and meeting notes.

| File | Format | Simulates |
|---|---|---|
| `data/jira.json` | JSON | Jira sprint board with 3 issues (P1 bug, P2 security, P3 story) |
| `data/servicenow.json` | JSON | ServiceNow incidents (P1 DB pool exhaustion, P2 SSL expiry) |
| `data/outlook.txt` | Plain text | Email inbox — VP escalation + teammate PR review request |
| `data/meeting_notes.txt` | Plain text | Sprint review transcript with 2 buried action items |

## Why It Exists
Before this task the `IngestionAgent` always logged `"Skipped source"` for
every configured source because the files did not exist. That meant
`ExtractionAgent` had nothing to process and `state.extracted_tasks` was
always empty.

These files give the full pipeline something real to work with during
development and the hackathon demo.

## Who Owns These Files Long-Term
Dev1 is responsible for the real versions of these files. Their data
pipeline will produce properly PII-scrubbed copies with realistic content
drawn from the provided hackathon dataset.

The files here are stubs that:
- Follow the same paths that `AppConfig` expects (`data/jira.json`, etc.)
- Contain believable content that exercises the extraction prompts
- Can be replaced by Dev1's files with zero code changes

## Pipeline Result After This Task
```
Ingestion   → loads 4 files → raw_inputs has 4 SourceDocuments
Extraction  → calls MockLLM → extracted_tasks has 5 TaskRecords
                JIRA-101  P1  Fix payment gateway timeout
                JIRA-102  P2  Upgrade auth library (CVE)
                SN-5501   P1  DB connection pool exhausted
                EMAIL-001 P2  VP escalation response
                MTG-001   P3  Add retry logic to ingestion
Dedup       → passes through (Dev3 will replace)
Prioritizer → placeholder scores (Dev3 will replace)
Planner     → daily_plan list built from ranked tasks
```

## Data Design Notes
- The Jira JSON includes `dependencies` arrays (JIRA-102 blocks on JIRA-101)
  so Dev3's dependency-aware prioritizer has real data to score against
- The Outlook file has TWO emails — one urgent (VP), one routine (PR review)
  — to test that extraction finds the P2 hidden among low-priority content
- The meeting notes transcript uses natural language so the extraction LLM
  must parse free text rather than structured JSON
- ServiceNow SN-5501 intentionally overlaps with the Jira payment bug theme
  to give Dev3's deduplication engine a cross-source merge scenario
