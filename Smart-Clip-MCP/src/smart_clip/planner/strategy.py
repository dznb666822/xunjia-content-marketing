"""Strategy engine — post-process LLM candidates into a final edit plan."""

from __future__ import annotations

import logging

from smart_clip.models.plan import ClipCandidate, EditPlan
from smart_clip.models.subtitle import SubtitleResult
from smart_clip.models.audio import AudioProfile

logger = logging.getLogger(__name__)


class StrategyEngine:
    """Apply strategy rules to refine LLM-selected clips into an edit plan."""

    def __init__(
        self,
        min_score: float = 6.0,
        min_gap: float = 10.0,
        snap_margin: float = 0.5,
        clip_duration_min: float = 15.0,
        clip_duration_max: float = 90.0,
    ):
        self.min_score = min_score
        self.min_gap = min_gap
        self.snap_margin = snap_margin
        self.clip_duration_min = clip_duration_min
        self.clip_duration_max = clip_duration_max

    def apply(
        self,
        candidates: list[ClipCandidate],
        subtitle: SubtitleResult,
        audio: AudioProfile | None = None,
        clip_count: int = 5,
        platform: str = "original",
        with_subtitles: bool = True,
        with_bgm: bool = False,
        summary: str = "",
        content_type: str = "",
        tone: str = "",
    ) -> EditPlan:
        """
        Apply strategy rules and generate a final edit plan.

        Steps:
        1. Score filtering
        2. Deduplication (overlap/gap check)
        3. Duration adjustment
        4. Top-N selection
        5. Snap to safe cut points
        """
        # 1. Score filter
        filtered = [c for c in candidates if c.weighted_score >= self.min_score]
        logger.info(f"Score filter: {len(candidates)} → {len(filtered)} (threshold={self.min_score})")

        # 2. Deduplicate overlapping clips
        deduped = self._deduplicate(filtered)
        logger.info(f"Dedup: {len(filtered)} → {len(deduped)}")

        # 3. Adjust durations
        adjusted = self._adjust_duration(deduped, subtitle, audio)
        logger.info(f"Duration adjusted: {len(adjusted)} clips")

        # 4. Top-N selection
        selected = sorted(adjusted, key=lambda c: c.weighted_score, reverse=True)[:clip_count]

        # 5. Snap to safe cut points
        snapped = self._snap_to_safe_cuts(selected, subtitle, audio)

        # Sort by start time for natural playback order
        snapped.sort(key=lambda c: c.start)

        total_duration = sum(c.duration for c in snapped)

        return EditPlan(
            clips=snapped,
            total_selected_duration=round(total_duration, 1),
            platform=platform,
            with_subtitles=with_subtitles,
            with_bgm=with_bgm,
            content_type=content_type,
            tone=tone,
            summary=summary,
        )

    def _deduplicate(self, clips: list[ClipCandidate]) -> list[ClipCandidate]:
        """Remove clips that overlap or are too close together."""
        if not clips:
            return []

        # Sort by score descending — keep higher-scored clips
        sorted_clips = sorted(clips, key=lambda c: c.weighted_score, reverse=True)
        kept = []

        for clip in sorted_clips:
            overlap = False
            for existing in kept:
                # Check if clips overlap or are within min_gap
                if (
                    clip.start < existing.end + self.min_gap
                    and clip.end > existing.start - self.min_gap
                ):
                    overlap = True
                    break
            if not overlap:
                kept.append(clip)

        return kept

    def _adjust_duration(
        self,
        clips: list[ClipCandidate],
        subtitle: SubtitleResult,
        audio: AudioProfile | None = None,
    ) -> list[ClipCandidate]:
        """Adjust clip durations to fit within min/max bounds."""
        adjusted = []

        for clip in clips:
            duration = clip.duration

            if duration < self.clip_duration_min:
                # Extend: try to find nearest silence/segment boundary
                new_end = min(
                    clip.start + self.clip_duration_min,
                    subtitle.segments[-1].end if subtitle.segments else clip.end + self.clip_duration_min,
                )
                new_end = self._find_safe_end(clip.start, new_end, subtitle, audio)
                clip.end = new_end

            elif duration > self.clip_duration_max:
                # Trim: find a good split point within range
                new_end = clip.start + self.clip_duration_max
                new_end = self._find_safe_end(clip.start, new_end, subtitle, audio)
                clip.end = new_end

            adjusted.append(clip)

        return adjusted

    def _snap_to_safe_cuts(
        self,
        clips: list[ClipCandidate],
        subtitle: SubtitleResult,
        audio: AudioProfile | None = None,
    ) -> list[ClipCandidate]:
        """Snap clip boundaries to safe cut points (sentence ends, silence gaps)."""
        if not subtitle.segments:
            return clips

        sentence_ends = [seg.end for seg in subtitle.segments]

        for clip in clips:
            # Snap start: move forward to nearest sentence end if within margin
            clip.start = self._snap_time(clip.start, sentence_ends, "forward", self.snap_margin)
            # Snap end: move backward to nearest sentence end if within margin
            clip.end = self._snap_time(clip.end, sentence_ends, "backward", self.snap_margin)

            # Ensure minimum duration
            if clip.end - clip.start < 5.0:
                clip.end = clip.start + self.clip_duration_min

        return clips

    def _snap_time(
        self, time: float, safe_points: list[float], direction: str, margin: float
    ) -> float:
        """
        Snap a time point to the nearest safe cut point.

        Args:
            time: The time point to snap.
            safe_points: List of safe cut points (sentence ends).
            direction: "forward" for start, "backward" for end.
            margin: Maximum distance to snap.
        """
        if direction == "forward":
            for point in safe_points:
                if 0 <= point - time <= margin:
                    return point
        else:
            for point in reversed(safe_points):
                if 0 <= time - point <= margin:
                    return point
        return time

    def _find_safe_end(
        self,
        start: float,
        target_end: float,
        subtitle: SubtitleResult,
        audio: AudioProfile | None = None,
    ) -> float:
        """Find a safe end time near the target, preferring sentence boundaries."""
        if not subtitle.segments:
            return target_end

        # Find segment that contains target_end
        best = target_end
        for seg in subtitle.segments:
            if abs(seg.end - target_end) <= 3.0:
                best = seg.end
                break

        return best
