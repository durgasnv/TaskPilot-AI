"""Prompt builders for the ingestion and extraction agents."""

from __future__ import annotations

from taskpilot_ai.models import SourceDocument

# Hard cap on source content sent to the LLM. Keeps prompt size bounded and
# prevents large Jira boards from exhausting the context window.
_MAX_CONTENT_CHARS = 6000


def build_ingestion_system_prompt() -> str:
    return (
        "You are the TaskPilot ingestion agent. Read only the provided source files, "
        "stay grounded in the inputs, and prepare clean context for downstream extraction."
    )


def build_extraction_system_prompt() -> str:
    return (
        "You are the TaskPilot extraction agent. Identify only actionable engineering work, "
        "cite the source text, and do not invent tasks not supported by the input. "
        "Return a JSON array where each item has: task_id, source_id, title, description, "
        "severity (P1-P4), deadline (ISO-8601 or null), blocked_by (list), blocks (list), "
        "business_impact (string), extracted (bool)."
    )


def build_react_user_prompt(document: SourceDocument, max_chars: int = _MAX_CONTENT_CHARS) -> str:
    content = document.content
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars]

    suffix = f"\n[...truncated at {max_chars} chars]" if truncated else ""

    return (
        f"Source: {document.source.value}\n"
        f"Location: {document.location or 'inline'}\n"
        "Follow a ReAct-style loop:\n"
        "1. Thought: explain what you need from the file.\n"
        "2. Action: call read_source if more context is required.\n"
        "3. Observation: summarize only what the file contains.\n"
        "4. Final: return candidate action items with evidence.\n\n"
        "Source content:\n"
        f"{content}{suffix}"
    )

