"""Specialist agents for the TaskPilot orchestration pipeline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from taskpilot_ai.agents.base import Agent
from taskpilot_ai.agents.react_runtime import build_extraction_packet, build_ingestion_packet
from taskpilot_ai.config import AppConfig
from taskpilot_ai.interfaces.protocols import VectorDeduplicatorProtocol, PrioritizerProtocol
from taskpilot_ai.llm.client import LLMClient, MockLLMClient
from taskpilot_ai.models import FileSource
from taskpilot_ai.orchestration.state import WorkflowState
from taskpilot_ai.tools.source_reader import FileSystemSourceReader, NormalizerSourceReader, SourceReader
from taskpilot_ai.unified_task import Severity, TaskSource, UnifiedTask


# Maps our internal FileSource names to UnifiedTask TaskSource enum values.
_SOURCE_MAP: dict[str, TaskSource] = {
    FileSource.JIRA.value: TaskSource.JIRA,
    FileSource.SERVICENOW.value: TaskSource.SERVICENOW,
    FileSource.OUTLOOK.value: TaskSource.EMAIL,
    FileSource.MEETING_NOTES.value: TaskSource.TRANSCRIPT,
    FileSource.INJECTED.value: TaskSource.SERVICENOW,  # runtime drops default to incident-type
}

# Named sub-agents for the multi-agent architecture.
# Includes both FileSource values and the normalizer's short source keys.
_AGENT_META: dict[str, tuple[str, str]] = {
    FileSource.JIRA.value:          ("jira-agent",     "Jira Board Analyst"),
    FileSource.SERVICENOW.value:    ("sn-agent",       "IT Ops Incident Agent"),
    FileSource.OUTLOOK.value:       ("email-agent",    "Email Intelligence Agent"),
    FileSource.MEETING_NOTES.value: ("meeting-agent",  "Meeting Transcript Analyst"),
    FileSource.INJECTED.value:      ("incident-agent", "Emergency Injection Handler"),
    # Normalizer uses these short keys in source_counts
    "email":      ("email-agent",    "Email Intelligence Agent"),
    "transcript": ("meeting-agent",  "Meeting Transcript Analyst"),
    "injected":   ("incident-agent", "Emergency Injection Handler"),
}


def _parse_unified_tasks(llm_output: str, source: FileSource) -> list[UnifiedTask]:
    """Parse LLM JSON response into UnifiedTask objects.

    Handles free-form responses: strips markdown fences and extracts the first
    JSON array found in the text (LLMs often wrap output in ReAct prose or
    code blocks before the actual array).
    """
    content = llm_output.strip()
    # Strip markdown code fences
    content = re.sub(r"```(?:json)?\s*", "", content)
    content = re.sub(r"```", "", content).strip()
    # Extract the outermost JSON array
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end > start:
        content = content[start : end + 1]
    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        return []

    unified_source = _SOURCE_MAP.get(source.value, TaskSource.JIRA)
    tasks = []
    for item in items:
        try:
            tasks.append(
                UnifiedTask(
                    task_id=item.get("task_id", "UNKNOWN"),
                    source=unified_source,
                    source_id=item.get("source_id", item.get("task_id", "UNKNOWN")),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    severity=item.get("severity"),
                    deadline=item.get("deadline"),
                    blocked_by=item.get("blocked_by", []),
                    blocks=item.get("blocks", []),
                    business_impact=item.get("business_impact"),
                    extracted=item.get("extracted", False),
                )
            )
        except Exception:
            continue
    return tasks


def _score_task(task: UnifiedTask) -> tuple[float, str]:
    """Compute a priority score (0-100) and plain-English rationale for a task."""
    score = 0.0
    reasons: list[str] = []

    # Severity — 40 pts max
    sev_pts = {"P1": 40.0, "P2": 30.0, "P3": 15.0, "P4": 5.0}
    s = str(task.severity or "P3")
    pts = sev_pts.get(s, 10.0)
    score += pts
    reasons.append(f"{s} severity ({pts:.0f} pts)")

    # Deadline proximity — 30 pts max
    if task.deadline:
        dl = task.deadline
        if dl.tzinfo is None:
            dl = dl.replace(tzinfo=timezone.utc)
        days = (dl - datetime.now(timezone.utc)).total_seconds() / 86400
        if days < 0:
            dl_pts, label = 30.0, "overdue"
        elif days < 1:
            dl_pts, label = 28.0, "due today"
        elif days < 2:
            dl_pts, label = 22.0, "due tomorrow"
        elif days < 4:
            dl_pts, label = 15.0, f"due in {int(days)} days"
        elif days < 8:
            dl_pts, label = 8.0, f"due in {int(days)} days"
        else:
            dl_pts, label = 3.0, f"due in {int(days)} days"
        score += dl_pts
        reasons.append(f"{label} ({dl_pts:.0f} pts)")

    # Blocks other tasks — 20 pts max
    if task.blocks:
        blk_pts = min(20.0, len(task.blocks) * 7.0)
        score += blk_pts
        reasons.append(f"blocks {len(task.blocks)} task(s) ({blk_pts:.0f} pts)")

    # Business impact — 10 pts
    if task.business_impact and len(task.business_impact.strip()) > 5:
        score += 10.0
        reasons.append(f"business impact: {task.business_impact[:80]}")

    rationale = " | ".join(reasons)
    return round(score, 1), rationale


_DEDUP_STOPWORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'for',
    'to', 'of', 'and', 'or', 'but', 'with', 'from', 'that', 'this', 'by',
    'be', 'has', 'have', 'been', 'will', 'not', 'all', 'we', 'our', 'your',
    'my', 'its', 'it', 'do', 're', 'up', 'as', 'no', 'due', 'new', 'via',
    'get', 'set', 'run', 'per', 'its', 'also', 'into', 'than', 'then',
}


def _basic_keyword_dedup(tasks: list[UnifiedTask]) -> list[UnifiedTask]:
    """
    Title-keyword deduplication fallback for when Dev3's vector engine isn't available.
    Two tasks sharing 2+ significant words in their TITLES are considered duplicates.
    Descriptions are intentionally excluded — they contain too many generic words.
    The first-seen task is kept as canonical; later duplicates get duplicate_of set.
    """
    def title_kw(task: UnifiedTask) -> set[str]:
        words = re.sub(r"[^a-z0-9\s]", " ", task.title.lower()).split()
        return {w for w in words if len(w) > 2 and w not in _DEDUP_STOPWORDS}

    kw_cache = {t.task_id: title_kw(t) for t in tasks}
    duplicate_of: dict[str, str] = {}

    for i, ti in enumerate(tasks):
        if ti.task_id in duplicate_of:
            continue
        for tj in tasks[i + 1:]:
            if tj.task_id in duplicate_of:
                continue
            shared = kw_cache[ti.task_id] & kw_cache[tj.task_id]
            if len(shared) >= 2:
                duplicate_of[tj.task_id] = ti.task_id
                tj.duplicate_of = ti.task_id

    return [t for t in tasks if t.task_id not in duplicate_of]


def _build_email_source_doc(
    email_path: str = "data/raw/outlook_inbox.json",
    max_emails: int = 8,
) -> "SourceDocument | None":
    """
    Read the email inbox and strip pre-labeled hidden_action_items so the LLM
    must find action items from the raw email body — not from pre-labeled fields.
    """
    import json as _json
    from pathlib import Path as _Path

    path = _Path(email_path)
    if not path.exists():
        return None

    data = _json.loads(path.read_text(encoding="utf-8"))
    _SKIP = {"hidden_action_items", "related_jira", "related_incident"}
    stripped_emails = [
        {k: v for k, v in email.items() if k not in _SKIP}
        for email in data.get("emails", [])[:max_emails]
    ]
    content = _json.dumps(
        {"mailbox": data.get("mailbox"), "emails": stripped_emails},
        indent=2,
    )

    from taskpilot_ai.models import SourceDocument, FileSource
    return SourceDocument(
        source=FileSource.OUTLOOK,
        content=content,
        location=email_path,
    )


class AgentMode(str, Enum):
    REACT = "react"


@dataclass(slots=True)
class IngestionAgent(Agent):
    name: str = "ingestion"
    config: AppConfig = field(default_factory=AppConfig)
    reader: SourceReader = field(default_factory=FileSystemSourceReader)
    mode: AgentMode = AgentMode.REACT

    def run(self, state: WorkflowState) -> WorkflowState:
        # Bulk path: Dev1's normalizer handles all parsing and PII scrubbing in one call.
        if isinstance(self.reader, NormalizerSourceReader):
            result = self.reader.load_all()
            for err in result.errors:
                state.trace(self.name, f"Normalizer warning: {err}")

            # Structured sources (Jira, ServiceNow, meetings) go directly to extracted_tasks.
            # Email tasks are routed through ExtractionAgent so the LLM reads the body text
            # and extracts action items — rather than reading pre-labeled hidden_action_items.
            non_email = [t for t in result.tasks if t.source != TaskSource.EMAIL]
            email_count = len(result.tasks) - len(non_email)
            state.extracted_tasks.extend(non_email)

            if email_count > 0:
                email_doc = _build_email_source_doc()
                if email_doc is not None:
                    state.raw_inputs[FileSource.OUTLOOK.value] = email_doc
                    state.memory.source_locations[FileSource.OUTLOOK.value] = (
                        email_doc.location or "inline"
                    )

            for src, count in result.source_counts.items():
                state.memory.source_locations[src] = f"data/raw/{src}"

            # Build agents roster for all active sources (Feature 1)
            for src_key, count in result.source_counts.items():
                if count > 0:
                    agent_name, agent_role = _AGENT_META.get(
                        src_key, (f"{src_key}-agent", src_key.title())
                    )
                    state.agents_roster.append({
                        "name": agent_name,
                        "role": agent_role,
                        "source": src_key,
                        "tasks_found": count,
                    })
                    state.trace(agent_name, f"{agent_role} — parsed {count} item(s) from {src_key}.")

            state.trace(
                self.name,
                f"Normalizer loaded {len(non_email)} structured tasks; "
                f"{email_count} email(s) queued for LLM extraction.",
            )
            return state

        # Per-file path: FileSystemSourceReader reads raw files one at a time.
        for source_config in self.config.sources:
            if not source_config.enabled:
                continue

            source = FileSource(source_config.name)
            result = self.reader.read(
                source=source,
                location=source_config.path,
                retries=source_config.retries,
            )
            if result.document:
                state.raw_inputs[source.value] = result.document
                state.memory.source_locations[source.value] = result.document.location or "inline"
                packet = build_ingestion_packet(result.document)
                state.memory.react_scratchpad.append(
                    f"{self.name}:{source.value}:{packet.system_prompt}"
                )
                state.trace(self.name, f"Loaded source '{source.value}' from file dependency.")
            else:
                state.trace(
                    self.name,
                    f"Skipped source '{source.value}': {result.error}",
                )
        return state


@dataclass(slots=True)
class ExtractionAgent(Agent):
    name: str = "extraction"
    mode: AgentMode = AgentMode.REACT
    llm: LLMClient = field(default_factory=MockLLMClient)

    def run(self, state: WorkflowState) -> WorkflowState:
        # Register all active sub-agents in the roster before processing
        active_agents = []
        for key in state.raw_inputs:
            agent_name, agent_role = _AGENT_META.get(key, (f"{key}-agent", key.title()))
            active_agents.append({"name": agent_name, "role": agent_role, "source": key})
        if active_agents:
            # Merge with sources already registered by IngestionAgent
            existing_names = {a["name"] for a in state.agents_roster}
            for a in active_agents:
                if a["name"] not in existing_names:
                    state.agents_roster.append(a)
            state.trace(
                self.name,
                f"Spawning {len(active_agents)} source agent(s): "
                + ", ".join(a["name"] for a in active_agents),
            )

        for file_source_key, document in state.raw_inputs.items():
            agent_name, agent_role = _AGENT_META.get(
                file_source_key, (f"{file_source_key}-agent", file_source_key.title())
            )
            state.trace(agent_name, f"Initializing — role: {agent_role}")

            packet = build_extraction_packet(document)
            state.memory.react_scratchpad.append(
                f"{agent_name}:{file_source_key}:{packet.user_prompt[:120]}"
            )

            state.trace(agent_name, "Scanning source document for actionable tasks...")
            response = self.llm.complete(packet.system_prompt, packet.user_prompt)
            tasks = _parse_unified_tasks(response.content, document.source)
            state.extracted_tasks.extend(tasks)

            # Source-specific completion summary
            by_sev: dict[str, int] = {}
            for t in tasks:
                s = str(t.severity or "P3")
                by_sev[s] = by_sev.get(s, 0) + 1
            sev_summary = ", ".join(
                f"{by_sev[k]} {k}" for k in ["P1", "P2", "P3", "P4"] if k in by_sev
            )
            state.trace(
                agent_name,
                f"Complete — {len(tasks)} task(s) extracted"
                + (f" ({sev_summary})" if sev_summary else "")
                + f" via {response.model}.",
            )

        state.memory.extracted_task_ids.update(t.task_id for t in state.extracted_tasks)
        if not state.raw_inputs:
            state.trace(self.name, "No source documents loaded; skipping LLM extraction.")
        return state


@dataclass(slots=True)
class DeduplicationAgent(Agent):
    name: str = "deduplication"
    engine: VectorDeduplicatorProtocol | None = None

    def run(self, state: WorkflowState) -> WorkflowState:
        if self.engine is not None:
            state.deduplicated_tasks = self.engine.deduplicate(state.extracted_tasks)
            state.trace(
                self.name,
                f"Deduplication via engine reduced to {len(state.deduplicated_tasks)} task(s).",
            )
        else:
            if not state.deduplicated_tasks:
                before = len(state.extracted_tasks)
                state.deduplicated_tasks = _basic_keyword_dedup(state.extracted_tasks)
                removed = before - len(state.deduplicated_tasks)
                state.trace(
                    self.name,
                    f"Keyword dedup: {before} → {len(state.deduplicated_tasks)} tasks "
                    f"({removed} duplicates merged). Dev3 will replace with vector engine.",
                )
        return state


@dataclass(slots=True)
class PrioritizationAgent(Agent):
    name: str = "prioritization"
    engine: PrioritizerProtocol | None = None

    def run(self, state: WorkflowState) -> WorkflowState:
        if self.engine is not None:
            state.ranked_tasks = self.engine.rank(state.deduplicated_tasks)
        else:
            if not state.ranked_tasks:
                for task in state.deduplicated_tasks:
                    task.priority_score, task.priority_rationale = _score_task(task)
                state.ranked_tasks = sorted(
                    state.deduplicated_tasks,
                    key=lambda t: -(t.priority_score or 0.0),
                )

        if state.emergency_mode:
            state.ranked_tasks.sort(
                key=lambda t: (0 if (t.severity or "") == Severity.P1 else 1, -(t.priority_score or 0.0))
            )
            state.trace(self.name, "Emergency mode: P1 tasks sorted to top.")

        # Apply engineer memory adjustments (Feature 2: memory & learning)
        try:
            from pathlib import Path as _Path
            from taskpilot_ai.memory.engineer_memory import EngineerMemory
            mem = EngineerMemory(_Path("data/memory/preferences.json"))
            state.ranked_tasks, mem_traces = mem.apply_adjustments(state.ranked_tasks)
            # Re-sort after adjustments
            state.ranked_tasks.sort(key=lambda t: -(t.priority_score or 0.0))
            if state.emergency_mode:
                state.ranked_tasks.sort(
                    key=lambda t: (0 if str(t.severity or "") == "P1" else 1, -(t.priority_score or 0.0))
                )
            for msg in mem_traces:
                state.trace("memory-agent", msg)
        except Exception:
            pass

        state.memory.ranked_task_ids = [t.task_id for t in state.ranked_tasks]
        state.trace(self.name, f"Ranked {len(state.ranked_tasks)} task(s).")

        # Build team view (Feature 3: team dashboard)
        state.team_view = _build_team_view(state.ranked_tasks)

        return state


def _build_team_view(tasks: list) -> dict:
    """Aggregate task metrics by assignee for the team dashboard."""
    view: dict[str, dict] = {}
    for task in tasks:
        assignee = str(getattr(task, "assignee", None) or "unassigned")
        if assignee not in view:
            view[assignee] = {"total": 0, "p1": 0, "p2": 0, "p3": 0, "p4": 0, "blocked": 0, "tasks": []}
        e = view[assignee]
        e["total"] += 1
        sev = str(task.severity or "P3").lower()
        if sev in e:
            e[sev] += 1
        if task.blocked_by:
            e["blocked"] += 1
        e["tasks"].append({"task_id": str(task.task_id), "title": str(task.title)[:60], "severity": str(task.severity or "P3")})
    return view


def _build_calendar_blocks(tasks: list) -> list[dict]:
    """
    Read today's calendar and slot priority tasks into available focus windows.
    Returns a list of time blocks: meetings + focus windows with assigned tasks.
    """
    import json as _json
    from pathlib import Path as _Path

    cal_path = _Path("data/raw/calendar.json")
    if not cal_path.exists():
        return []

    try:
        cal = _json.loads(cal_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    def to_mins(t: str) -> int:
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    def to_str(mins: int) -> str:
        return f"{mins // 60:02d}:{mins % 60:02d}"

    work_start = to_mins(cal.get("work_start", "09:00"))
    work_end   = to_mins(cal.get("work_end",   "18:00"))

    # Sort events by start time; skip breaks for gap calculation
    events = sorted(
        [e for e in cal.get("events", []) if e.get("type") in ("meeting",)],
        key=lambda e: to_mins(e["start"]),
    )

    blocks: list[dict] = []
    cursor = work_start
    p_tasks = [t for t in tasks if str(t.severity or "P3") in ("P1", "P2")]
    task_idx = 0

    for ev in events:
        ev_start = to_mins(ev["start"])
        ev_end   = to_mins(ev["end"])
        gap = ev_start - cursor
        if gap >= 30 and task_idx < len(p_tasks):
            # Assign tasks to the focus window
            focus_tasks = []
            window_mins = gap
            while window_mins >= 30 and task_idx < len(p_tasks):
                t = p_tasks[task_idx]
                est = 60 if str(t.severity or "") == "P1" else 45
                if window_mins >= est:
                    focus_tasks.append({
                        "task_id": str(t.task_id),
                        "title": str(t.title)[:55],
                        "severity": str(t.severity),
                        "est_mins": est,
                    })
                    window_mins -= est
                    task_idx += 1
                else:
                    break
            if focus_tasks:
                blocks.append({
                    "type": "focus",
                    "start": to_str(cursor),
                    "end": to_str(ev_start),
                    "label": f"Focus block — {gap} min",
                    "tasks": focus_tasks,
                })
        blocks.append({
            "type": "meeting",
            "start": ev["start"],
            "end": ev["end"],
            "label": ev["title"],
            "attendees": ev.get("attendees", []),
            "tasks": [],
        })
        cursor = ev_end

    # Remaining time after last meeting
    if cursor < work_end and task_idx < len(p_tasks):
        gap = work_end - cursor
        focus_tasks = []
        window_mins = gap
        while window_mins >= 30 and task_idx < len(p_tasks):
            t = p_tasks[task_idx]
            est = 60 if str(t.severity or "") == "P1" else 45
            if window_mins >= est:
                focus_tasks.append({
                    "task_id": str(t.task_id),
                    "title": str(t.title)[:55],
                    "severity": str(t.severity),
                    "est_mins": est,
                })
                window_mins -= est
                task_idx += 1
            else:
                break
        if focus_tasks:
            blocks.append({
                "type": "focus",
                "start": to_str(cursor),
                "end": to_str(work_end),
                "label": f"Focus block — {gap} min",
                "tasks": focus_tasks,
            })

    return blocks


@dataclass(slots=True)
class PlanningAgent(Agent):
    name: str = "planning"

    def run(self, state: WorkflowState) -> WorkflowState:
        if not state.daily_plan:
            state.daily_plan = [t.title for t in state.ranked_tasks]

        # Feature 5: calendar-aware time blocking
        try:
            blocks = _build_calendar_blocks(state.ranked_tasks)
            state.calendar_blocks = blocks
            focus_count = sum(1 for b in blocks if b["type"] == "focus")
            mtg_count   = sum(1 for b in blocks if b["type"] == "meeting")
            state.trace(
                self.name,
                f"Calendar-aware plan: {mtg_count} meeting(s) + {focus_count} focus block(s) scheduled.",
            )
        except Exception:
            state.trace(self.name, "Built daily plan from ranked tasks (no calendar data).")
        else:
            state.trace(self.name, "Built daily plan from ranked tasks.")

        return state
