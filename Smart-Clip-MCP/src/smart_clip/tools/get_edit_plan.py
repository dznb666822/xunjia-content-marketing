"""get_edit_plan tool — generate edit plan for human review without executing."""

from __future__ import annotations

import logging
import os

from smart_clip.analyzer import SubtitleExtractor, AudioEnergyAnalyzer
from smart_clip.planner import SpeechSegmenter, HighlightDetector, StrategyEngine
from smart_clip.config import DEFAULT_CONFIG
from smart_clip.utils import run_async

logger = logging.getLogger(__name__)


async def _run_get_edit_plan(
    video_path: str,
    intent: str = "提取精彩片段",
    clip_count: int = 5,
    clip_duration_min: int = 15,
    clip_duration_max: int = 90,
) -> dict:
    """Core logic for get_edit_plan tool."""
    if not os.path.exists(video_path):
        return {"success": False, "error": f"Video file not found: {video_path}"}

    cfg = DEFAULT_CONFIG

    # Analyze
    whisper_cfg = cfg["analyzer"]["whisper"]
    extractor = SubtitleExtractor(
        mode=whisper_cfg["mode"],
        language=whisper_cfg["language"],
        model=whisper_cfg["model"],
        api_key=whisper_cfg.get("api_key") or None,
    )
    subtitle = await extractor.extract(video_path, language=whisper_cfg["language"])

    audio_analyzer = AudioEnergyAnalyzer(
        energy_percentile=cfg["analyzer"]["audio"]["energy_percentile"],
        silence_threshold=cfg["analyzer"]["audio"]["silence_threshold"],
    )
    audio = await audio_analyzer.analyze(video_path)

    total_duration = subtitle.segments[-1].end if subtitle.segments else 0.0

    # Plan (without execute)
    segmenter = SpeechSegmenter(max_duration=clip_duration_max)
    segments = segmenter.segment(subtitle, audio, max_clip_duration=clip_duration_max)

    detector = HighlightDetector(
        model=cfg["planner"]["llm"]["model"],
        temperature=cfg["planner"]["llm"]["temperature"],
        api_key=cfg["planner"]["llm"].get("api_key") or None,
        base_url=cfg["planner"]["llm"].get("base_url") or None,
    )

    candidates, summary, content_type, tone = await detector.detect(
        segments=segments,
        total_duration=total_duration,
        language=subtitle.language,
        intent=intent,
        clip_count=clip_count,
        clip_duration_min=clip_duration_min,
        clip_duration_max=clip_duration_max,
        audio=audio,
    )

    strategy_cfg = cfg["planner"]["strategy"]
    engine = StrategyEngine(
        min_score=strategy_cfg["min_score"],
        min_gap=strategy_cfg["min_gap"],
        snap_margin=strategy_cfg["snap_margin"],
        clip_duration_min=clip_duration_min,
        clip_duration_max=clip_duration_max,
    )

    plan = engine.apply(
        candidates=candidates,
        subtitle=subtitle,
        audio=audio,
        clip_count=clip_count,
        platform="original",
        with_subtitles=True,
        with_bgm=False,
        summary=summary,
        content_type=content_type,
        tone=tone,
    )

    return {
        "success": True,
        "edit_plan": {
            "clips": [
                {
                    "index": i,
                    "start": c.start,
                    "end": c.end,
                    "duration": round(c.duration, 1),
                    "title": c.title,
                    "reason": c.reason,
                    "score": c.weighted_score,
                    "suggested_hook": c.suggested_hook,
                }
                for i, c in enumerate(plan.clips)
            ],
            "total_selected_duration": plan.total_selected_duration,
            "content_type": plan.content_type,
            "tone": plan.tone,
            "summary": plan.summary,
        },
        "video_path": video_path,
        "note": "此方案尚未执行。审核通过后，可使用 smart_clip 工具执行剪辑。",
    }


def get_edit_plan_tool(
    video_path: str,
    intent: str = "提取精彩片段",
    clip_count: int = 5,
    clip_duration_min: int = 15,
    clip_duration_max: int = 90,
) -> dict:
    """
    生成剪辑方案但不执行，返回方案供人工审核。审核通过后调用 smart_clip 执行。

    Args:
        video_path: 输入视频文件路径
        intent: 剪辑意图，自然语言描述
        clip_count: 期望输出的片段数量
        clip_duration_min: 单片段最短秒数
        clip_duration_max: 单片段最长秒数

    Returns:
        包含剪辑方案的字典（未执行）
    """
    return run_async(_run_get_edit_plan(
        video_path=video_path,
        intent=intent,
        clip_count=clip_count,
        clip_duration_min=clip_duration_min,
        clip_duration_max=clip_duration_max,
    ))
