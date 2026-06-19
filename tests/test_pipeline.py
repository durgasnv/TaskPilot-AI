"""
Dev 1 validation suite.

Runs without any LLM API calls. Validates:
  - Privacy / PII scrubbing
  - All four parsers
  - Normalization pipeline
  - Schema consistency
  - File path resolution
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.privacy import scrub_dict, scrub_text
from src.pipeline.normalizer import normalize_all_sources
from src.parsers.jira_parser import parse_jira
from src.parsers.servicenow_parser import parse_servicenow
from src.parsers.email_parser import parse_emails
from src.parsers.meeting_parser import parse_meetings
from src.schemas.unified_task import Severity, TaskSource, TaskStatus, UnifiedTask
from src.utils.file_loader import RAW_DIR, TEST_DIR, INJECTED_DIR, REPO_ROOT

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    icon = "+" if condition else "X"
    print(f"  {icon} [{status}] {name}" + (f" - {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# 1. Privacy layer
# ---------------------------------------------------------------------------
print("\n=== 1. Privacy Layer ===")

scrubbed = scrub_text("Call me at +1-415-555-0192 or email alice@company.com")
check("phone scrubbed", "[PHONE]" in scrubbed, scrubbed)
check("email scrubbed", "[EMAIL_ADDR]" in scrubbed, scrubbed)
check("original text not in scrubbed", "+1-415-555-0192" not in scrubbed)

scrubbed_aws = scrub_text("AKIA1234567890ABCDEF is the key and aws_secret_access_key=abcdefghijklmnopqrstuvwxyz12345678901234")
check("AWS key ID scrubbed", "AKIA1234567890ABCDEF" not in scrubbed_aws, scrubbed_aws[:60])
check("AWS secret scrubbed", "[AWS_SECRET_KEY]" in scrubbed_aws, scrubbed_aws[:80])

scrubbed_aadhaar = scrub_text("My Aadhaar is 2345 6789 0123")
check("Aadhaar scrubbed", "[AADHAAR]" in scrubbed_aadhaar, scrubbed_aadhaar)

scrubbed_card = scrub_text("Card: 4111 1111 1111 1111")
check("Credit card scrubbed", "[CREDIT_CARD]" in scrubbed_card, scrubbed_card)

d = scrub_dict({"name": "Alice", "phone": "+1-415-555-0192", "description": "Call +1-312-555-0147"})
check("dict phone field redacted", d["phone"] == "[REDACTED]")
check("dict description phone scrubbed", "[PHONE]" in d["description"])
check("dict non-PII field preserved", d["name"] == "Alice")

# ---------------------------------------------------------------------------
# 2. File paths
# ---------------------------------------------------------------------------
print("\n=== 2. File Path Resolution ===")

check("REPO_ROOT exists", REPO_ROOT.exists(), str(REPO_ROOT))
check("RAW_DIR exists", RAW_DIR.exists(), str(RAW_DIR))
check("TEST_DIR exists", TEST_DIR.exists(), str(TEST_DIR))
check("INJECTED_DIR exists", INJECTED_DIR.exists(), str(INJECTED_DIR))
check("jira_board.json exists", (RAW_DIR / "jira_board.json").exists())
check("servicenow_defects.json exists", (RAW_DIR / "servicenow_defects.json").exists())
check("outlook_inbox.json exists", (RAW_DIR / "outlook_inbox.json").exists())
check("meeting_transcripts.json exists", (RAW_DIR / "meeting_transcripts.json").exists())
check("ground_truth_duplicates.json exists", (TEST_DIR / "ground_truth_duplicates.json").exists())
check("prioritization_test_data.json exists", (TEST_DIR / "prioritization_test_data.json").exists())
check("p1_emergency.json exists", (INJECTED_DIR / "p1_emergency.json").exists())

# ---------------------------------------------------------------------------
# 3. Jira parser
# ---------------------------------------------------------------------------
print("\n=== 3. Jira Parser ===")

jira_tasks = parse_jira(RAW_DIR / "jira_board.json")
check("jira: returns list", isinstance(jira_tasks, list))
check("jira: 20+ tasks", len(jira_tasks) >= 20, f"{len(jira_tasks)} tasks")
check("jira: all UnifiedTask", all(isinstance(t, UnifiedTask) for t in jira_tasks))
check("jira: all have source=jira", all(t.source == TaskSource.JIRA for t in jira_tasks))
check("jira: all have task_id", all(t.task_id for t in jira_tasks))
check("jira: all have title", all(t.title for t in jira_tasks))
p1_tasks = [t for t in jira_tasks if t.severity == Severity.P1]
check("jira: has P1 tasks", len(p1_tasks) >= 3, f"{len(p1_tasks)} P1 tasks")
blocked_tasks = [t for t in jira_tasks if t.status == TaskStatus.BLOCKED]
check("jira: has blocked tasks", len(blocked_tasks) >= 2, f"{len(blocked_tasks)} blocked")
tasks_with_deps = [t for t in jira_tasks if t.blocks or t.blocked_by]
check("jira: has dependency links", len(tasks_with_deps) >= 5, f"{len(tasks_with_deps)} with deps")
tasks_with_deadlines = [t for t in jira_tasks if t.deadline]
check("jira: has deadlines", len(tasks_with_deadlines) >= 10, f"{len(tasks_with_deadlines)} with deadlines")

# PII check: no raw emails in scrubbed descriptions
for t in jira_tasks:
    if "@" in (t.description or "") and "[EMAIL_ADDR]" not in (t.description or ""):
        check(f"jira PII check {t.task_id}", False, "raw email found in description")
        break
else:
    check("jira: descriptions scrubbed (no raw emails)", True)

# ---------------------------------------------------------------------------
# 4. ServiceNow parser
# ---------------------------------------------------------------------------
print("\n=== 4. ServiceNow Parser ===")

sn_tasks = parse_servicenow(RAW_DIR / "servicenow_defects.json")
check("sn: returns list", isinstance(sn_tasks, list))
check("sn: 15+ tasks", len(sn_tasks) >= 15, f"{len(sn_tasks)} tasks")
check("sn: all UnifiedTask", all(isinstance(t, UnifiedTask) for t in sn_tasks))
check("sn: all have source=servicenow", all(t.source == TaskSource.SERVICENOW for t in sn_tasks))
check("sn: task_ids start with SN-", all(t.task_id.startswith("SN-") for t in sn_tasks))
sn_p1 = [t for t in sn_tasks if t.severity == Severity.P1]
check("sn: has P1 incidents", len(sn_p1) >= 4, f"{len(sn_p1)} P1s")
sn_with_deadlines = [t for t in sn_tasks if t.deadline]
check("sn: incidents have SLA deadlines", len(sn_with_deadlines) >= 10, f"{len(sn_with_deadlines)}")

# ---------------------------------------------------------------------------
# 5. Email parser
# ---------------------------------------------------------------------------
print("\n=== 5. Email Parser ===")

email_tasks = parse_emails(RAW_DIR / "outlook_inbox.json")
check("email: returns list", isinstance(email_tasks, list))
check("email: 20+ emails", len(email_tasks) >= 20, f"{len(email_tasks)} emails")
check("email: all UnifiedTask", all(isinstance(t, UnifiedTask) for t in email_tasks))
check("email: all have source=email", all(t.source == TaskSource.EMAIL for t in email_tasks))
email_p1 = [t for t in email_tasks if t.severity == Severity.P1]
check("email: urgent emails classified P1", len(email_p1) >= 5, f"{len(email_p1)} P1s")
emails_with_raw_text = [t for t in email_tasks if t.raw_text]
check("email: raw_text populated (for LLM extraction)", len(emails_with_raw_text) >= 15)

# Verify phone numbers in email raw_text are scrubbed
vp_email = next((t for t in email_tasks if "EMAIL-001" in t.task_id), None)
if vp_email:
    check("email: phone scrubbed in raw_text", "+1-415-555-0192" not in (vp_email.raw_text or ""), vp_email.raw_text[:100] if vp_email.raw_text else "None")
    check("email: PHONE placeholder present in raw_text", "[PHONE]" in (vp_email.raw_text or ""))

# ---------------------------------------------------------------------------
# 6. Meeting parser
# ---------------------------------------------------------------------------
print("\n=== 6. Meeting Parser ===")

meeting_tasks = parse_meetings(RAW_DIR / "meeting_transcripts.json")
check("meetings: returns list", isinstance(meeting_tasks, list))
check("meetings: 5+ meetings", len(meeting_tasks) >= 5, f"{len(meeting_tasks)} meetings")
check("meetings: all UnifiedTask", all(isinstance(t, UnifiedTask) for t in meeting_tasks))
check("meetings: all have source=transcript", all(t.source == TaskSource.TRANSCRIPT for t in meeting_tasks))
meetings_with_raw = [t for t in meeting_tasks if t.raw_text]
check("meetings: raw_text populated (transcript text for LLM)", len(meetings_with_raw) >= 5)
meetings_extracted = [t for t in meeting_tasks if t.extracted]
check("meetings: marked as extracted=True", len(meetings_extracted) >= 5)

# ---------------------------------------------------------------------------
# 7. Normalization pipeline
# ---------------------------------------------------------------------------
print("\n=== 7. Normalization Pipeline ===")

result = normalize_all_sources(
    jira_path=RAW_DIR / "jira_board.json",
    servicenow_path=RAW_DIR / "servicenow_defects.json",
    email_path=RAW_DIR / "outlook_inbox.json",
    meeting_path=RAW_DIR / "meeting_transcripts.json",
    injected_path=INJECTED_DIR,
)
check("normalizer: returns NormalizationResult", result is not None)
check("normalizer: 60+ total tasks", result.total >= 60, f"{result.total} total tasks")
check("normalizer: no critical errors", len(result.errors) == 0, str(result.errors))
check("normalizer: source_counts has all 4 sources", all(k in result.source_counts for k in ["jira", "servicenow", "email", "transcript"]))
check("normalizer: jira count >= 20", result.source_counts.get("jira", 0) >= 20)
check("normalizer: sn count >= 15", result.source_counts.get("servicenow", 0) >= 15)
check("normalizer: email count >= 20", result.source_counts.get("email", 0) >= 20)
check("normalizer: transcript count >= 5", result.source_counts.get("transcript", 0) >= 5)

# All tasks have required fields
for t in result.tasks:
    assert t.task_id, f"Empty task_id: {t}"
    assert t.title, f"Empty title: {t.task_id}"
    assert t.source, f"Missing source: {t.task_id}"
check("normalizer: all tasks have task_id, title, source", True)

# No duplicate task_ids
task_ids = [t.task_id for t in result.tasks]
check("normalizer: no duplicate task_ids", len(task_ids) == len(set(task_ids)), f"{len(task_ids)} total, {len(set(task_ids))} unique")

# ---------------------------------------------------------------------------
# 8. Schema round-trip (serialization)
# ---------------------------------------------------------------------------
print("\n=== 8. Schema Serialization ===")

sample = result.tasks[0]
json_str = sample.model_dump_json()
check("schema: model_dump_json works", bool(json_str))
reloaded = UnifiedTask.model_validate_json(json_str)
check("schema: round-trip validate_json works", reloaded.task_id == sample.task_id)

full_json = result.to_json()
check("normalizer: to_json produces valid JSON", bool(json.loads(full_json)))

# ---------------------------------------------------------------------------
# 9. Ground truth file integrity
# ---------------------------------------------------------------------------
print("\n=== 9. Ground Truth File Integrity ===")

with (TEST_DIR / "ground_truth_duplicates.json").open() as f:
    gt = json.load(f)
check("ground truth: has duplicate_pairs", len(gt.get("duplicate_pairs", [])) >= 10)
check("ground truth: has extracted_only_tasks", len(gt.get("extracted_only_tasks", {}).get("items", [])) >= 10)
check("ground truth: target_accuracy = 90%", gt["_meta"]["target_accuracy"] == ">=90% precision and recall")

# Verify all canonical task_ids in ground truth exist in parsed tasks
all_task_ids = set(t.task_id for t in result.tasks)
missing_canonical = []
for pair in gt["duplicate_pairs"]:
    cid = pair["canonical_task"]
    # Ground truth uses bare IDs — check prefixed versions
    prefixed = f"JIRA-{cid.replace('JIRA-', '')}" if cid.startswith("JIRA") else cid
    # SN- prefixed
    sn_prefixed = f"SN-{cid}" if not cid.startswith("SN-") and not cid.startswith("JIRA") and not cid.startswith("EMAIL") and not cid.startswith("MTG") else cid
    if prefixed not in all_task_ids and sn_prefixed not in all_task_ids and cid not in all_task_ids:
        missing_canonical.append(cid)
check("ground truth: canonical task_ids resolvable", len(missing_canonical) == 0, str(missing_canonical))

with (TEST_DIR / "prioritization_test_data.json").open() as f:
    pt = json.load(f)
check("prioritization test: has expected_top_10_ranking", len(pt.get("expected_top_10_ranking", [])) >= 10)
check("prioritization test: has scoring_edge_cases", len(pt.get("scoring_edge_cases", [])) >= 3)
check("prioritization test: has demo_scenario_validation", "demo_scenario_validation" in pt)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
print(f"TOTAL: {passed} passed, {failed} failed out of {len(results)} checks")
print("=" * 60)

if failed > 0:
    print("\nFAILED CHECKS:")
    for status, name, detail in results:
        if status == FAIL:
            print(f"  X {name}" + (f" - {detail}" if detail else ""))
    sys.exit(1)
else:
    print("\nAll checks passed. Dev 1 pipeline is ready.")
    sys.exit(0)
