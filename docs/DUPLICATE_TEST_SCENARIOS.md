# Duplicate Test Scenarios

Cross-system duplicate scenarios planted in the mock data. Dev 3 builds the dedup engine against these; Dev 5 measures accuracy against them.

---

## Scenario 1 — ACME Corp File Upload (4-way cluster)

**The most important demo scenario. Must work perfectly.**

| task_id | Source | Relationship |
|---|---|---|
| `JIRA-1001` | Jira | **Canonical** — authoritative record |
| `SN-INC0001001` | ServiceNow | Exact same issue — filed as incident |
| `EMAIL-001` | Email | VP escalation email about the same issue |
| `EMAIL-002` | Email | ACME Corp customer email about the same issue |

**Shared signals across all four:**
- "file upload" + "timeout" / "504" in all
- "ACME Corp" in all
- Same deadline (June 20 EOD)
- Same assignee (alice)

**Expected merged result:**
```python
UnifiedTask(
    task_id="JIRA-1001",           # canonical
    title="Fix file upload timeout on large attachments (>50 MB)",
    severity="P1",
    deadline=datetime(2026, 6, 20, 17, 0),
    related_tasks=["SN-INC0001001", "EMAIL-001", "EMAIL-002"],
    business_impact="ACME Corp ($2M ARR) threatening churn. VP of Engineering alerted. Customer SLA breach clause 7.3 active.",
    labels=["upload", "timeout", "customer-escalation", "vp-escalation", "acme", "sla", "revenue-impact"],
)
# SN-INC0001001, EMAIL-001, EMAIL-002 each get: duplicate_of="JIRA-1001"
```

---

## Scenario 2 — AWS Credential Exposure (3-way cluster)

| task_id | Source | Relationship |
|---|---|---|
| `JIRA-1006` | Jira | **Canonical** |
| `SN-INC0001003` | ServiceNow | Exact same security incident |
| `EMAIL-003` | Email | Security team alert email about same commit |

**Shared signals:** "commit abc1234", "AWS credentials", "alice.chen", noon TODAY deadline

**Expected merge:** Keep JIRA-1006 canonical. Extract additional action items from EMAIL-003 (`raw_text`): BFG cleanup, CloudTrail review, ServiceNow report.

---

## Scenario 3 — Mobile Auth Silent Logout (2-way)

| task_id | Source | Relationship |
|---|---|---|
| `JIRA-1002` | Jira | **Canonical** |
| `SN-INC0001004` | ServiceNow | Same issue — 47 support tickets |

**Shared signals:** "mobile authentication", "silent logout", "12% DAU", same assignee (carol), same deadline (June 22)

---

## Scenario 4 — DB Connection Pool Exhaustion (2-way)

| task_id | Source | Relationship |
|---|---|---|
| `JIRA-1003` | Jira | **Canonical** |
| `SN-INC0001005` | ServiceNow | Same production incident |

**Shared signals:** "connection pool", "100 connections", "PagerDuty", SRE reporter (dan), same deadline (June 21)

---

## Scenario 5 — API Latency / GlobalTech SLA (2-way + email confirmation)

| task_id | Source | Relationship |
|---|---|---|
| `JIRA-1017` | Jira | **Canonical** |
| `SN-INC0001002` | ServiceNow | Same SLA breach |
| `EMAIL-020` | Email | CSM email confirming $50K penalty, same issue |

**Shared signals:** "480ms", "200ms SLA", "GlobalTech", same assignee (george)

---

## Scenario 6 — CVE / Log4js Patch (overlapping, not exact duplicate)

| task_id | Source | Relationship |
|---|---|---|
| `JIRA-1013` | Jira | Parent: all 7 HIGH CVEs |
| `SN-INC0001007` | ServiceNow | Child: log4js CVE-2026-31240 specifically |

**Note:** These are RELATED, not exact duplicates. The dedup engine should set `related_tasks` rather than `duplicate_of`. Both stay in the task list with a link between them.

---

## Scenario 7 — GDPR Deletion (email + incident)

| task_id | Source | Relationship |
|---|---|---|
| `SN-INC0001011` | ServiceNow | **Canonical** — formal incident |
| `EMAIL-005` | Email (manager 1:1 notes) | Confirms the same legal action item |
| `EMAIL-014` | Email (legal team direct) | Also confirms same deletion requirement |

**Shared signals:** "ACC-USER-55391" → `[EMPLOYEE_ID]` after scrubbing, "30-day deadline", "June 19", legal escalation

---

## Scenario 8 — Webhook Retry / Payment (PR → Incident)

| task_id | Source | Relationship |
|---|---|---|
| `JIRA-1022` | Jira | PR review task |
| `SN-INC0001008` | ServiceNow | Business incident caused by the same bug |

**Note:** These are linked (the PR is the fix for the incident) but not duplicates. Link as `related_tasks`. Both remain in the task list.

---

## Boundary Cases (Should NOT be merged)

| Pair | Why they might look similar | Why they should NOT merge |
|---|---|---|
| `JIRA-1003` + `JIRA-1004` | Both about database, same team | Different issues: exhaustion vs. read-replica implementation |
| `JIRA-1002` + `JIRA-1018` | Both mobile auth | Different: token refresh (1002) vs. biometric re-auth (1018) |
| `JIRA-1011` + `JIRA-1015` | Both notification service | Different: memory leak (1011) vs. GraphQL migration (1015) |
| `EMAIL-009` + `EMAIL-013` | Both mention JIRA-1003 | Different emails: one is incident review scheduling, one is standup notes |

The dedup engine must NOT merge these. False positives here would cause visible data loss in the demo.
