"""
Conversational CLI interface for TaskPilot AI.

Pattern-matches natural language questions against WorkflowState data
and returns formatted answers. Works without a real LLM — all answers
are derived directly from the pipeline output.
"""

from __future__ import annotations

import re
from taskpilot_ai.orchestration.state import WorkflowState
from taskpilot_ai.unified_task import UnifiedTask


# Maps common demo phrases to canonical task_ids for reliable lookup.
_DEMO_ALIASES: dict[str, str] = {
    "upload bug": "JIRA-1001",
    "file upload": "JIRA-1001",
    "acme issue": "JIRA-1001",
    "vp email": "EMAIL-001",
    "james email": "EMAIL-001",
    "vp's email": "EMAIL-001",
    "james's email": "EMAIL-001",
    "security incident": "JIRA-1006",
    "key rotation": "JIRA-1006",
    "rotate keys": "JIRA-1006",
    "gdpr deletion": "SN-INC0001011",
    "erasure request": "SN-INC0001011",
    "db issue": "JIRA-1003",
    "database problem": "JIRA-1003",
}


class TaskPilotChat:
    def __init__(self, state: WorkflowState) -> None:
        self.state = state

    # ── Public entry point ────────────────────────────────────────────────────

    def answer(self, question: str) -> str:
        q = question.lower().strip()

        if any(w in q for w in ("help", "what can you", "commands", "examples")):
            return self._help()

        # "why" questions must be checked before "#1" / "top priority" to avoid mismatch
        if re.search(r"why.*(rank|prior|top|number|#|first|score)", q):
            return self._explain_ranking(question)

        if "explain" in q and any(w in q for w in ("rank", "prior", "score")):
            return self._explain_ranking(question)

        if any(w in q for w in ("top priority", "number one", "#1", "most important",
                                 "what should i work on", "what do i work on", "first task",
                                 "start with", "highest priority")):
            return self._top_priority()

        # "weekly" must be checked before "summary" to avoid the generic branch
        if any(w in q for w in ("week", "weekly", "this week", "rollup", "standup report")):
            return self._weekly_summary()

        if any(w in q for w in ("summarize", "summary", "overview", "tell me about")):
            return self._summarize(question)

        if any(w in q for w in ("block", "blocked", "blocking", "depend", "waiting on")):
            return self._blockers()

        if any(p in q for p in ("all p1", "p1s", "p1 task", "critical", "severity p1")):
            return self._by_severity("P1")

        if any(p in q for p in ("all p2", "p2s", "p2 task")):
            return self._by_severity("P2")

        if any(w in q for w in ("email", "inbox", "outlook", "mail")):
            return self._by_source("email")

        if any(w in q for w in ("meeting", "transcript", "standup", "action item")):
            return self._by_source("transcript")

        if any(w in q for w in ("jira", "ticket", "story", "sprint")):
            return self._by_source("jira")

        if any(w in q for w in ("servicenow", "incident", "sn-", "defect")):
            return self._by_source("servicenow")

        if any(w in q for w in ("plan", "today", "daily", "my day", "list")):
            return self._daily_plan()

        if any(w in q for w in ("how many", "count", "total", "stats", "statistics", "numbers")):
            return self._stats()

        if any(w in q for w in ("deadline", "due", "overdue", "expir", "sla")):
            return self._deadlines()

        if any(w in q for w in ("duplicate", "dedup", "merged", "similar")):
            return self._dedup_summary()

        # Last resort: keyword search across task titles
        return self._keyword_search(question)

    # ── Answer builders ───────────────────────────────────────────────────────

    def _top_priority(self) -> str:
        if not self.state.ranked_tasks:
            return "No tasks in the pipeline yet."
        t = self.state.ranked_tasks[0]
        lines = [
            f"Your top priority is:\n",
            f"  [{t.severity}] {t.title}",
        ]
        if t.priority_rationale:
            lines.append(f"\n  Why: {t.priority_rationale}")
        if t.business_impact:
            lines.append(f"\n  Business impact: {t.business_impact[:120]}")
        if t.deadline:
            lines.append(f"\n  Deadline: {t.deadline.strftime('%Y-%m-%d %H:%M UTC')}")
        if t.blocks:
            lines.append(f"\n  Blocks: {', '.join(t.blocks)}")
        return "".join(lines)

    def _explain_ranking(self, question: str) -> str:
        # Try to find a specific task mentioned in the question
        task = self._find_task_in_question(question)
        if task:
            rank = next(
                (i + 1 for i, t in enumerate(self.state.ranked_tasks) if t.task_id == task.task_id),
                "?"
            )
            lines = [f'"{task.title}" is ranked #{rank}.\n']
            lines.append(f"  Score: {task.priority_score}/100")
            if task.priority_rationale:
                lines.append(f"\n  Breakdown: {task.priority_rationale}")
            if task.business_impact:
                lines.append(f"\n  Business impact: {task.business_impact[:120]}")
            return "".join(lines)

        # No specific task found — explain top 3
        lines = ["Here's why the top tasks are ranked as they are:\n"]
        for i, t in enumerate(self.state.ranked_tasks[:3], 1):
            lines.append(f"\n  #{i} [{t.severity}] {t.title[:60]}")
            if t.priority_rationale:
                lines.append(f"\n      {t.priority_rationale}")
        return "".join(lines)

    def _summarize(self, question: str) -> str:
        q = question.lower()

        # VP / escalation email
        if any(w in q for w in ("vp", "escalation", "executive")):
            matches = [t for t in self.state.ranked_tasks
                       if any(w in t.title.lower() for w in ("vp", "escalation", "executive", "urgent"))]
            if matches:
                t = matches[0]
                return (
                    f"VP/Escalation summary:\n"
                    f"  Task: {t.title}\n"
                    f"  Severity: {t.severity}\n"
                    f"  Source: {t.source}\n"
                    f"  Impact: {(t.business_impact or 'Not specified')[:150]}\n"
                    f"  Details: {(t.description or '')[:200]}"
                )

        # Email summary
        if any(w in q for w in ("email", "inbox", "mail")):
            return self._by_source("email", brief=True)

        # Meeting summary
        if any(w in q for w in ("meeting", "transcript", "standup")):
            return self._by_source("transcript", brief=True)

        # General summary
        p1s = [t for t in self.state.ranked_tasks if str(t.severity) == "P1"]
        p2s = [t for t in self.state.ranked_tasks if str(t.severity) == "P2"]
        lines = [
            f"Summary: {len(self.state.ranked_tasks)} tasks across "
            f"{len(set(str(t.source) for t in self.state.ranked_tasks))} sources.\n",
            f"\n  {len(p1s)} critical (P1) items requiring immediate attention.",
            f"\n  {len(p2s)} high-priority (P2) items.",
        ]
        if p1s:
            lines.append(f"\n\n  Top P1: [{p1s[0].severity}] {p1s[0].title}")
            if p1s[0].priority_rationale:
                lines.append(f"\n    {p1s[0].priority_rationale}")
        return "".join(lines)

    def _blockers(self) -> str:
        blocked = [t for t in self.state.ranked_tasks if t.blocked_by]
        blocking = [t for t in self.state.ranked_tasks if t.blocks]

        lines = []
        if blocked:
            lines.append(f"Tasks blocked ({len(blocked)}):\n")
            for t in blocked[:5]:
                lines.append(f"  [{t.severity}] {t.title[:60]}\n")
                lines.append(f"    Waiting on: {', '.join(t.blocked_by)}\n")
        if blocking:
            lines.append(f"\nTasks blocking others ({len(blocking)}):\n")
            for t in blocking[:5]:
                lines.append(f"  [{t.severity}] {t.title[:60]}\n")
                lines.append(f"    Blocks: {', '.join(t.blocks)}\n")
        if not blocked and not blocking:
            return "No dependency information found in current task set."
        return "".join(lines)

    def _by_severity(self, sev: str) -> str:
        tasks = [t for t in self.state.ranked_tasks if str(t.severity) == sev]
        if not tasks:
            return f"No {sev} tasks found."
        lines = [f"{sev} tasks ({len(tasks)} total):\n"]
        for i, t in enumerate(tasks, 1):
            lines.append(f"\n  {i}. {t.title[:70]}")
            if t.priority_rationale:
                lines.append(f"\n     {t.priority_rationale[:80]}")
        return "".join(lines)

    def _by_source(self, source: str, brief: bool = False) -> str:
        tasks = [t for t in self.state.ranked_tasks if str(t.source).lower() == source.lower()]
        if not tasks:
            return f"No tasks from {source} found."
        label = {"email": "Email/Outlook", "transcript": "Meeting transcripts",
                 "jira": "Jira", "servicenow": "ServiceNow"}.get(source, source)
        lines = [f"{label} tasks ({len(tasks)}):\n"]
        limit = 5 if brief else len(tasks)
        for t in tasks[:limit]:
            lines.append(f"\n  [{t.severity}] {t.title[:65]}")
        if brief and len(tasks) > limit:
            lines.append(f"\n  ... and {len(tasks) - limit} more.")
        return "".join(lines)

    def _daily_plan(self) -> str:
        if not self.state.daily_plan:
            return "No daily plan generated yet."
        lines = [f"Your daily plan ({len(self.state.daily_plan)} tasks):\n"]
        for i, title in enumerate(self.state.daily_plan, 1):
            task = next((t for t in self.state.ranked_tasks if t.title == title), None)
            sev = f"[{task.severity}] " if task else ""
            lines.append(f"\n  {i}. {sev}{title[:65]}")
        return "".join(lines)

    def _weekly_summary(self) -> str:
        p1s = [t for t in self.state.ranked_tasks if str(t.severity) == "P1"]
        p2s = [t for t in self.state.ranked_tasks if str(t.severity) == "P2"]
        p3s = [t for t in self.state.ranked_tasks if str(t.severity) == "P3"]
        sources = set(str(t.source) for t in self.state.ranked_tasks)
        lines = [
            "Weekly Standup Summary\n",
            f"{'─' * 40}\n",
            f"Total tasks: {len(self.state.ranked_tasks)} (from {', '.join(sources)})\n\n",
            f"  Critical (P1): {len(p1s)} items\n",
        ]
        for t in p1s[:3]:
            lines.append(f"    • {t.title[:65]}\n")
        lines.append(f"\n  High (P2): {len(p2s)} items\n")
        for t in p2s[:3]:
            lines.append(f"    • {t.title[:65]}\n")
        lines.append(f"\n  Normal (P3): {len(p3s)} items — see daily plan for details.\n")
        return "".join(lines)

    def _stats(self) -> str:
        tasks = self.state.ranked_tasks
        sources = {}
        severities = {}
        for t in tasks:
            sources[str(t.source)] = sources.get(str(t.source), 0) + 1
            severities[str(t.severity or "unknown")] = severities.get(str(t.severity or "unknown"), 0) + 1

        extracted = len(self.state.extracted_tasks)
        deduped = len(self.state.deduplicated_tasks)
        removed = extracted - deduped

        lines = [
            f"Pipeline stats:\n",
            f"  Total extracted : {extracted}\n",
            f"  After dedup     : {deduped} ({removed} duplicates merged)\n",
            f"  Final ranked    : {len(tasks)}\n\n",
            f"  By severity:\n",
        ]
        for sev in ("P1", "P2", "P3", "P4"):
            count = severities.get(sev, 0)
            if count:
                lines.append(f"    {sev}: {count}\n")
        lines.append(f"\n  By source:\n")
        for src, count in sorted(sources.items(), key=lambda x: -x[1]):
            lines.append(f"    {src}: {count}\n")
        return "".join(lines)

    def _deadlines(self) -> str:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        with_deadlines = [(t, t.deadline) for t in self.state.ranked_tasks if t.deadline]
        with_deadlines.sort(key=lambda x: x[1])
        if not with_deadlines:
            return "No deadline information found."
        lines = [f"Tasks by deadline ({len(with_deadlines)} with deadlines):\n"]
        for t, dl in with_deadlines[:10]:
            dl_tz = dl if dl.tzinfo else dl.replace(tzinfo=timezone.utc)
            days = (dl_tz - now).days
            label = "OVERDUE" if days < 0 else f"in {days} day(s)"
            lines.append(f"\n  [{t.severity}] {t.title[:55]}")
            lines.append(f"\n    Due: {dl.strftime('%Y-%m-%d')} ({label})")
        return "".join(lines)

    def _dedup_summary(self) -> str:
        extracted = len(self.state.extracted_tasks)
        deduped = len(self.state.deduplicated_tasks)
        removed = extracted - deduped
        dupes = [t for t in self.state.extracted_tasks if t.duplicate_of]
        lines = [
            f"Deduplication: {extracted} tasks → {deduped} unique ({removed} duplicates merged).\n",
        ]
        if dupes:
            lines.append(f"\nExample merges (showing first 5):\n")
            seen_canonical: set[str] = set()
            count = 0
            for t in dupes:
                if count >= 5:
                    break
                if t.duplicate_of not in seen_canonical:
                    canonical = next((c for c in self.state.extracted_tasks if c.task_id == t.duplicate_of), None)
                    if canonical:
                        lines.append(f"\n  Canonical : [{canonical.source}] {canonical.title[:55]}")
                        lines.append(f"\n  Duplicate : [{t.source}] {t.title[:55]}\n")
                        seen_canonical.add(t.duplicate_of)
                        count += 1
        return "".join(lines)

    def _keyword_search(self, question: str) -> str:
        words = set(re.sub(r"[^a-z0-9\s]", " ", question.lower()).split()) - {
            "what", "who", "when", "where", "how", "why", "is", "are", "the",
            "my", "me", "i", "a", "an", "about", "tell", "show", "give", "can",
        }
        if not words:
            return self._help()
        matches = [
            t for t in self.state.ranked_tasks
            if any(w in t.title.lower() for w in words)
        ]
        if not matches:
            return (
                f"No tasks found matching your query.\n"
                f"Try: 'top priority', 'show P1s', 'summarize emails', 'what's blocking me'"
            )
        lines = [f"Tasks matching your query ({len(matches)}):\n"]
        for t in matches[:8]:
            lines.append(f"\n  [{t.severity}] {t.title[:70]}")
            if t.priority_rationale:
                lines.append(f"\n    {t.priority_rationale[:80]}")
        return "".join(lines)

    def _find_task_in_question(self, question: str) -> UnifiedTask | None:
        q_lower = question.lower()

        # Check demo aliases first for reliable demo-path lookups.
        for phrase, task_id in _DEMO_ALIASES.items():
            if phrase in q_lower:
                match = next((t for t in self.state.ranked_tasks if t.task_id == task_id), None)
                if match:
                    return match

        best: UnifiedTask | None = None
        best_overlap = 0
        stop = {"why", "is", "the", "my", "#1", "ranked", "top", "number", "task",
                "what", "about", "priority", "score", "explain", "reason"}
        q_words = set(re.sub(r"[^a-z0-9\s]", " ", q_lower).split()) - stop
        for t in self.state.ranked_tasks:
            t_words = set(re.sub(r"[^a-z0-9\s]", " ", t.title.lower()).split())
            label_words = set(lbl.replace("-", " ") for lbl in (t.labels or []))
            overlap = len(q_words & (t_words | label_words))
            if overlap > best_overlap:
                best_overlap = overlap
                best = t
        return best if best_overlap >= 1 else None

    def _help(self) -> str:
        return (
            "Things you can ask me:\n\n"
            "  Prioritization\n"
            "    • 'What's my top priority?'\n"
            "    • 'Why is the upload bug ranked #1?'\n"
            "    • 'Show me all P1 tasks'\n\n"
            "  Summaries\n"
            "    • 'Summarize the VP's email'\n"
            "    • 'Summarize my emails'\n"
            "    • 'Give me a weekly summary'\n\n"
            "  Dependencies\n"
            "    • 'What's blocking me?'\n"
            "    • 'What tasks are we blocking?'\n\n"
            "  Planning\n"
            "    • 'Show my daily plan'\n"
            "    • 'What are the deadlines?'\n"
            "    • 'How many tasks do I have?'\n\n"
            "  Or just describe what you're looking for and I'll search."
        )


def run_chat(state: WorkflowState) -> None:
    """Interactive CLI chat loop."""
    chat = TaskPilotChat(state)
    print("\nTaskPilot AI — Chat Mode")
    print("─" * 45)
    print("Ask me anything about your tasks. Type 'help' for examples, 'quit' to exit.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTaskPilot: Goodbye!")
            break
        if not question:
            continue
        if question.lower() in ("quit", "exit", "bye", "q"):
            print("TaskPilot: Goodbye!")
            break
        print(f"\nTaskPilot: {chat.answer(question)}\n")
