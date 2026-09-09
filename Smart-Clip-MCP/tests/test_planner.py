"""Tests for the planner module."""

import pytest
from smart_clip.models.subtitle import Segment, SubtitleResult
from smart_clip.models.audio import AudioProfile, Peak, SilenceInterval
from smart_clip.planner.segmenter import SpeechSegmenter


class TestSpeechSegmenter:
    """Tests for SpeechSegmenter."""

    def _make_subtitle(self, segments_data: list[tuple[float, float, str]]) -> SubtitleResult:
        return SubtitleResult(
            segments=[
                Segment(index=i, start=s, end=e, text=t)
                for i, (s, e, t) in enumerate(segments_data)
            ],
            language="zh",
            full_text=" ".join(t for _, _, t in segments_data),
        )

    def test_single_segment(self):
        subtitle = self._make_subtitle([(0.0, 10.0, "这是一段测试文字。")])
        segmenter = SpeechSegmenter()
        segments = segmenter.segment(subtitle)
        assert len(segments) == 1
        assert segments[0].start == 0.0
        assert segments[0].end == 10.0

    def test_split_by_gap(self):
        subtitle = self._make_subtitle([
            (0.0, 5.0, "第一段话。"),
            (8.0, 13.0, "第二段话。"),  # 3-second gap
        ])
        segmenter = SpeechSegmenter(min_silence_gap=1.5)
        segments = segmenter.segment(subtitle)
        assert len(segments) == 2

    def test_no_split_short_gap(self):
        subtitle = self._make_subtitle([
            (0.0, 5.0, "第一段话。"),
            (5.5, 10.0, "第二段话。"),  # 0.5-second gap
        ])
        segmenter = SpeechSegmenter(min_silence_gap=1.5)
        segments = segmenter.segment(subtitle)
        assert len(segments) == 1

    def test_empty_subtitle(self):
        subtitle = SubtitleResult(segments=[], language="zh")
        segmenter = SpeechSegmenter()
        segments = segmenter.segment(subtitle)
        assert len(segments) == 0


class TestSubtitleResultFormat:
    """Tests for SubtitleResult.format_for_prompt."""

    def test_format(self):
        subtitle = SubtitleResult(
            segments=[
                Segment(index=0, start=1.0, end=5.0, text="测试文字"),
                Segment(index=1, start=6.0, end=10.0, text="第二段"),
            ],
            language="zh",
        )
        formatted = subtitle.format_for_prompt()
        assert "[0]" in formatted
        assert "[1]" in formatted
        assert "1.0s" in formatted
