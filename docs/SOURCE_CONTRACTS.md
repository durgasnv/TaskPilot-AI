# TaskPilot AI — Source Contracts

Defines the stable interfaces between Dev 1's data pipeline and the rest of the team. These are **frozen contracts** — changes require team consensus.

---

## Contract 1: File Locations

| File | Absolute path (from repo root) | Consumer |
|---|---|---|
| Jira board | `data/raw/jira_board.json` | Dev 2 (agent), Dev 3 (analytics), Dev 5 (QA) |
| ServiceNow defects | `data/raw/servicenow_defects.json` | Dev 2, Dev 3, Dev 5 |
| Outlook inbox | `data/raw/outlook_inbox.json` | Dev 2, Dev 3, Dev 5 |
| Meeting transcripts | `data/raw/meeting_transcripts.json` | Dev 2, Dev 3, Dev 5 |
| P1 injection directory | `data/injected/` | Dev 4 (event poller watches this) |
| P1 injection filename | `p1_emergency.json` (any `.json` file triggers) | Dev 4 |
| Ground truth duplicates | `data/test/ground_truth_duplicates.json` | Dev 5 |
| Prioritization test data | `data/test/prioritization_test_data.json` | Dev 3, Dev 5 |

**Path resolution** — use `src/utils/file_loader.py`:
```python
from src.utils.file_loader import RAW_DIR, INJECTED_DIR, TEST_DIR
jira_path = RAW_DIR / "jira_board.json"
```

---

## Contract 2: Parser Inputs and Outputs

### `parse_jira(file_path) -> List[UnifiedTask]`
- Input: JSON with top-level `"issues"` array
- Each issue must have: `id`, `title`, `status`, `severity`
- Optional: `description`, `deadline`, `assignee`, `blocks`, `blocked_by`, `labels`, `business_impact`
- Output: `List[UnifiedTask]` with `source="jira"`, `task_id="JIRA-{id}"`

### `parse_servicenow(file_path) -> List[UnifiedTask]`
- Input: JSON with top-level `"records"` array
- Each record must have: `number`, `short_description`, `priority` or `severity`, `state`
- Optional: `description`, `sla_due`, `assigned_to`, `tags`, `business_impact`
- Output: `List[UnifiedTask]` with `source="servicenow"`, `task_id="SN-{number}"`

### `parse_emails(file_path) -> List[UnifiedTask]`
- Input: JSON with top-level `"emails"` array
- Each email must have: `id`, `subject`, `from`, `received_at`, `body`
- Optional: `labels`, `hidden_action_items`, `related_jira`
- Output: `List[UnifiedTask]` with `source="email"`, `raw_text` populated for LLM extraction
- **Note:** `raw_text` contains the full scrubbed body + pre-declared action items. The LLM Extraction Agent reads `raw_text` — do not read `body` directly.

### `parse_meetings(file_path) -> List[UnifiedTask]`
- Input: JSON with top-level `"meetings"` array
- Each meeting must have: `id`, `title`, `date`, `transcript` (list of `{speaker, text}`)
- Optional: `extracted_action_items`, `attendees`
- Output: `List[UnifiedTask]` with `source="transcript"`, `extracted=True`, `raw_text` = full scrubbed transcript

---

## Contract 3: Normalization Entry Point

```python
from src.pipeline.normalizer import normalize_all_sources

result = normalize_all_sources()   # uses all default paths
# or specify paths explicitly:
result = normalize_all_sources(
    jira_path="data/raw/jira_board.json",
    servicenow_path="data/raw/servicenow_defects.json",
    email_path="data/raw/outlook_inbox.json",
    meeting_path="data/raw/meeting_transcripts.json",
    injected_path="data/injected",
)

result.tasks          # List[UnifiedTask] — all sources combined
result.total          # int — total task count
result.source_counts  # Dict[str, int] — per-source counts
result.errors         # List[str] — parse errors (non-fatal)
result.to_json()      # JSON string of full output
```

**Guarantees:**
- All `task_id` values are unique across the combined list
- All string fields have been PII-scrubbed
- No LLM calls are made — this is deterministic and fast (< 1 second)
- Parser failures are isolated: one broken source does not crash the pipeline

---

## Contract 4: Privacy Module

```python
from src.pipeline.privacy import scrub_text, scrub_dict

clean = scrub_text("Call +1-415-555-0192 or email foo@bar.com")
# -> "Call [PHONE] or email [EMAIL_ADDR]"

clean_dict = scrub_dict({"body": "AKIA1234567890ABCDEF key", "phone": "555-1234"})
# -> {"body": "[AWS_ACCESS_KEY_ID] key", "phone": "[REDACTED]"}
```

**Rule:** Any string that will reach an LLM MUST be passed through `scrub_text()` first. The parsers handle this for all standard fields. If you add new fields or new data sources, apply `scrub_text()` before assigning.

---

## Contract 5: Demo P1 Injection

Dev 4's file-drop listener watches `data/injected/` for new `.json` files.

**Trigger:** Any `.json` file dropped into `data/injected/` during the demo triggers re-prioritization.

**Required file structure:**
```json
{
  "incident": {
    "number": "INC0001016",
    "short_description": "...",
    "description": "...",
    "severity": "P1",
    "sla_due": "2026-06-19T09:47:00Z",
    "opened_at": "2026-06-19T08:47:00Z",
    "assigned_to": "dev_alice@company.com",
    "business_impact": "...",
    "tags": ["p1", "demo-injection"]
  }
}
```

The `_meta` key is optional and ignored by the parser.

---

## Contract 6: Cross-System Duplicate Pairs

The ground truth file at `data/test/ground_truth_duplicates.json` defines which task_ids refer to the same real-world issue. Dev 3 uses this to validate dedup accuracy; Dev 5 uses it to compute precision/recall metrics.

**Structure of each pair:**
```json
{
  "pair_id": "DUP-001",
  "canonical_task": "JIRA-1001",      <- task_id of the authoritative record
  "duplicate_task": "SN-INC0001001",  <- task_id of the duplicate
  "similarity_type": "exact_same_issue",
  "confidence": 0.97,
  "shared_signals": ["..."],
  "merge_strategy": "keep_jira_as_canonical"
}
```

**Key demo pair (must work in live demo):**
- `JIRA-1001` + `SN-INC0001001` + `EMAIL-001` + `EMAIL-002` — all refer to the ACME Corp file upload P1
- The dedup engine must merge these into one canonical task with `duplicate_of` set on the non-canonical records
