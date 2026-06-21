"""LLM client abstraction and mock implementation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class LLMResponse:
    content: str
    model: str
    tokens_used: int = 0


class LLMClient(ABC):
    """Abstract LLM client. Swap MockLLMClient for a real provider at demo time."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Send a system+user prompt pair and return the model's response."""


class MockLLMClient(LLMClient):
    """
    Returns deterministic fake extraction results for known sources.
    For unknown or injected sources, parses the actual file content and
    builds UnifiedTask-compatible JSON from whatever structure it finds.
    This makes the system work with arbitrary files during demos.
    """

    _RESPONSES: dict[str, str] = {
        "jira": json.dumps([
            {
                "task_id": "JIRA-101",
                "source_id": "JIRA-101",
                "title": "Fix payment gateway timeout on checkout",
                "description": "Users hitting 30s timeout during card processing. Affects ~12% of transactions.",
                "severity": "P1",
                "deadline": "2026-06-22T17:00:00+00:00",
                "blocked_by": [],
                "blocks": [],
                "business_impact": "ACME Corp ($2M ARR) threatening churn. VP alerted.",
                "extracted": False,
            },
            {
                "task_id": "JIRA-102",
                "source_id": "JIRA-102",
                "title": "Upgrade auth library to patch CVE-2026-1234",
                "description": "Security advisory requires upgrading jwt-go from 3.x to 4.x.",
                "severity": "P2",
                "deadline": "2026-06-25T17:00:00+00:00",
                "blocked_by": ["JIRA-101"],
                "blocks": [],
                "business_impact": "",
                "extracted": False,
            },
        ]),
        "servicenow": json.dumps([
            {
                "task_id": "SN-5501",
                "source_id": "SN-5501",
                "title": "Production DB connection pool exhausted",
                "description": "SLA breach imminent. Pool size 50, all connections held by stalled queries.",
                "severity": "P1",
                "deadline": "2026-06-20T17:00:00+00:00",
                "blocked_by": [],
                "blocks": [],
                "business_impact": "All authenticated API requests affected.",
                "extracted": False,
            },
        ]),
        "outlook": json.dumps([
            {
                "task_id": "EMAIL-001",
                "source_id": "EMAIL-001",
                "title": "Respond to VP escalation on upload latency",
                "description": "VP flagged media upload times exceed 8s. Needs written response by EOD.",
                "severity": "P2",
                "deadline": "2026-06-19T18:00:00+00:00",
                "blocked_by": [],
                "blocks": [],
                "business_impact": "Enterprise customer SLA at risk.",
                "extracted": True,
            },
        ]),
        "meeting_notes": json.dumps([
            {
                "task_id": "MTG-001",
                "source_id": "MTG-001",
                "title": "Add retry logic to file ingestion pipeline",
                "description": "Action item from sprint review: ingestion drops silently on transient I/O errors.",
                "severity": "P3",
                "deadline": "2026-06-26T17:00:00+00:00",
                "blocked_by": [],
                "blocks": [],
                "business_impact": "",
                "extracted": True,
            },
        ]),
    }

    # Severity normalisation — maps common priority strings to P1-P4
    _SEVERITY_MAP: dict[str, str] = {
        "1": "P1", "1 - critical": "P1", "critical": "P1", "urgent": "P1", "p1": "P1",
        "2": "P2", "2 - high": "P2", "high": "P2", "important": "P2", "p2": "P2",
        "3": "P3", "3 - moderate": "P3", "medium": "P3", "moderate": "P3", "p3": "P3",
        "4": "P4", "4 - low": "P4", "low": "P4", "minimal": "P4", "p4": "P4",
    }

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        # Known sources: return deterministic hardcoded response
        for source_key, response_json in self._RESPONSES.items():
            if f"Source: {source_key}" in user_prompt:
                return LLMResponse(content=response_json, model="mock", tokens_used=0)
        # Unknown / injected source: extract from the actual file content
        extracted = self._extract_from_prompt(user_prompt)
        return LLMResponse(content=extracted, model="mock", tokens_used=0)

    def _extract_from_prompt(self, user_prompt: str) -> str:
        """Pull the source content block from the prompt and parse it."""
        marker = "Source content:\n"
        idx = user_prompt.find(marker)
        raw = user_prompt[idx + len(marker):].strip() if idx != -1 else user_prompt

        # Strip truncation notice if present
        trunc = raw.find("\n[...truncated")
        if trunc != -1:
            raw = raw[:trunc]

        try:
            data = json.loads(raw)
            return self._extract_from_json(data)
        except (json.JSONDecodeError, TypeError):
            return self._extract_from_text(raw)

    def _extract_from_json(self, data: object) -> str:
        """Recursively extract tasks from any JSON structure."""
        if isinstance(data, list):
            tasks = [self._dict_to_task(item, f"INJECTED-{i+1:03d}")
                     for i, item in enumerate(data[:10]) if isinstance(item, dict)]
            return json.dumps(tasks) if tasks else self._fallback()

        if isinstance(data, dict):
            # Known list wrappers
            for key in ("issues", "records", "emails", "meetings", "tasks", "items", "data", "incidents"):
                if key in data and isinstance(data[key], list):
                    return self._extract_from_json(data[key])
            # Single-record wrappers like {"incident": {...}}
            for key in ("incident", "issue", "ticket", "task", "record", "email", "item"):
                if key in data and isinstance(data[key], dict):
                    return json.dumps([self._dict_to_task(data[key], "INJECTED-001")])
            # Unknown wrapper key (backlog, work_items, bugs, requests, etc.)
            # Find any key whose value is a non-empty list of dicts — that's the task list.
            for key, value in data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return self._extract_from_json(value)
            # Bare dict — treat as a single task
            return json.dumps([self._dict_to_task(data, "INJECTED-001")])

        return self._fallback()

    def _dict_to_task(self, item: dict, fallback_id: str) -> dict:
        """Map arbitrary dict keys to UnifiedTask fields."""
        task_id = str(
            item.get("task_id") or item.get("id") or item.get("number")
            or item.get("key") or item.get("ticket_id") or item.get("ref")
            or item.get("code") or item.get("issue_id") or fallback_id
        )
        title = str(
            item.get("title") or item.get("summary") or item.get("short_description")
            or item.get("subject") or item.get("name") or item.get("headline")
            or "Task extracted from injected file"
        )[:200]
        description = str(
            item.get("description") or item.get("body") or item.get("details")
            or item.get("text") or item.get("content") or item.get("comments") or ""
        )[:2000]
        raw_severity = str(
            item.get("severity") or item.get("priority") or item.get("urgency")
            or item.get("impact") or "P3"
        )
        severity = self._SEVERITY_MAP.get(raw_severity.lower(), "P3")
        deadline = (
            item.get("deadline") or item.get("sla_due") or item.get("due_date")
            or item.get("due") or item.get("target_date")
        )
        business_impact = str(
            item.get("business_impact") or item.get("impact") or item.get("customer_impact") or ""
        )
        return {
            "task_id": task_id,
            "source_id": task_id,
            "title": title,
            "description": description,
            "severity": severity,
            "deadline": deadline,
            "blocked_by": item.get("blocked_by", []),
            "blocks": item.get("blocks", []),
            "business_impact": business_impact,
            "extracted": True,
        }

    def _extract_from_text(self, text: str) -> str:
        """Turn plain text (email body, transcript, .txt file) into a single task."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0][:200] if lines else "Task from injected file"
        description = " ".join(lines[1:])[:2000] if len(lines) > 1 else ""
        return json.dumps([{
            "task_id": "INJECTED-TXT-001",
            "source_id": "INJECTED-TXT-001",
            "title": title,
            "description": description,
            "severity": "P2",
            "deadline": None,
            "blocked_by": [],
            "blocks": [],
            "business_impact": "Injected at runtime — verify urgency.",
            "extracted": True,
        }])

    def _fallback(self) -> str:
        return json.dumps([{
            "task_id": "INJECTED-001",
            "source_id": "INJECTED-001",
            "title": "Task from injected file",
            "description": "Content could not be parsed into a known structure.",
            "severity": "P2",
            "deadline": None,
            "blocked_by": [],
            "blocks": [],
            "business_impact": "",
            "extracted": True,
        }])


class GroqLLMClient(LLMClient):
    """
    Free LLM client backed by GroqCloud (Llama models).
    Reads GROQ_API_KEY from the environment. Sign up free at console.groq.com.
    """

    def __init__(self, model: str = "llama-3.3-70b-versatile", max_tokens: int = 4096) -> None:
        from groq import Groq
        self._client = Groq()  # reads GROQ_API_KEY from env
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=self._model,
            tokens_used=response.usage.total_tokens,
        )


class AnthropicLLMClient(LLMClient):
    """
    LLM client backed by the Anthropic Messages API (paid, fallback).
    Reads ANTHROPIC_API_KEY from the environment.
    """

    def __init__(self, model: str = "claude-opus-4-8", max_tokens: int = 4096) -> None:
        import anthropic
        self._client = anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return LLMResponse(
            content=response.content[0].text,
            model=self._model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )
