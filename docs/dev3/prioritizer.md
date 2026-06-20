# ScoringPrioritizer — Formula & Design

**File:** `src/taskpilot_ai/analytics/prioritizer.py`  
**Implements:** `PrioritizerProtocol` from `src/taskpilot_ai/interfaces/protocols.py`

---

## Scoring Formula

```
priority_score = (deadline_urgency   * 0.40)
               + (severity_weight    * 0.35)
               + (dependency_impact  * 0.15)
               + (business_impact_m  * 0.10)
```

Final score is capped at `1.0`. All components are floats in `[0.0, 1.0]`
except `business_impact_m` which is `[1.0, 1.5]` (acts as a multiplier-contribution).

---

## Component Tables

### Severity Weight (`severity_weight`)

| Severity | Weight |
|---|---|
| P1 | 1.00 |
| P2 | 0.70 |
| P3 | 0.40 |
| P4 | 0.10 |
| None | 0.40 (P3 default) |

### Deadline Urgency (`deadline_urgency`)

Computed from `datetime.now(UTC)`:

| Time until deadline | Urgency | Label |
|---|---|---|
| Overdue (past) | 1.0 | "OVERDUE by Nh" |
| <= 4 hours | 1.0 | "due in Nh (critical)" |
| <= 24 hours | 0.9 | "due in Nh (today)" |
| <= 48 hours | 0.75 | "due in Nh (tomorrow)" |
| <= 1 week (168h) | 0.5 | "due in Nd" |
| > 1 week or None | 0.2 | "due in Nd" / "no SLA deadline" |

### Business Impact Multiplier (`business_impact_m`)

Scans `task.business_impact` and `task.labels` (lowercase):

| Keywords matched | Multiplier |
|---|---|
| revenue_loss, payment down, $, arr at risk | 1.5 |
| gdpr, legal, compliance, audit, fine, penalty | 1.4 |
| vp-escalation, vp escalation, executive, c-suite | 1.3 |
| customer-escalation, churn, acme, globaltech | 1.2 |
| (none of the above) | 1.0 |

First match wins (ordered by severity of impact).

### Dependency Impact (`dependency_impact`)

```python
base = min(1.0, len(task.blocks) * 0.25)
if task.blocked_by or task.status == "blocked":
    base = max(0.0, base - 0.15)  # penalty for being blocked
```

A task that blocks 4+ others scores 1.0 on this component (contributes 0.15 to total).

---

## Rationale String Format

Every ranked task gets a `priority_rationale` string. Required elements:

```
"P1 severity | due in 6h (today) | business impact: $ (x1.5) | unblocks: JIRA-1012"
```

Format: `<severity> | <deadline label> [| <business impact>] [| <dependency note>]`

The `|`-delimited format makes it easy to parse in the chat interface for query
responses like "Why is task X ranked #1?"

---

## Edge Cases

| Scenario | Behaviour |
|---|---|
| `status == "closed"` or `"resolved"` | Excluded from output entirely |
| `deadline == None` | Urgency = 0.2 (not excluded) |
| Score tie | Tiebreak: earliest deadline → highest severity → most blocks → alpha task_id |
| `blocked_by` non-empty | `dependency_impact` reduced by 0.15 |

---

## Example Scores (live data, 2026-06-20)

```
[P1] Fix file upload timeout (ACME Corp)
     Score: 0.8975 | P1 severity | due in 6h (today) | business impact: $ (x1.5)

[P1] GDPR data deletion — legal deadline TODAY
     Score: 0.8900 | P1 severity | OVERDUE by 17h | business impact: gdpr (x1.4)

[P1] Security: Rotate API keys (commit abc1234)
     Score: 0.8500 | P1 severity | OVERDUE by Nh
```

---

## Integration

```python
from taskpilot_ai.analytics import ScoringPrioritizer
from taskpilot_ai.agents.specialists import PrioritizationAgent

agent = PrioritizationAgent(engine=ScoringPrioritizer())
state = agent.run(state)
# state.ranked_tasks is sorted by priority_score descending
# Each task has priority_score (float) and priority_rationale (str)
```
