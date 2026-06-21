"""FastAPI web UI for TaskPilot AI — autonomous agent console."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is importable when run from any directory
_ROOT = Path(__file__).parents[3]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="TaskPilot AI")

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

# Single-user in-memory state (demo)
_state = None
_chat = None


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return HTMLResponse(content=(_STATIC / "index.html").read_text(encoding="utf-8"))


@app.post("/api/run")
async def run() -> dict[str, Any]:
    global _state, _chat
    result = await asyncio.to_thread(_pipeline_sync)
    _state = result.pop("_state")
    from taskpilot_ai.chat import TaskPilotChat
    _chat = TaskPilotChat(_state)
    return result


def _pipeline_sync() -> dict[str, Any]:
    from taskpilot_ai.main import _build_graph
    from taskpilot_ai.orchestration.state import WorkflowState

    graph = _build_graph()
    state = graph.run(WorkflowState())

    extracted = len(state.extracted_tasks)
    deduped = len(state.deduplicated_tasks)

    if os.environ.get("GROQ_API_KEY"):
        llm_label = "groq · llama-3.3-70b-versatile"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        llm_label = "anthropic · claude-opus-4-8"
    else:
        llm_label = "offline · mock"

    from taskpilot_ai.memory.engineer_memory import EngineerMemory
    mem = EngineerMemory(_ROOT / "data/memory/preferences.json")

    tasks_out = [_ser_task(t, mem) for t in state.ranked_tasks]

    return {
        "_state": state,
        "traces": [{"step": t.step, "detail": t.detail} for t in state.traces],
        "tasks": tasks_out,
        "stats": {
            "extracted": extracted,
            "deduplicated": deduped,
            "duplicates": extracted - deduped,
            "total": len(state.ranked_tasks),
        },
        "llm": llm_label,
        "agents_roster": getattr(state, "agents_roster", []),
        "calendar_blocks": getattr(state, "calendar_blocks", []),
        "team_view": getattr(state, "team_view", {}),
        "memory_summary": mem.summary,
    }


def _ser_task(task: Any, mem: Any = None) -> dict[str, Any]:
    deadline = None
    if task.deadline:
        try:
            dl = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=timezone.utc)
            deadline = dl.isoformat()
        except Exception:
            deadline = str(task.deadline)
    mem_status = None
    if mem is not None:
        try:
            mem_status = mem.get_status_for(str(task.task_id))
        except Exception:
            pass

    return {
        "task_id": str(task.task_id),
        "title": str(task.title),
        "description": str(task.description or "")[:300],
        "severity": str(task.severity or "P3"),
        "source": str(task.source or "").replace("TaskSource.", ""),
        "deadline": deadline,
        "blocked_by": list(task.blocked_by or []),
        "blocks": list(task.blocks or []),
        "business_impact": str(task.business_impact or "")[:200],
        "priority_score": round(float(task.priority_score or 0), 4),
        "priority_rationale": str(task.priority_rationale or ""),
        "extracted": bool(task.extracted),
        "mem_status": mem_status,
    }


class ChatRequest(BaseModel):
    question: str


class FeedbackRequest(BaseModel):
    task_id: str
    action: str  # "snooze" | "boost" | "deprioritize" | "undo"


@app.post("/api/feedback")
async def feedback(req: FeedbackRequest) -> dict[str, Any]:
    from taskpilot_ai.memory.engineer_memory import EngineerMemory
    mem = EngineerMemory(_ROOT / "data/memory/preferences.json")
    action = req.action
    if action not in ("snooze", "boost", "deprioritize", "undo"):
        return {"error": f"Unknown action: {action}"}
    getattr(mem, action)(req.task_id)
    return {
        "status": "recorded",
        "task_id": req.task_id,
        "action": action,
        "summary": mem.summary,
        "recent": mem.recent_interactions(5),
    }


@app.get("/api/team")
async def team_view() -> dict[str, Any]:
    if _state is None:
        return {"error": "Pipeline has not run yet."}
    return {
        "team": getattr(_state, "team_view", {}),
        "total_tasks": len(_state.ranked_tasks),
    }


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict[str, str]:
    if _chat is None:
        return {"answer": "Agent has not completed its analysis yet. Please wait."}
    return {"answer": _chat.answer(req.question)}


@app.post("/api/inject")
async def inject(file: UploadFile = File(...)) -> dict[str, Any]:
    inject_dir = _ROOT / "data" / "injected"
    inject_dir.mkdir(parents=True, exist_ok=True)
    raw = await file.read()
    dest = inject_dir / (file.filename or "injected.json")
    dest.write_bytes(raw)
    # Run pipeline with the injected file pre-loaded, mirroring FileDropMonitor logic
    result = await asyncio.to_thread(_inject_pipeline_sync, dest, raw.decode("utf-8", errors="replace"))
    global _state, _chat
    _state = result.pop("_state")
    from taskpilot_ai.chat import TaskPilotChat
    _chat = TaskPilotChat(_state)
    result["filename"] = dest.name
    return result


def _inject_pipeline_sync(path: "Path", content: str) -> dict[str, Any]:
    from taskpilot_ai.main import _build_graph
    from taskpilot_ai.models import FileSource, SourceDocument
    from taskpilot_ai.orchestration.state import WorkflowState

    state = WorkflowState(emergency_mode=True)
    state.raw_inputs[FileSource.INJECTED.value] = SourceDocument(
        source=FileSource.INJECTED,
        content=content,
        location=str(path),
    )

    graph = _build_graph()
    state = graph.run(state)

    extracted = len(state.extracted_tasks)
    deduped = len(state.deduplicated_tasks)

    if os.environ.get("GROQ_API_KEY"):
        llm_label = "groq · llama-3.3-70b-versatile"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        llm_label = "anthropic · claude-opus-4-8"
    else:
        llm_label = "offline · mock"

    from taskpilot_ai.memory.engineer_memory import EngineerMemory
    mem = EngineerMemory(_ROOT / "data/memory/preferences.json")
    return {
        "_state": state,
        "traces": [{"step": t.step, "detail": t.detail} for t in state.traces],
        "tasks": [_ser_task(t, mem) for t in state.ranked_tasks],
        "stats": {
            "extracted": extracted,
            "deduplicated": deduped,
            "duplicates": extracted - deduped,
            "total": len(state.ranked_tasks),
        },
        "llm": llm_label,
        "emergency": True,
        "agents_roster": getattr(state, "agents_roster", []),
        "calendar_blocks": getattr(state, "calendar_blocks", []),
        "team_view": getattr(state, "team_view", {}),
        "memory_summary": mem.summary,
    }


def _detect_source_type(content: str) -> str:
    """Infer the source type from JSON structure."""
    import json as _json
    try:
        data = _json.loads(content)
        if not isinstance(data, dict):
            return "injected"
        issues = data.get("issues", [])
        if issues and isinstance(issues, list) and isinstance(issues[0], dict):
            first = issues[0]
            if any(k in first for k in ("key", "fields", "issuetype", "assignee", "status")):
                return "jira"
        result = data.get("result", [])
        if result and isinstance(result, list) and isinstance(result[0], dict):
            first = result[0]
            if any(k in first for k in ("short_description", "sys_id", "incident_state", "caller_id")):
                return "servicenow"
        if "emails" in data or "mailbox" in data:
            return "outlook"
        if "meetings" in data or "transcript" in data or "meeting_notes" in data:
            return "meetings"
    except Exception:
        pass
    return "injected"


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    """Accept any file, auto-detect its source type, run the pipeline on it."""
    global _state, _chat
    raw = await file.read()
    content = raw.decode("utf-8", errors="replace")
    source_type = _detect_source_type(content)
    result = await asyncio.to_thread(_upload_pipeline_sync, content, source_type, file.filename or "upload")
    _state = result.pop("_state")
    from taskpilot_ai.chat import TaskPilotChat
    _chat = TaskPilotChat(_state)
    result["filename"] = file.filename
    return result


def _upload_pipeline_sync(content: str, source_type: str, filename: str) -> dict[str, Any]:
    """Run pipeline on a single uploaded file without touching data/raw/."""
    from taskpilot_ai.agents.specialists import (
        ExtractionAgent, DeduplicationAgent, PrioritizationAgent, PlanningAgent,
    )
    from taskpilot_ai.analytics import TFIDFVectorDeduplicator, ScoringPrioritizer
    from taskpilot_ai.llm.client import GroqLLMClient, AnthropicLLMClient, MockLLMClient
    from taskpilot_ai.models import FileSource, SourceDocument
    from taskpilot_ai.orchestration.graph import TaskPilotGraph
    from taskpilot_ai.orchestration.state import WorkflowState

    if os.environ.get("GROQ_API_KEY"):
        llm = GroqLLMClient()
        llm_label = "groq · llama-3.3-70b-versatile"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        llm = AnthropicLLMClient()
        llm_label = "anthropic · claude-opus-4-8"
    else:
        llm = MockLLMClient()
        llm_label = "offline · mock"

    _SOURCE_MAP = {
        "jira": FileSource.JIRA,
        "servicenow": FileSource.SERVICENOW,
        "outlook": FileSource.OUTLOOK,
        "meetings": FileSource.MEETING_NOTES,
        "injected": FileSource.INJECTED,
    }
    file_source = _SOURCE_MAP.get(source_type, FileSource.INJECTED)

    state = WorkflowState()
    state.raw_inputs[file_source.value] = SourceDocument(
        source=file_source,
        content=content,
        location=filename,
    )

    # Skip IngestionAgent (we already loaded the file) — run extraction onward
    graph = TaskPilotGraph(agents=[
        ExtractionAgent(llm=llm),
        DeduplicationAgent(engine=TFIDFVectorDeduplicator(threshold=0.85)),
        PrioritizationAgent(engine=ScoringPrioritizer()),
        PlanningAgent(),
    ])
    state = graph.run(state)

    extracted = len(state.extracted_tasks)
    deduped = len(state.deduplicated_tasks)

    from taskpilot_ai.memory.engineer_memory import EngineerMemory
    mem = EngineerMemory(_ROOT / "data/memory/preferences.json")
    return {
        "_state": state,
        "traces": [{"step": t.step, "detail": t.detail} for t in state.traces],
        "tasks": [_ser_task(t, mem) for t in state.ranked_tasks],
        "stats": {
            "extracted": extracted,
            "deduplicated": deduped,
            "duplicates": extracted - deduped,
            "total": len(state.ranked_tasks),
        },
        "llm": llm_label,
        "source_type": source_type,
        "agents_roster": getattr(state, "agents_roster", []),
        "calendar_blocks": getattr(state, "calendar_blocks", []),
        "team_view": getattr(state, "team_view", {}),
        "memory_summary": mem.summary,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("taskpilot_ai.ui.app:app", host="0.0.0.0", port=8000, reload=True)
