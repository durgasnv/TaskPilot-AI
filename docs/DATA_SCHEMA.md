# TaskPilot AI — Data Schema Reference

**Status:** FROZEN — do not change field names or types without team sign-off.  
**Version:** 1.0  
**Owner:** Dev 1 (Data Pipeline & Privacy Lead)

---

## UnifiedTask — Canonical Data Contract

Every data source emits `UnifiedTask` objects. All agents, the dedup engine, the prioritization engine, and the interface layer consume this type exclusively.

```python
class UnifiedTask(BaseModel):
    # --- Identity ---
    task_id:              str                  # Unique: "JIRA-1001", "SN-INC0001001", "EMAIL-003", "MTG-001"
    source:               TaskSource           # "jira" | "servicenow" | "email" | "transcript"
    source_id:            str                  # Original ID in the source system

    # --- Core content (always PII-scrubbed) ---
    title:                str                  # Short summary (required, non-empty)
    description:          str                  # Full detail — scrubbed before population

    # --- Scheduling ---
    deadline:             Optional[datetime]   # UTC. None = no SLA
    created_at:           Optional[datetime]
    updated_at:           Optional[datetime]

    # --- Classification ---
    severity:             Optional[Severity]   # "P1" | "P2" | "P3" | "P4"
    status:               TaskStatus           # "open" | "in_progress" | "blocked" | "resolved" | "closed"
    labels:               List[str]

    # --- Assignment ---
    assignee:             Optional[str]        # Role alias or scrubbed name — never raw PII
    reporter:             Optional[str]
    team:                 Optional[str]

    # --- Dependency graph ---
    blocks:               List[str]            # task_ids this task blocks
    blocked_by:           List[str]            # task_ids blocking this task

    # --- Extraction metadata ---
    extracted:            bool                 # True = LLM-extracted from unstructured text
    raw_text:             Optional[str]        # Original scrubbed text (for LLM use)
    extraction_confidence: Optional[float]     # 0.0–1.0

    # --- Cross-system correlation ---
    duplicate_of:         Optional[str]        # task_id of canonical task if this is a dup
    related_tasks:        List[str]            # Semantically related (not duplicates)

    # --- Prioritization ---
    business_impact:      Optional[str]        # Human-readable impact note
    priority_score:       Optional[float]      # Set by prioritization engine
    priority_rationale:   Optional[str]        # Set by prioritization engine
```

---

## Severity Enum

| Value | Meaning | SLA |
|---|---|---|
| `P1` | Critical | < 1 business day |
| `P2` | High | < 3 business days |
| `P3` | Medium | < 1 sprint |
| `P4` | Low | Best effort |

**Rule:** All sources must map to this enum. Never use "Critical", "High", "1 - Critical" etc. in the UnifiedTask — the parsers normalize these.

---

## TaskSource Enum

| Value | Source system |
|---|---|
| `jira` | Jira sprint board |
| `servicenow` | ServiceNow incident tracker |
| `email` | Outlook inbox |
| `transcript` | Meeting transcript |

---

## task_id Format Convention

| Source | Format | Example |
|---|---|---|
| Jira | `JIRA-{issue_id}` | `JIRA-1001` |
| ServiceNow | `SN-{number}` | `SN-INC0001001` |
| Email | `EMAIL-{id}` | `EMAIL-001` |
| Meeting | `MTG-{id}` | `MTG-001` |
| Injected P1 | `INJECTED-{number}` | `INJECTED-INC0001016` |

task_ids are **globally unique within a normalized pipeline run**. The dedup engine uses these as stable anchors.

---

## PII Scrubbing Rules

The following patterns are replaced BEFORE any string populates a UnifiedTask field:

| Pattern | Replacement |
|---|---|
| Phone numbers (US/international/E.164) | `[PHONE]` |
| Email addresses | `[EMAIL_ADDR]` |
| AWS Access Key IDs (`AKIA...`) | `[AWS_ACCESS_KEY_ID]` |
| AWS Secret Keys | `[AWS_SECRET_KEY]` |
| Credit/debit card numbers | `[CREDIT_CARD]` |
| Indian Aadhaar numbers (12-digit) | `[AADHAAR]` |
| US Social Security Numbers | `[SSN]` |
| Internal employee IDs (`ACC-USER-NNNNN`) | `[EMPLOYEE_ID]` |
| Internal account IDs (`ACC-NNNN`) | `[ACCOUNT_ID]` |
| IPv4 / IPv6 addresses | `[IP_ADDR]` / `[IP_ADDR_V6]` |

Fields named `phone`, `password`, `secret`, `token`, `api_key`, `private_key` in raw dicts are replaced wholesale with `[REDACTED]`.

---

## Directory Structure

```
TaskPilot-AI/
├── data/
│   ├── raw/
│   │   ├── jira_board.json            # 22 Jira tasks
│   │   ├── servicenow_defects.json    # 15 ServiceNow incidents
│   │   ├── outlook_inbox.json         # 21 emails
│   │   └── meeting_transcripts.json   # 6 meeting transcripts
│   ├── injected/
│   │   └── p1_emergency.json          # Drop here for demo P1 injection
│   └── test/
│       ├── ground_truth_duplicates.json    # 12 duplicate pairs for QA
│       └── prioritization_test_data.json   # Expected ranking for engine validation
├── src/
│   ├── schemas/
│   │   └── unified_task.py            # Pydantic UnifiedTask model
│   ├── parsers/
│   │   ├── jira_parser.py
│   │   ├── servicenow_parser.py
│   │   ├── email_parser.py
│   │   └── meeting_parser.py
│   ├── pipeline/
│   │   ├── privacy.py                 # scrub_text(), scrub_dict()
│   │   └── normalizer.py              # normalize_all_sources()
│   └── utils/
│       └── file_loader.py             # REPO_ROOT, RAW_DIR, etc.
├── docs/
│   ├── DATA_SCHEMA.md                 # This file
│   ├── SOURCE_CONTRACTS.md
│   └── handoff/
│       ├── DEV2_AGENT_HANDOFF.md
│       ├── DEV3_ANALYTICS_HANDOFF.md
│       ├── DEV4_INTERFACE_HANDOFF.md
│       └── DEV5_QA_HANDOFF.md
└── tests/
    └── test_pipeline.py               # 73-check validation suite
```
