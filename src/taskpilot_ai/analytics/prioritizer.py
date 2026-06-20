"""
Multi-factor scoring prioritizer implementing PrioritizerProtocol.

Formula (from DEV3_ANALYTICS_HANDOFF.md):
    priority_score = (deadline_urgency * 0.40)
                   + (severity_weight  * 0.35)
                   + (dependency_impact * 0.15)
                   + (business_impact_m * 0.10)

All component values are in [0.0, 1.0] except business_impact_m which
is in [1.0, 1.5]; final score is capped at 1.0.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from taskpilot_ai.unified_task import Severity, TaskStatus, UnifiedTask

# --- Scoring constants (from handoff doc) ---

_SEVERITY_WEIGHTS: dict[str, float] = {"P1": 1.0, "P2": 0.7, "P3": 0.4, "P4": 0.1}

_BUSINESS_KEYWORDS: list[tuple[float, list[str]]] = [
    (1.5, ["revenue_loss", "revenue loss", "payment down", "$", "payment failed", "arr at risk"]),
    (1.4, ["gdpr", "legal", "compliance", "audit", "erasure", "fine", "penalty"]),
    (1.3, ["vp-escalation", "vp escalation", "executive", "vp james", "c-suite"]),
    (1.2, ["customer-escalation", "customer escalation", "churn", "acme", "globaltech"]),
]


def _deadline_urgency(deadline: Optional[datetime]) -> tuple[float, str]:
    if deadline is None:
        return 0.2, "no SLA deadline"
    dl = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    hours = (dl - datetime.now(timezone.utc)).total_seconds() / 3600
    if hours < 0:
        return 1.0, f"OVERDUE by {abs(int(hours))}h"
    if hours <= 4:
        return 1.0, f"due in {int(hours)}h (critical)"
    if hours <= 24:
        return 0.9, f"due in {int(hours)}h (today)"
    if hours <= 48:
        return 0.75, f"due in {int(hours)}h (tomorrow)"
    if hours <= 168:
        return 0.5, f"due in {int(hours / 24)}d"
    return 0.2, f"due in {int(hours / 24)}d"


def _severity_weight(task: UnifiedTask) -> tuple[float, str]:
    s = str(task.severity or "P3")
    w = _SEVERITY_WEIGHTS.get(s, 0.4)
    return w, f"{s} severity"


def _dependency_impact(task: UnifiedTask) -> tuple[float, str]:
    blocked = bool(task.blocked_by) or task.status == TaskStatus.BLOCKED
    n_blocks = len(task.blocks)
    base = min(1.0, n_blocks * 0.25)
    if blocked:
        base = max(0.0, base - 0.15)
    label_parts = []
    if n_blocks:
        label_parts.append(f"blocks {n_blocks} task(s)")
    if blocked:
        label_parts.append("currently blocked (-0.15)")
    return base, " | ".join(label_parts) if label_parts else "no dependencies"


def _business_impact_multiplier(task: UnifiedTask) -> tuple[float, str]:
    haystack = " ".join(filter(None, [
        task.business_impact or "",
        " ".join(task.labels),
    ])).lower()

    for multiplier, keywords in _BUSINESS_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return multiplier, kw.replace("_", " ")
    return 1.0, "internal"


def _tiebreak_key(task: UnifiedTask):
    dl = task.deadline
    if dl and dl.tzinfo is None:
        dl = dl.replace(tzinfo=timezone.utc)
    dl_ts = dl.timestamp() if dl else float("inf")
    sev_rank = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}.get(str(task.severity or "P3"), 2)
    return (dl_ts, sev_rank, -len(task.blocks), task.task_id)


def _build_rationale(
    sev_label: str,
    dl_label: str,
    dep_label: str,
    biz_label: str,
    biz_m: float,
    blocks: list[str],
) -> str:
    parts = [sev_label, dl_label]
    if biz_m > 1.0:
        parts.append(f"business impact: {biz_label} (×{biz_m})")
    if blocks:
        parts.append(f"unblocks: {', '.join(blocks[:3])}")
    elif dep_label != "no dependencies":
        parts.append(dep_label)
    return " | ".join(parts)


_EXCLUDED_STATUSES = {TaskStatus.RESOLVED, TaskStatus.CLOSED, "resolved", "closed"}


class ScoringPrioritizer:
    """
    Implements PrioritizerProtocol with the exact 4-factor formula from the
    Dev3 handoff document. Every score includes an auditable rationale string.
    """

    def rank(self, tasks: list[UnifiedTask]) -> list[UnifiedTask]:
        active = [t for t in tasks if t.status not in _EXCLUDED_STATUSES]

        scored: list[tuple[float, UnifiedTask]] = []
        for task in active:
            score, rationale = self._score(task)
            task.priority_score = score
            task.priority_rationale = rationale
            scored.append((score, task))

        scored.sort(key=lambda x: (-x[0], _tiebreak_key(x[1])))
        return [t for _, t in scored]

    def _score(self, task: UnifiedTask) -> tuple[float, str]:
        dl_u, dl_label = _deadline_urgency(task.deadline)
        sev_w, sev_label = _severity_weight(task)
        dep_i, dep_label = _dependency_impact(task)
        biz_m, biz_label = _business_impact_multiplier(task)

        raw = (dl_u * 0.40) + (sev_w * 0.35) + (dep_i * 0.15) + (biz_m * 0.10)
        score = round(min(1.0, raw), 4)

        rationale = _build_rationale(
            sev_label, dl_label, dep_label, biz_label, biz_m, task.blocks
        )
        return score, rationale
