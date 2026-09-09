"""Prompt templates package."""

from smart_clip.planner.prompts.highlight_detection import (
    HIGHLIGHT_DETECTION_PROMPT,
    QUOTE_EXTRACTION_PROMPT,
    LIVESTREAM_CLIP_PROMPT,
)
from smart_clip.planner.prompts.packaging import PACKAGING_DECISION_PROMPT

__all__ = [
    "HIGHLIGHT_DETECTION_PROMPT",
    "QUOTE_EXTRACTION_PROMPT",
    "LIVESTREAM_CLIP_PROMPT",
    "PACKAGING_DECISION_PROMPT",
]
