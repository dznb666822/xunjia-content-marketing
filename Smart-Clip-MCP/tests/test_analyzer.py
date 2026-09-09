"""Tests for the analyzer module."""

import pytest


class TestSubtitleExtractor:
    """Tests for SubtitleExtractor."""

    def test_init_default(self):
        from smart_clip.analyzer import SubtitleExtractor
        ext = SubtitleExtractor()
        assert ext.mode == "local"
        assert ext.language == "zh"

    def test_init_api_mode(self):
        from smart_clip.analyzer import SubtitleExtractor
        ext = SubtitleExtractor(mode="api", language="en")
        assert ext.mode == "api"
        assert ext.language == "en"


class TestAudioEnergyAnalyzer:
    """Tests for AudioEnergyAnalyzer."""

    def test_init_default(self):
        from smart_clip.analyzer import AudioEnergyAnalyzer
        analyzer = AudioEnergyAnalyzer()
        assert analyzer.energy_percentile == 90
        assert analyzer.silence_threshold == 0.3


class TestSceneDetector:
    """Tests for SceneDetector."""

    def test_init_default(self):
        from smart_clip.analyzer import SceneDetector
        detector = SceneDetector()
        assert detector.threshold == 27.0
