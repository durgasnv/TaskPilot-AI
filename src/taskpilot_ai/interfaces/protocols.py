"""
Structural Protocol contracts that connect Dev2's orchestration backbone
to the work delivered by Dev1, Dev3, and Dev4.

Each Protocol is a Python typing.Protocol — duck-typed, zero runtime cost.
Other devs write a class that matches the method signature; no imports of
this file are required on their side.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskpilot_ai.models import SourceDocument
from taskpilot_ai.unified_task import UnifiedTask


@runtime_checkable
class ScrubberProtocol(Protocol):
    """
    Dev1 implements this.

    The scrubber receives a raw SourceDocument (file content as loaded from
    disk) and returns a new SourceDocument whose content field has all PII
    removed — phone numbers, email addresses, personal names, etc.

    The returned document carries the same source and location so downstream
    agents can still trace which file the content came from.
    """

    def scrub(self, document: SourceDocument) -> SourceDocument:
        ...


@runtime_checkable
class VectorDeduplicatorProtocol(Protocol):
    """
    Dev3 implements this.

    The deduplicator receives the full list of extracted TaskRecords and
    returns a smaller list where semantically identical tasks (>=85%
    embedding similarity) have been merged into a single representative
    record.

    The implementation is expected to use ChromaDB or FAISS internally.
    Dev2's DeduplicationAgent calls this and writes the result into
    WorkflowState.deduplicated_tasks.
    """

    def deduplicate(self, tasks: list[UnifiedTask]) -> list[UnifiedTask]:
        ...


@runtime_checkable
class PrioritizerProtocol(Protocol):
    """
    Dev3 implements this.

    The prioritizer receives deduplicated TaskRecords and returns a list of
    RankedTask objects — each pairing a task with a float score and a plain-
    English rationale string.

    Scoring must factor in deadline proximity, severity, and dependency
    depth. The rationale must be non-empty (black-box ranking is blocked by
    the PRD).
    """

    def rank(self, tasks: list[UnifiedTask]) -> list[UnifiedTask]:
        ...


@runtime_checkable
class NotifierProtocol(Protocol):
    """
    Dev4 implements this.

    The notifier is called by the event monitor when a high-priority file
    is detected at runtime (the mid-demo P1 injection scenario).

    message is a plain-English alert string.
    channel is an optional hint about where to send it (e.g. 'slack',
    'cli', 'webhook'). Implementations may ignore it and use their own
    routing logic.
    """

    def notify(self, message: str, channel: str = "cli") -> None:
        ...
