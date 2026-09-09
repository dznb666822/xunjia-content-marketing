"""highlight_reel tool — compile highlights from multiple videos."""

from __future__ import annotations

import logging
import os

from smart_clip.analyzer import SubtitleExtractor
from smart_clip.utils import run_async
from smart_clip.planner import SpeechSegmenter, HighlightDetector, StrategyEngine
from smart_clip.executor import ClipExecutor
from smart_clip.models.plan import ExecuteConfig
from smart_clip.models.result import ClipResult, AnalysisInfo, ClipOutput
from smart_clip.config import DEFAULT_CONFIG

logger = logging.getLogger(__name__)


async def _run_highlight_reel(
    video_paths: list[str],
    theme: str,
    target_duration: int = 180,
) -> dict:
    """Core logic for highlight_reel tool."""
    cfg = DEFAULT_CONFIG
    all_candidates = []
    total_found = 0

    for video_path in video_paths:
        if not os.path.exists(video_path):
            logger.warning(f"Video not found, skipping: {video_path}")
            continue

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

        # Plan
        segmenter = SpeechSegmenter()
        segments = segmenter.segment(subtitle, audio)

        detector = HighlightDetector(
            model=cfg["planner"]["llm"]["model"],
            temperature=cfg["planner"]["llm"]["temperature"],
            api_key=cfg["planner"]["llm"].get("api_key") or None,
        )

        candidates, _, _, _ = await detector.detect(
            segments=segments,
            total_duration=total_duration,
            language=subtitle.language,
            intent=f"提取与'{theme}'相关的精彩片段",
            clip_count=3,
            clip_duration_min=15,
            clip_duration_max=60,
            audio=audio,
        )

        # Tag with source video
        for c in candidates:
            c.title = f"[{os.path.basename(video_path)}] {c.title}"

        all_candidates.extend(candidates)
        total_found += len(candidates)

    # Select best across all videos
    all_candidates.sort(key=lambda c: c.weighted_score, reverse=True)

    # Limit by target_duration
    selected = []
    acc_duration = 0.0
    for c in all_candidates:
        if acc_duration + c.duration <= target_duration:
            selected.append(c)
            acc_duration += c.duration

    return {
        "success": True,
        "theme": theme,
        "clips": [
            {
                "index": i,
                "title": c.title,
                "start": c.start,
                "end": c.end,
                "duration": c.duration,
                "reason": c.reason,
                "score": c.weighted_score,
            }
            for i, c in enumerate(selected)
        ],
        "analysis": {
            "videos_processed": len(video_paths),
            "highlights_found": total_found,
            "highlights_selected": len(selected),
            "total_duration": round(acc_duration, 1),
        },
        "note": "跨视频片段需要手动拼接。后续版本将支持自动合并。",
    }


def highlight_reel_tool(
    video_paths: list[str],
    theme: str,
    target_duration: int = 180,
) -> dict:
    """
    从多个视频中提取精彩片段合成集锦视频。支持跨视频主题聚合。

    Args:
        video_paths: 输入视频文件路径列表
        theme: 集锦主题，如'搞笑瞬间''核心观点'
        target_duration: 目标总时长(秒)

    Returns:
        包含跨视频精选片段的字典
    """
    return run_async(_run_highlight_reel(
        video_paths=video_paths,
        theme=theme,
        target_duration=target_duration,
    ))
