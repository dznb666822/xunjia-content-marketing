"""Tests for the executor module."""

import pytest
from smart_clip.executor.clipper import ClipExecutor, PLATFORM_PRESETS


class TestClipExecutor:
    """Tests for ClipExecutor."""

    def test_init_default(self):
        executor = ClipExecutor()
        assert executor.use_mcp_video is True

    def test_init_no_mcp(self):
        executor = ClipExecutor(use_mcp_video=False)
        assert executor.use_mcp_video is False

    def test_srt_time_format(self):
        result = ClipExecutor._seconds_to_srt_time(3661.5)
        assert result == "01:01:01,500"

    def test_srt_time_zero(self):
        result = ClipExecutor._seconds_to_srt_time(0.0)
        assert result == "00:00:00,000"


class TestPlatformPresets:
    """Tests for platform presets."""

    def test_tiktok_preset(self):
        assert PLATFORM_PRESETS["tiktok"]["aspect"] == "9:16"

    def test_youtube_preset(self):
        assert PLATFORM_PRESETS["youtube"]["aspect"] == "16:9"

    def test_original_is_none(self):
        assert PLATFORM_PRESETS["original"] is None
