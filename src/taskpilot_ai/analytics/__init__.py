"""Dev 3 analytics engines: vector deduplication and multi-factor prioritization."""

from taskpilot_ai.analytics.deduplicator import TFIDFVectorDeduplicator
from taskpilot_ai.analytics.prioritizer import ScoringPrioritizer

__all__ = ["TFIDFVectorDeduplicator", "ScoringPrioritizer"]
