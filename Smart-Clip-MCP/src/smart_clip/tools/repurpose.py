"""repurpose tool — convert long video to platform-specific short clips."""

from __future__ import annotations

import logging

from smart_clip.tools.smart_clip import _run_smart_clip
from smart_clip.utils import run_async

logger = logging.getLogger(__name__)

# Platform-specific defaults
PLATFORM_DEFAULTS = {
    "tiktok": {"clip_duration_max": 60, "clip_count": 3},
    "youtube_shorts": {"clip_duration_max": 60, "clip_count": 3},
    "instagram_reels": {"clip_duration_max": 60, "clip_count": 3},
}


def repurpose_tool(
    video_input: str,
    platform: str = "tiktok",
    clip_count: int = 3,
    style: str = "informative",
) -> dict:
    """
    将长视频自动重制为适配目标平台的短视频。支持文件路径和URL。自动识别精彩内容、裁切、加字幕、调比例。

    Args:
        video_input: 输入视频文件路径或URL
        platform: 目标平台 (tiktok/youtube_shorts/instagram_reels)
        clip_count: 期望输出的片段数量
        style: 剪辑风格偏好 (informative/entertaining/emotional)

    Returns:
        包含输出片段列表和分析摘要的字典
    """
    import asyncio

    # Map style to intent
    style_intents = {
        "informative": "提取信息密度最高的片段，保留核心观点和关键数据",
        "entertaining": "提取最有趣、最搞笑的片段，节奏快、有反转",
        "emotional": "提取最感人、最有共鸣的片段，保留情绪张力",
    }
    intent = style_intents.get(style, "提取精彩片段")

    # Platform-specific overrides
    platform_defaults = PLATFORM_DEFAULTS.get(platform, {})
    max_duration = platform_defaults.get("clip_duration_max", 60)

    return run_async(_run_smart_clip(
        video_input=video_input,
        intent=intent,
        clip_count=clip_count,
        clip_duration_min=15,
        clip_duration_max=max_duration,
        platform=platform,
        with_subtitles=True,
        with_bgm=False,
        output_dir=f"./smart-clip-output/{platform}",
        template="quote" if style == "entertaining" else "default",
    ))
