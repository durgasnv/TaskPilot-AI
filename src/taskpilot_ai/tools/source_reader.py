"""File-reading tool dependencies for ingestion agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from taskpilot_ai.models import SourceDocument, FileSource


@dataclass(slots=True)
class ReadResult:
    document: SourceDocument | None
    error: str | None = None


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

