"""Data models for audio analysis results."""

from __future__ import annotations

from pydantic import BaseModel


class Peak(BaseModel):
    """An audio energy peak point."""

    time: float  # seconds
    intensity: float  # relative intensity (ratio to baseline)


class SilenceInterval(BaseModel):
    """A silence/gap interval."""

    start: float  # seconds
    end: float  # seconds

    @property
    def duration(self) -> float:
        return self.end - self.start


class AudioProfile(BaseModel):
    """Full audio analysis result."""

    energy_curve: list[float] = []  # RMS energy per second
    peaks: list[Peak] = []
    silences: list[SilenceInterval] = []
    tempo: float = 0.0  # estimated BPM

    def get_silences_near(self, time: float, tolerance: float = 2.0) -> list[SilenceInterval]:
        """Find silence intervals near a given time point."""
        return [s for s in self.silences if abs(s.start - time) <= tolerance or abs(s.end - time) <= tolerance]
