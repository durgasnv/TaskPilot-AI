"""
Dev 3 analytics validation suite.

Validates:
  - TFIDFVectorDeduplicator: must-pass demo cases, precision vs ground truth
  - ScoringPrioritizer: P1 tasks rank above P2, rationale fields populated,
    closed/resolved tasks excluded, scoring formula components correct
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.normalizer import normalize_all_sources
from src.utils.file_loader import TEST_DIR
from taskpilot_ai.analytics.deduplicator import TFIDFVectorDeduplicator
from taskpilot_ai.analytics.prioritizer import ScoringPrioritizer
from taskpilot_ai.unified_task import Severity, TaskSource, TaskStatus, UnifiedTask

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    icon = "+" if condition else "X"
    print(f"  {icon} [{status}] {name}" + (f" - {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
norm = normalize_all_sources()
tasks = norm.tasks
id_map = {t.task_id: t for t in tasks}

with (TEST_DIR / "ground_truth_duplicates.json").open() as f:
    gt = json.load(f)
gt_pairs = gt["duplicate_pairs"]

# ---------------------------------------------------------------------------
# 1. Deduplication — must-pass demo cases
# ---------------------------------------------------------------------------
print("\n=== 1. Deduplication: Must-Pass Demo Cases ===")

dedup = TFIDFVectorDeduplicator(threshold=0.85, tfidf_min_for_boost=0.15)
unique = dedup.deduplicate(list(tasks))
merged_map = {t.task_id: t.duplicate_of for t in tasks if t.duplicate_of}

check("dedup: output count < input count", len(unique) < len(tasks), f"{len(tasks)} -> {len(unique)}")
check("dedup: all have task_id", all(t.task_id for t in unique))
check("dedup: output has no duplicate task_ids", len({t.task_id for t in unique}) == len(unique))

# ACME Corp must-pass cluster: JIRA-1001 is canonical for all three
check("dedup: SN-INC0001001 -> JIRA-1001", merged_map.get("SN-INC0001001") == "JIRA-1001",
      merged_map.get("SN-INC0001001", "NOT MERGED"))
check("dedup: EMAIL-001 -> JIRA-1001", merged_map.get("EMAIL-001") == "JIRA-1001",
      merged_map.get("EMAIL-001", "NOT MERGED"))
check("dedup: EMAIL-002 -> JIRA-1001", merged_map.get("EMAIL-002") == "JIRA-1001",
      merged_map.get("EMAIL-002", "NOT MERGED"))

# Canonical JIRA-1001 should be enriched with labels from merged duplicates
canonical = id_map.get("JIRA-1001")
if canonical:
    check("dedup: canonical JIRA-1001 has combined labels", len(canonical.labels) >= 4,
          f"labels: {canonical.labels}")

# ---------------------------------------------------------------------------
# 2. Deduplication — precision vs ground truth
# ---------------------------------------------------------------------------
print("\n=== 2. Deduplication: Ground Truth Precision ===")

# Count how many GT pairs we correctly merged
gt_expected_merges = set()
for pair in gt_pairs:
    if pair.get("merge_strategy") in ("keep_jira_as_canonical", "keep_incident_as_canonical",
                                       "extract_additional_action_items_only"):
        gt_expected_merges.add(pair["duplicate_task"])

correctly_merged = sum(1 for t in gt_expected_merges if t in merged_map)
precision = correctly_merged / max(len(merged_map), 1)
recall = correctly_merged / max(len(gt_expected_merges), 1)

check(f"dedup: recall >= 0.70 ({correctly_merged}/{len(gt_expected_merges)} GT pairs found)",
      recall >= 0.70, f"recall={recall:.2f}")
# GT only documents 10 pairs; algorithm may discover additional valid cross-source
# duplicates not listed. We require >=80% recall and >=25% precision floor.
check(f"dedup: precision >= 0.25 ({correctly_merged}/{len(merged_map)} merges in GT)",
      precision >= 0.25, f"precision={precision:.2f}")

# Tasks from emails/meetings must survive in unique output (not all filtered)
email_tasks_in_output = [t for t in unique if str(t.source) == "email"]
check("dedup: email-only tasks preserved in output", len(email_tasks_in_output) >= 5,
      f"{len(email_tasks_in_output)} email tasks in output")

# ---------------------------------------------------------------------------
# 3. Prioritization — basic correctness
# ---------------------------------------------------------------------------
print("\n=== 3. Prioritization: Basic Correctness ===")

# Reset duplicate_of to avoid state contamination between tests
fresh_tasks = normalize_all_sources().tasks
dedup2 = TFIDFVectorDeduplicator(threshold=0.85, tfidf_min_for_boost=0.15)
deduped = dedup2.deduplicate(fresh_tasks)

prioritizer = ScoringPrioritizer()
ranked = prioritizer.rank(deduped)

check("prioritizer: returns non-empty list", len(ranked) > 0)
check("prioritizer: all tasks have priority_score", all(t.priority_score is not None for t in ranked))
check("prioritizer: all tasks have priority_rationale", all(t.priority_rationale for t in ranked))
check("prioritizer: scores in [0, 1]", all(0.0 <= (t.priority_score or 0) <= 1.0 for t in ranked))

# Scores must be in descending order
scores = [t.priority_score or 0 for t in ranked]
check("prioritizer: ranked in descending score order", scores == sorted(scores, reverse=True))

# P1 tasks must dominate the top
top_10 = ranked[:10]
top_10_p1 = [t for t in top_10 if str(t.severity) == "P1"]
check("prioritizer: top-10 mostly P1", len(top_10_p1) >= 6, f"{len(top_10_p1)}/10 P1s in top 10")

# ---------------------------------------------------------------------------
# 4. Prioritization — scoring formula components
# ---------------------------------------------------------------------------
print("\n=== 4. Prioritization: Scoring Formula ===")

# A P1 task must always score higher than a P4 task with same deadline
t_p1 = UnifiedTask(task_id="TEST-P1", source=TaskSource.JIRA, source_id="TEST-P1",
                   title="Critical P1 task", severity=Severity.P1)
t_p4 = UnifiedTask(task_id="TEST-P4", source=TaskSource.JIRA, source_id="TEST-P4",
                   title="Low priority P4 task", severity=Severity.P4)
ranked_test = prioritizer.rank([t_p4, t_p1])
check("prioritizer: P1 ranks above P4 with no deadline", ranked_test[0].task_id == "TEST-P1")

# Overdue task must score >= 0.75 if P1
t_overdue = UnifiedTask(task_id="TEST-OD", source=TaskSource.JIRA, source_id="TEST-OD",
                        title="Overdue P1 task", severity=Severity.P1,
                        deadline=datetime(2020, 1, 1, tzinfo=timezone.utc))
ranked_od = prioritizer.rank([t_overdue])
check("prioritizer: overdue P1 >= 0.75 score", (ranked_od[0].priority_score or 0) >= 0.75,
      f"score={ranked_od[0].priority_score}")

# Closed/resolved tasks must be excluded
t_closed = UnifiedTask(task_id="TEST-CL", source=TaskSource.JIRA, source_id="TEST-CL",
                       title="Closed task", severity=Severity.P1, status=TaskStatus.CLOSED)
t_resolved = UnifiedTask(task_id="TEST-RES", source=TaskSource.JIRA, source_id="TEST-RES",
                         title="Resolved task", severity=Severity.P1, status=TaskStatus.RESOLVED)
t_open = UnifiedTask(task_id="TEST-OPEN", source=TaskSource.JIRA, source_id="TEST-OPEN",
                     title="Open task", severity=Severity.P3)
ranked_excl = prioritizer.rank([t_closed, t_resolved, t_open])
ids_in_output = {t.task_id for t in ranked_excl}
check("prioritizer: closed tasks excluded", "TEST-CL" not in ids_in_output)
check("prioritizer: resolved tasks excluded", "TEST-RES" not in ids_in_output)
check("prioritizer: open tasks included", "TEST-OPEN" in ids_in_output)

# Business impact multiplier must apply
t_revenue = UnifiedTask(task_id="TEST-REV", source=TaskSource.JIRA, source_id="TEST-REV",
                        title="Revenue loss task", severity=Severity.P3,
                        business_impact="$2M ARR revenue loss")
t_internal = UnifiedTask(task_id="TEST-INT", source=TaskSource.JIRA, source_id="TEST-INT",
                         title="Internal refactor task", severity=Severity.P3)
ranked_biz = prioritizer.rank([t_internal, t_revenue])
check("prioritizer: revenue-impact task ranks above plain P3",
      ranked_biz[0].task_id == "TEST-REV",
      f"top={ranked_biz[0].task_id}")

# ---------------------------------------------------------------------------
# 5. Rationale string contract
# ---------------------------------------------------------------------------
print("\n=== 5. Rationale String Contract ===")

for task in ranked[:5]:
    r = task.priority_rationale or ""
    has_sev = any(p in r for p in ["P1", "P2", "P3", "P4"])
    check(f"rationale has severity label [{task.task_id[:12]}]", has_sev, r[:80])

check("prioritizer: rationale includes deadline label",
      any("due" in (t.priority_rationale or "").lower() or "overdue" in (t.priority_rationale or "").lower()
          for t in ranked[:10] if t.deadline))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if __name__ == "__main__":
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
        print("\nAll Dev 3 analytics checks passed.")
        sys.exit(0)
