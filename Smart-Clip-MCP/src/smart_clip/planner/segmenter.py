"""Speech segmentation module — split subtitles into semantic paragraphs."""

from __future__ import annotations

import logging

from smart_clip.models.subtitle import SubtitleResult, Segment
from smart_clip.models.audio import AudioProfile

logger = logging.getLogger(__name__)


class SpeechSegment:
    """A semantic speech segment composed of subtitle segments."""

    def __init__(
        self,
        index: int,
        start: float,
        end: float,
        text: str,
        segments: list[Segment],
        silence_before: float = 0.0,
        silence_after: float = 0.0,
    ):
        self.index = index
        self.start = start
        self.end = end
        self.text = text
        self.segments = segments
        self.silence_before = silence_before
        self.silence_after = silence_after

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def word_count(self) -> int:
        return len(self.text)

    def format_for_prompt(self) -> str:
        return f"[{self.index}] ({self.start:.1f}s - {self.end:.1f}s) {self.text}"


class SpeechSegmenter:
    """Split continuous subtitle stream into semantic paragraphs."""

    def __init__(
        self,
        min_silence_gap: float = 1.5,
        sentence_end_gap: float = 0.8,
        max_duration: float = 90.0,
        force_split_duration: float = 30.0,
    ):
        self.min_silence_gap = min_silence_gap
        self.sentence_end_gap = sentence_end_gap
        self.max_duration = max_duration
        self.force_split_duration = force_split_duration

    def segment(
        self,
        subtitle: SubtitleResult,
        audio: AudioProfile | None = None,
        max_clip_duration: float = 90.0,
    ) -> list[SpeechSegment]:
        """
        Segment subtitles into semantic paragraphs.

        Strategy (priority order):
        1. Silence gaps > min_silence_gap
        2. Sentence endings + pause > sentence_end_gap
        3. Duration exceeds max_duration → split at nearest gap
        4. Fallback: force split every force_split_duration seconds
        """
        if not subtitle.segments:
            return []

        silence_times = set()
        if audio:
            for s in audio.silences:
                # Mark silence midpoints as safe split points
                silence_times.add((s.start + s.end) / 2)

        segments = []
        current_group: list[Segment] = []
        seg_index = 0

        for i, seg in enumerate(subtitle.segments):
            should_split = False

            # Check gap between current and previous segment
            if current_group:
                gap = seg.start - current_group[-1].end

                # Rule 1: Long silence gap
                if gap >= self.min_silence_gap:
                    should_split = True

                # Rule 2: Sentence-ending punctuation + short pause
                elif gap >= self.sentence_end_gap and self._ends_sentence(current_group[-1].text):
                    should_split = True

            # Rule 3: Duration exceeds max
            if current_group and not should_split:
                group_duration = seg.end - current_group[0].start
                if group_duration >= max_clip_duration:
                    should_split = True

            if should_split and current_group:
                speech_seg = self._build_segment(seg_index, current_group, audio)
                segments.append(speech_seg)
                seg_index += 1
                current_group = [seg]
            else:
                current_group.append(seg)

        # Don't forget the last group
        if current_group:
            speech_seg = self._build_segment(seg_index, current_group, audio)
            segments.append(speech_seg)

        # Rule 4: Force-split any segments still too long
        segments = self._force_split_long(segments, max_clip_duration)

        return segments

    def _ends_sentence(self, text: str) -> bool:
        """Check if text ends with sentence-ending punctuation."""
        sentence_enders = ".!?。！？"
        stripped = text.rstrip()
        return stripped[-1] in sentence_enders if stripped else False

    def _build_segment(
        self, index: int, group: list[Segment], audio: AudioProfile | None
    ) -> SpeechSegment:
        """Build a SpeechSegment from a group of subtitle segments."""
        text = " ".join(s.text for s in group)
        silence_before = 0.0
        silence_after = 0.0

        if audio:
            silences_before = audio.get_silences_near(group[0].start, tolerance=2.0)
            silences_after = audio.get_silences_near(group[-1].end, tolerance=2.0)
            if silences_before:
                silence_before = max(s.duration for s in silences_before)
            if silences_after:
                silence_after = max(s.duration for s in silences_after)

        return SpeechSegment(
            index=index,
            start=group[0].start,
            end=group[-1].end,
            text=text,
            segments=group,
            silence_before=silence_before,
            silence_after=silence_after,
        )

    def _force_split_long(
        self, segments: list[SpeechSegment], max_duration: float
    ) -> list[SpeechSegment]:
        """Force-split segments that exceed max_duration."""
        result = []
        seg_index = 0

        for seg in segments:
            if seg.duration <= max_duration:
                seg.index = seg_index
                result.append(seg)
                seg_index += 1
            else:
                # Split at the midpoint silence or just halve
                mid = (seg.start + seg.end) / 2
                part1 = SpeechSegment(
                    index=seg_index,
                    start=seg.start,
                    end=mid,
                    text=seg.text[: len(seg.text) // 2],
                    segments=[s for s in seg.segments if s.end <= mid],
                )
                seg_index += 1
                part2 = SpeechSegment(
                    index=seg_index,
                    start=mid,
                    end=seg.end,
                    text=seg.text[len(seg.text) // 2 :],
                    segments=[s for s in seg.segments if s.start >= mid],
                )
                seg_index += 1
                result.extend([part1, part2])

        return result
