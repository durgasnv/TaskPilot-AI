"""ReAct runtime primitives for the ingestion and extraction flow."""

from __future__ import annotations

from dataclasses import dataclass

from taskpilot_ai.models import SourceDocument
from taskpilot_ai.prompts.extraction import (
    build_extraction_system_prompt,
    build_ingestion_system_prompt,
    build_react_user_prompt,
)


@dataclass(slots=True)
class ReActPromptPacket:
    system_prompt: str
    user_prompt: str


def build_ingestion_packet(document: SourceDocument) -> ReActPromptPacket:
    return ReActPromptPacket(
        system_prompt=build_ingestion_system_prompt(),
        user_prompt=build_react_user_prompt(document),
    )


def build_extraction_packet(document: SourceDocument) -> ReActPromptPacket:
    return ReActPromptPacket(
        system_prompt=build_extraction_system_prompt(),
        user_prompt=build_react_user_prompt(document),
    )
