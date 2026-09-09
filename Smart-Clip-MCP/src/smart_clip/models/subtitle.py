"""Data models for subtitle/transcription results."""

from __future__ import annotations

from pydantic import BaseModel


class Segment(BaseModel):
    """A single subtitle segment with timing."""

    index: int
    start: float  # seconds
    end: float  # seconds
    text: str
    confidence: float = 1.0


class SubtitleResult(BaseModel):
    """Full transcription result."""

    segments: list[Segment]
    language: str = "zh"
    full_text: str = ""

    def format_for_prompt(self) -> str:
        """Format segments for LLM prompt injection."""
        lines = []
        for seg in self.segments:
            lines.append(f"[{seg.index}] ({seg.start:.1f}s - {seg.end:.1f}s) {seg.text}")
        return "\n".join(lines)
