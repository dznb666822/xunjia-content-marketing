"""smart_clip tool — auto-detect highlights and clip from long video."""

from __future__ import annotations

import logging
import os

from smart_clip.analyzer import AudioEnergyAnalyzer
from smart_clip.planner import SpeechSegmenter, HighlightDetector, StrategyEngine
from smart_clip.executor import ClipExecutor
from smart_clip.models.plan import ExecuteConfig
from smart_clip.models.result import ClipResult, AnalysisInfo
from smart_clip.config import DEFAULT_CONFIG
from smart_clip.utils import run_async
from smart_clip.resolver import VideoResolver

logger = logging.getLogger(__name__)


async def _run_smart_clip(
    video_input: str,
    intent: str = "提取精彩片段",
    clip_count: int = 5,
    clip_duration_min: int = 15,
    clip_duration_max: int = 90,
    platform: str = "original",
    with_subtitles: bool = True,
    with_bgm: bool = False,
    output_dir: str | None = None,
    template: str = "default",
    analyze_only: bool = False,
    srt_path: str | None = None,
) -> dict:
    """Core logic for smart_clip tool. video_input can be a local path or a URL."""
    if output_dir is None:
        output_dir = os.getenv("SMART_CLIP_OUTPUT_DIR", "./smart-clip-output")

    cfg = DEFAULT_CONFIG
    whisper_cfg = cfg["analyzer"]["whisper"]

    # Resolve input: URL → download video+subs, file → SRT/Whisper
    resolver = VideoResolver(
        whisper_mode=whisper_cfg["mode"],
        language=whisper_cfg["language"],
        whisper_model=whisper_cfg["model"],
        api_key=whisper_cfg.get("api_key") or None,
    )
    try:
        video_path, subtitle, source_info = await resolver.resolve(video_input, srt_path)
    except Exception as e:
        return {"success": False, "error": f"Failed to resolve input: {e}"}

    # Phase 1: Analyze (subtitles already resolved above, now analyze audio)
    logger.info("Phase 1: Analyzing video...")

    audio_cfg = cfg["analyzer"]["audio"]
    audio_analyzer = AudioEnergyAnalyzer(
        energy_percentile=audio_cfg["energy_percentile"],
        silence_threshold=audio_cfg["silence_threshold"],
        sample_rate=audio_cfg["sample_rate"],
    )
    audio = await audio_analyzer.analyze(video_path)

    total_duration = subtitle.segments[-1].end if subtitle.segments else 0.0
    speech_ratio = sum(s.end - s.start for s in subtitle.segments) / total_duration if total_duration > 0 else 0.0

    logger.info(f"Analysis done: {len(subtitle.segments)} segments, {total_duration:.1f}s, speech ratio: {speech_ratio:.2f}")

    # Phase 2: Plan
    logger.info("Phase 2: Planning clips...")

    segmenter = SpeechSegmenter(max_duration=clip_duration_max)
    segments = segmenter.segment(subtitle, audio, max_clip_duration=clip_duration_max)

    llm_cfg = cfg["planner"]["llm"]
    detector = HighlightDetector(
        model=llm_cfg["model"],
        temperature=llm_cfg["temperature"],
        api_key=llm_cfg.get("api_key") or None,
        base_url=llm_cfg.get("base_url") or None,
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
        template=template,
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
        platform=platform,
        with_subtitles=with_subtitles,
        with_bgm=with_bgm,
        summary=summary,
        content_type=content_type,
        tone=tone,
    )

    logger.info(f"Plan: {len(plan.clips)} clips selected, total {plan.total_selected_duration:.1f}s")

    # Phase 3: Execute (skip if analyze_only)
    if analyze_only:
        logger.info("analyze_only=True: skipping execution phase")
        analysis = AnalysisInfo(
            total_duration=total_duration,
            speech_ratio=round(speech_ratio, 2),
            language=subtitle.language,
            highlights_found=len(candidates),
            highlights_selected=len(plan.clips),
        )
        return {
            "success": True,
            "analyze_only": True,
            "source": source_info,
            "analysis": analysis.model_dump(),
            "plan": plan.model_dump(),
            "candidates": [
                {
                    "start": c.start,
                    "end": c.end,
                    "duration": round(c.duration, 1),
                    "title": c.title,
                    "reason": c.reason,
                    "weighted_score": c.weighted_score,
                    "suggested_hook": c.suggested_hook,
                }
                for c in candidates
            ],
            "summary": summary,
            "content_type": content_type,
            "tone": tone,
        }

    logger.info("Phase 3: Executing clips...")

    executor = ClipExecutor(use_mcp_video=cfg["executor"]["mcp_video"]["enabled"])
    exec_config = ExecuteConfig(
        video_path=video_path,
        output_dir=output_dir,
        format=cfg["executor"]["output"]["format"],
        quality=cfg["executor"]["output"]["quality"],
        codec=cfg["executor"]["output"]["codec"],
    )

    result = await executor.execute(plan, exec_config)

    # Build response
    analysis = AnalysisInfo(
        total_duration=total_duration,
        speech_ratio=round(speech_ratio, 2),
        language=subtitle.language,
        highlights_found=len(candidates),
        highlights_selected=len(result.clips),
    )
    result.analysis = analysis

    final = result.model_dump()
    final["source"] = source_info
    return final


def smart_clip_tool(
    video_input: str,
    intent: str = "提取精彩片段",
    clip_count: int = 5,
    clip_duration_min: int = 15,
    clip_duration_max: int = 90,
    platform: str = "original",
    with_subtitles: bool = True,
    with_bgm: bool = False,
    output_dir: str = "./smart-clip-output",
) -> dict:
    """
    从长视频中自动识别精彩片段并裁切输出。支持文件路径和URL。适用于口播、播客、直播回放等语音驱动内容。

    Args:
        video_input: 输入视频文件路径或URL (如 https://www.bilibili.com/video/xxx)
        intent: 剪辑意图，自然语言描述。如：'提取最精彩的5个片段' / '找出所有金句'
        clip_count: 期望输出的片段数量
        clip_duration_min: 单片段最短秒数
        clip_duration_max: 单片段最长秒数
        platform: 目标平台 (auto/tiktok/youtube_shorts/instagram_reels/youtube/original)
        with_subtitles: 是否烧录字幕
        with_bgm: 是否添加背景音乐
        output_dir: 输出目录

    Returns:
        包含输出片段列表和分析摘要的字典
    """
    return run_async(_run_smart_clip(
        video_input=video_input,
        intent=intent,
        clip_count=clip_count,
        clip_duration_min=clip_duration_min,
        clip_duration_max=clip_duration_max,
        platform=platform,
        with_subtitles=with_subtitles,
        with_bgm=with_bgm,
        output_dir=output_dir,
    ))
