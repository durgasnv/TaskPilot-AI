# TaskPilot AI

**Agentic Task Intelligence Assistant for Engineers**

Autonomously ingests tasks from Jira, ServiceNow, Outlook, and meeting transcripts — deduplicates, scores, and delivers a calendar-aware daily plan through a web console, CLI, and MCP server.

---

## Team Byte Builders

| Member | Role |
|---|---|
| Burra Srinidhi | Dev1 — Data Foundation & Parsers |
| Durgashree Nag | Dev2 — Multi-Agent Architecture |
| Siripuram Poojitha | Dev3 — Deduplication & Prioritization |
| Aishwarya Gudla | Dev4 — Event Monitor & Interfaces |
| Kumudwini Gottipati | Dev5 — QA & Testing |

---

## Requirements

- Python 3.11+
- pip

---

## Setup

```bash
git clone https://github.com/durgasnv/TaskPilot-AI.git
cd TaskPilot-AI
pip install -e .
```

### API Key (optional)

TaskPilot works out of the box with a built-in mock LLM. For real LLM extraction, set a free Groq key:

```bash
export GROQ_API_KEY=your_key_here
```

Get one free at https://console.groq.com. Falls back to mock automatically if not set.

---

## Run — Web Dashboard

```bash
uvicorn taskpilot_ai.ui.app:app --reload
```

Open **http://localhost:8000** in your browser.

- Click **Run Pipeline** to execute all 5 agents
- Watch the live agent log as each specialist activates
- Switch between **TASKS**, **SCHEDULE**, and **TEAM** tabs
- Use the filter pills (P1/P2/P3/P4, JIRA/SN/EMAIL/MTG) to narrow results
- Click **↑ boost**, **⊘ snooze**, or **↓ drop** on any task card to train the memory

---

## Run — CLI Pipeline

```bash
taskpilot
```

Or directly:

```bash
python -m taskpilot_ai.main
```

Prints the full ranked task list and daily schedule to the terminal.

---

## Run — File-Drop Monitor

```bash
taskpilot --monitor
```

Watches `data/injected/` every 5 seconds. Drop any JSON file there and the full pipeline re-runs automatically. P1 tasks trigger an immediate alert.

---

## Run — MCP Server

Exposes 6 tools over JSON-RPC 2.0 (stdin/stdout) for Claude Desktop or any MCP-compatible client:

```bash
taskpilot-mcp
```

**Available tools:** `run_pipeline`, `get_tasks`, `inject_task`, `get_daily_plan`, `get_team_view`, `record_feedback`

To connect from Claude Desktop, add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "taskpilot": {
      "command": "taskpilot-mcp"
    }
  }
}
```

---

## Run — Tests

```bash
python -m pytest tests/ -v
```

37 tests, all passing in ~2 seconds.

---

## Project Structure

```
src/taskpilot_ai/
├── agents/          # 5 specialist agents (ingestion → extraction → dedup → priority → planning)
├── analytics/       # TF-IDF deduplicator and scoring prioritizer
├── llm/             # Groq, Anthropic, and Mock LLM clients
├── memory/          # Engineer preference persistence
├── mcp/             # MCP/JSON-RPC 2.0 server
├── orchestration/   # WorkflowState and pipeline graph
├── tools/           # Source readers and file utilities
└── ui/              # FastAPI app and web dashboard

data/raw/
├── jira_board.json              # 12 Jira tickets
├── servicenow_defects.json      # 8 ServiceNow incidents
├── outlook_inbox.json           # 8 emails with hidden action items
├── meeting_transcripts.json     # 3 meeting transcripts
└── calendar.json                # Alice's working day calendar

data/memory/
└── preferences.json             # Persisted engineer feedback (boost/snooze/drop)
```

---

## Features

- **Multi-source ingestion** — Jira, ServiceNow, Outlook, meeting transcripts
- **LLM extraction** — Surfaces hidden action items from unstructured text (ReAct pattern)
- **Semantic deduplication** — TF-IDF cosine similarity with keyword boosting
- **Explainable prioritization** — Four-factor formula with auditable rationale per task
- **Engineer memory** — Learns from boost/snooze/drop feedback; persists across runs
- **Calendar-aware planning** — Slots top tasks into free focus windows between meetings
- **Team dashboard** — Per-engineer workload bars and P1 exposure
- **MCP server** — 6 tools for Claude Desktop and AI client integration
- **PII scrubbing** — 8 pattern types redacted before any LLM call
- **File-drop monitor** — Emergency task injection with automatic re-prioritization
