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
            SourceConfig(name="jira", path="data/jira.json"),
            SourceConfig(name="servicenow", path="data/servicenow.json"),
            SourceConfig(name="outlook", path="data/outlook.txt"),
            SourceConfig(name="meeting_notes", path="data/meeting_notes.txt"),
        ]
    )


DEFAULT_CONFIG = AppConfig()
