"""File-reading tool dependencies for ingestion agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from taskpilot_ai.models import SourceDocument, FileSource

if TYPE_CHECKING:
    from taskpilot_ai.unified_task import UnifiedTask


@dataclass(slots=True)
class ReadResult:
    document: SourceDocument | None
    error: str | None = None


@dataclass(slots=True)
class NormalizerResult:
    """Return type for bulk normalizer-based ingestion."""
    tasks: list[UnifiedTask]
    source_counts: dict[str, int]
    errors: list[str]


class SourceReader(ABC):
    @abstractmethod
    def read(self, source: FileSource, location: str | None) -> ReadResult:
        """Read a source payload from its configured location."""


class FileSystemSourceReader(SourceReader):
    def read(self, source: FileSource, location: str | None) -> ReadResult:
        if not location:
            return ReadResult(document=None, error="No path configured.")

        path = Path(location)
        if not path.exists():
            return ReadResult(document=None, error=f"Missing source file: {location}")

        return ReadResult(
            document=SourceDocument(
                source=source,
                content=path.read_text(encoding="utf-8"),
                location=str(path),
            )
        )


class NormalizerSourceReader:
    """
    Wraps Dev1's normalize_all_sources() pipeline.

    Instead of reading raw files one at a time, this calls the normalizer
    which handles all four parsers, PII scrubbing, and UnifiedTask creation
    in a single call. The IngestionAgent detects this reader type and takes
    the bulk-load path instead of the per-file loop.
    """

    def load_all(
        self,
        jira_path: str = "data/raw/jira_board.json",
        servicenow_path: str = "data/raw/servicenow_defects.json",
        email_path: str = "data/raw/outlook_inbox.json",
        meeting_path: str = "data/raw/meeting_transcripts.json",
        injected_path: str = "data/injected",
    ) -> NormalizerResult:
        from src.pipeline.normalizer import normalize_all_sources
        result = normalize_all_sources(
            jira_path=jira_path,
            servicenow_path=servicenow_path,
            email_path=email_path,
            meeting_path=meeting_path,
            injected_path=injected_path,
        )
        return NormalizerResult(
            tasks=result.tasks,
            source_counts=result.source_counts,
            errors=result.errors,
        )

