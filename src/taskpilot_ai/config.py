"""Static configuration for local development."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class SourceConfig:
    name: str
    enabled: bool = True
    path: str | None = None


@dataclass(slots=True)
class AppConfig:
    app_name: str = "TaskPilot AI"
    sources: list[SourceConfig] = field(
        default_factory=lambda: [
            SourceConfig(name="jira", path="data/raw/jira_board.json"),
            SourceConfig(name="servicenow", path="data/raw/servicenow_defects.json"),
            SourceConfig(name="outlook", path="data/raw/outlook_inbox.json"),
            SourceConfig(name="meeting_notes", path="data/raw/meeting_transcripts.json"),
        ]
    )


DEFAULT_CONFIG = AppConfig()
