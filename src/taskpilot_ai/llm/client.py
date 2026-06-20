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
    Returns deterministic fake extraction results keyed on the source name
    found in the user prompt. Field names match UnifiedTask exactly so
    _parse_unified_tasks can deserialise without transformation.
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

    _DEFAULT: str = json.dumps([
        {
            "task_id": "MOCK-001",
            "source_id": "MOCK-001",
            "title": "Extracted task placeholder",
            "description": "Mock extraction result for an unrecognised source.",
            "severity": "P3",
            "deadline": None,
            "blocked_by": [],
            "blocks": [],
            "business_impact": "",
            "extracted": True,
        }
    ])

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        for source_key, response_json in self._RESPONSES.items():
            if f"Source: {source_key}" in user_prompt:
                return LLMResponse(content=response_json, model="mock", tokens_used=0)
        return LLMResponse(content=self._DEFAULT, model="mock", tokens_used=0)
