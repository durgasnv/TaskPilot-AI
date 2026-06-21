"""
TaskPilot MCP Server — exposes agents as Model Context Protocol tools.

Protocol: JSON-RPC 2.0 over stdin/stdout (MCP 1.0).
Run:  python -m taskpilot_ai.mcp.server

Claude Desktop config (~/.config/claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "taskpilot": {
        "command": "python",
        "args": ["-m", "taskpilot_ai.mcp.server"],
        "cwd": "<project_root>"
      }
    }
  }
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).parents[4]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# ── Tool definitions ──────────────────────────────────────────────────────────

_TOOLS: list[dict] = [
    {
        "name": "run_pipeline",
        "description": (
            "Run the full TaskPilot AI multi-agent pipeline over all configured sources "
            "(Jira, ServiceNow, Outlook, meeting transcripts). Returns a ranked priority "
            "queue with scores, deadlines, and rationale for every task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_tasks",
        "description": (
            "Return the current ranked task list from the last pipeline run. "
            "Optionally filter by severity (P1-P4) or source (jira, servicenow, email, transcript)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["P1", "P2", "P3", "P4"],
                    "description": "Filter to only tasks of this severity.",
                },
                "source": {
                    "type": "string",
                    "enum": ["jira", "servicenow", "email", "transcript", "injected"],
                    "description": "Filter to only tasks from this source.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tasks to return (default 20).",
                    "default": 20,
                },
            },
            "required": [],
        },
    },
    {
        "name": "inject_task",
        "description": (
            "Inject an emergency P1 task into the priority queue. The task is immediately "
            "sorted to the top and triggers a re-plan. Use for incidents discovered outside "
            "the normal ingestion cycle."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Unique identifier (e.g. INC-9999)."},
                "title":   {"type": "string", "description": "Short one-line title."},
                "description": {"type": "string", "description": "Detailed description."},
                "severity": {
                    "type": "string",
                    "enum": ["P1", "P2", "P3", "P4"],
                    "default": "P1",
                },
                "deadline": {
                    "type": "string",
                    "description": "ISO 8601 datetime (e.g. 2026-06-21T18:00:00Z).",
                },
                "business_impact": {"type": "string"},
            },
            "required": ["task_id", "title", "severity"],
        },
    },
    {
        "name": "get_daily_plan",
        "description": (
            "Return the calendar-aware time-blocked plan for today. Shows which focus blocks "
            "are available between meetings and which tasks are assigned to each block."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_team_view",
        "description": (
            "Return an aggregated workload view grouped by engineer. Shows task counts, "
            "P1 exposure, and blocked tasks per assignee — useful for manager triage."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "record_feedback",
        "description": (
            "Record engineer feedback on a task so the agent can learn preferences over time. "
            "Snoozed tasks are pushed to the bottom of future runs. Boosted tasks are surfaced "
            "higher. Deprioritized tasks score lower without being snoozed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "action": {
                    "type": "string",
                    "enum": ["snooze", "boost", "deprioritize", "undo"],
                },
            },
            "required": ["task_id", "action"],
        },
    },
]

# ── Global pipeline state cache (populated on first run_pipeline call) ────────

_cached_state: Any = None


def _run_pipeline() -> dict:
    global _cached_state
    import os
    sys.path.insert(0, str(_ROOT / "src"))
    os.chdir(_ROOT)

    from taskpilot_ai.main import _build_graph
    from taskpilot_ai.orchestration.state import WorkflowState

    graph = _build_graph()
    state = graph.run(WorkflowState())
    _cached_state = state

    tasks = [_ser_task(t) for t in state.ranked_tasks]
    return {
        "status": "ok",
        "total": len(tasks),
        "tasks": tasks[:5],
        "message": f"Pipeline complete — {len(tasks)} tasks ranked. Use get_tasks to retrieve.",
    }


def _get_tasks(severity: str | None = None, source: str | None = None, limit: int = 20) -> dict:
    if _cached_state is None:
        return {"error": "Pipeline has not run yet. Call run_pipeline first."}
    tasks = _cached_state.ranked_tasks
    if severity:
        tasks = [t for t in tasks if str(t.severity) == severity]
    if source:
        tasks = [t for t in tasks if source.lower() in str(t.source).lower()]
    return {"total": len(tasks), "tasks": [_ser_task(t) for t in tasks[:limit]]}


def _inject_task(payload: dict) -> dict:
    global _cached_state
    import os
    os.chdir(_ROOT)

    from taskpilot_ai.main import _build_graph
    from taskpilot_ai.models import FileSource, SourceDocument
    from taskpilot_ai.orchestration.state import WorkflowState

    content = json.dumps({"issues": [payload]})
    state = WorkflowState(emergency_mode=True)
    state.raw_inputs[FileSource.INJECTED.value] = SourceDocument(
        source=FileSource.INJECTED,
        content=content,
        location="mcp-inject",
    )
    graph = _build_graph()
    state = graph.run(state)
    _cached_state = state
    top = state.ranked_tasks[0] if state.ranked_tasks else None
    return {
        "status": "injected",
        "ranked_first": _ser_task(top) if top else None,
        "total": len(state.ranked_tasks),
    }


def _get_daily_plan() -> dict:
    if _cached_state is None:
        return {"error": "Pipeline has not run yet. Call run_pipeline first."}
    return {
        "calendar_blocks": getattr(_cached_state, "calendar_blocks", []),
        "plan": _cached_state.daily_plan[:20],
    }


def _get_team_view() -> dict:
    if _cached_state is None:
        return {"error": "Pipeline has not run yet. Call run_pipeline first."}
    return getattr(_cached_state, "team_view", {"message": "No team data available."})


def _record_feedback(task_id: str, action: str) -> dict:
    from taskpilot_ai.memory.engineer_memory import EngineerMemory
    mem = EngineerMemory(_ROOT / "data/memory/preferences.json")
    getattr(mem, action)(task_id)
    return {"status": "recorded", "task_id": task_id, "action": action, "summary": mem.summary}


def _ser_task(task: Any) -> dict:
    if task is None:
        return {}
    return {
        "task_id": str(task.task_id),
        "title": str(task.title),
        "severity": str(task.severity or "P3"),
        "source": str(task.source or "").replace("TaskSource.", ""),
        "priority_score": round(float(task.priority_score or 0), 4),
        "priority_rationale": str(task.priority_rationale or ""),
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "business_impact": str(task.business_impact or "")[:200],
    }


# ── JSON-RPC 2.0 dispatch ─────────────────────────────────────────────────────

def _handle(req: dict) -> dict:
    rid    = req.get("id")
    method = req.get("method", "")
    params = req.get("params") or {}

    try:
        if method == "initialize":
            return _ok(rid, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "taskpilot-mcp", "version": "1.0.0"},
            })

        if method == "tools/list":
            return _ok(rid, {"tools": _TOOLS})

        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            if name == "run_pipeline":
                result = _run_pipeline()
            elif name == "get_tasks":
                result = _get_tasks(
                    severity=args.get("severity"),
                    source=args.get("source"),
                    limit=int(args.get("limit", 20)),
                )
            elif name == "inject_task":
                result = _inject_task(args)
            elif name == "get_daily_plan":
                result = _get_daily_plan()
            elif name == "get_team_view":
                result = _get_team_view()
            elif name == "record_feedback":
                result = _record_feedback(args["task_id"], args["action"])
            else:
                return _err(rid, -32601, f"Unknown tool: {name}")

            return _ok(rid, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            })

        # notifications (no id) — silently ignore
        if rid is None:
            return None  # type: ignore[return-value]

        return _err(rid, -32601, f"Method not found: {method}")

    except Exception as exc:
        return _err(rid, -32603, f"Internal error: {exc}")


def _ok(rid: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError:
            print(json.dumps(_err(None, -32700, "Parse error")), flush=True)
            continue
        resp = _handle(req)
        if resp is not None:
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
