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
            SourceConfig(name="jira"),
            SourceConfig(name="servicenow"),
            SourceConfig(name="outlook"),
            SourceConfig(name="meeting_notes"),
        ]
    )


DEFAULT_CONFIG = AppConfig()

