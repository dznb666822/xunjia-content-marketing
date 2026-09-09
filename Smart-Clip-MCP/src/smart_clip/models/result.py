"""Data models for clip execution results."""

from __future__ import annotations

from pydantic import BaseModel


class ClipOutput(BaseModel):
    """A single output clip."""

    index: int
    output_path: str
    start: float
    end: float
    duration: float
    reason: str = ""
    score: float = 0.0


class AnalysisInfo(BaseModel):
    """Summary of the analysis phase."""

    total_duration: float = 0.0
    speech_ratio: float = 0.0
    language: str = "zh"
    highlights_found: int = 0
    highlights_selected: int = 0


class ClipResult(BaseModel):
    """Full result of a clip operation."""

    success: bool = True
    clips: list[ClipOutput] = []
    analysis: AnalysisInfo = AnalysisInfo()
    output_dir: str = ""
    error: str | None = None
