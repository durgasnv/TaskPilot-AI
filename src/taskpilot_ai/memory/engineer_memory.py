"""Persistent engineer-preference memory for adaptive task prioritization."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_PATH = Path("data/memory/preferences.json")
_SNOOZE_PENALTY = -0.35
_BOOST_BONUS    =  0.20
_DEPRIOR_PENALTY = -0.15


class EngineerMemory:
    """
    Reads/writes engineer feedback to a JSON file and applies score adjustments
    during prioritization so the agent learns from every interaction.
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self.path = Path(path)
        self._data: dict[str, Any] = self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "snoozed_ids": [],
            "boosted_ids": [],
            "deprioritized_ids": [],
            "boosted_labels": [],
            "deprioritized_labels": [],
            "interaction_log": [],
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    # ── feedback actions ──────────────────────────────────────────────────────

    def snooze(self, task_id: str) -> None:
        ids = self._data.setdefault("snoozed_ids", [])
        if task_id not in ids:
            ids.append(task_id)
        self._data.setdefault("boosted_ids", [])
        if task_id in self._data["boosted_ids"]:
            self._data["boosted_ids"].remove(task_id)
        self._log(task_id, "snooze")
        self.save()

    def boost(self, task_id: str) -> None:
        ids = self._data.setdefault("boosted_ids", [])
        if task_id not in ids:
            ids.append(task_id)
        self._data.setdefault("snoozed_ids", [])
        if task_id in self._data["snoozed_ids"]:
            self._data["snoozed_ids"].remove(task_id)
        self._log(task_id, "boost")
        self.save()

    def deprioritize(self, task_id: str) -> None:
        ids = self._data.setdefault("deprioritized_ids", [])
        if task_id not in ids:
            ids.append(task_id)
        self._log(task_id, "deprioritize")
        self.save()

    def undo(self, task_id: str) -> None:
        for key in ("snoozed_ids", "boosted_ids", "deprioritized_ids"):
            lst = self._data.setdefault(key, [])
            if task_id in lst:
                lst.remove(task_id)
        self._log(task_id, "undo")
        self.save()

    def _log(self, task_id: str, action: str) -> None:
        log = self._data.setdefault("interaction_log", [])
        log.append({
            "task_id": task_id,
            "action": action,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self._data["interaction_log"] = log[-200:]

    # ── score adjustment (called by PrioritizationAgent) ─────────────────────

    def apply_adjustments(
        self, tasks: list  # list[UnifiedTask]
    ) -> tuple[list, list[str]]:
        """
        Mutates priority_score and priority_rationale in-place.
        Returns (tasks, trace_messages).
        """
        snoozed       = set(self._data.get("snoozed_ids", []))
        boosted       = set(self._data.get("boosted_ids", []))
        deprioritized = set(self._data.get("deprioritized_ids", []))

        adjusted = 0
        for task in tasks:
            base = task.priority_score or 0.0
            tag  = ""

            if task.task_id in snoozed:
                task.priority_score = max(0.0, base + _SNOOZE_PENALTY)
                tag = "[memory: snoozed] "
                adjusted += 1
            elif task.task_id in boosted:
                task.priority_score = min(1.0, base + _BOOST_BONUS)
                tag = "[memory: boosted ↑] "
                adjusted += 1
            elif task.task_id in deprioritized:
                task.priority_score = max(0.0, base + _DEPRIOR_PENALTY)
                tag = "[memory: deprioritized ↓] "
                adjusted += 1

            if tag:
                task.priority_rationale = tag + (task.priority_rationale or "")

        total = len(snoozed) + len(boosted) + len(deprioritized)
        msgs = [
            f"Memory: {total} preference(s) on record "
            f"({len(snoozed)} snoozed, {len(boosted)} boosted, {len(deprioritized)} deprioritized) — "
            f"{adjusted} task(s) re-scored this run."
            if total
            else "Memory: no preferences recorded yet — scores unmodified."
        ]
        return tasks, msgs

    # ── introspection ─────────────────────────────────────────────────────────

    @property
    def summary(self) -> dict[str, int]:
        return {
            "snoozed":       len(self._data.get("snoozed_ids", [])),
            "boosted":       len(self._data.get("boosted_ids", [])),
            "deprioritized": len(self._data.get("deprioritized_ids", [])),
            "interactions":  len(self._data.get("interaction_log", [])),
        }

    def get_status_for(self, task_id: str) -> str | None:
        """Returns 'snoozed'|'boosted'|'deprioritized'|None for a task."""
        if task_id in self._data.get("snoozed_ids", []):
            return "snoozed"
        if task_id in self._data.get("boosted_ids", []):
            return "boosted"
        if task_id in self._data.get("deprioritized_ids", []):
            return "deprioritized"
        return None

    def recent_interactions(self, n: int = 10) -> list[dict]:
        return list(reversed(self._data.get("interaction_log", [])[-n:]))
