#!/usr/bin/env python3
"""Quick local test script for Smart Clip MCP.

Usage:
    # Test with a video file (uses Whisper API + GPT-4o-mini)
    python test_clip.py /path/to/video.mp4

    # Test with custom options
    python test_clip.py /path/to/video.mp4 --count 3 --intent "提取金句"

    # Test analyze only (no clipping, just see what LLM picks)
    python test_clip.py /path/to/video.mp4 --analyze-only

Requires:
    - OPENAI_API_KEY environment variable
    - ffmpeg installed on system
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

# Add project src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_clip")


async def run_test(
    video_path: str,
    intent: str,
    clip_count: int,
    clip_min: int,
    clip_max: int,
    platform: str,
    analyze_only: bool,
    output_dir: str,
    whisper_mode: str,
    whisper_model: str,
    language: str,
):
    from smart_clip.analyzer import SubtitleExtractor, AudioEnergyAnalyzer
    from smart_clip.planner import SpeechSegmenter, HighlightDetector, StrategyEngine
    from smart_clip.config import DEFAULT_CONFIG

    if not os.path.exists(video_path):
        logger.error(f"Video not found: {video_path}")
        sys.exit(1)

    # Override config from CLI args
    cfg = DEFAULT_CONFIG
    cfg["analyzer"]["whisper"]["mode"] = whisper_mode
    cfg["analyzer"]["whisper"]["model"] = whisper_model
    cfg["analyzer"]["whisper"]["language"] = language

    # ─── Phase 1: Analyze ───
    logger.info("=" * 60)
    logger.info("Phase 1: Analyzing video...")
    logger.info(f"  Video: {video_path}")
    logger.info(f"  Whisper mode: {whisper_mode}, model: {whisper_model}, lang: {language}")
    logger.info("=" * 60)

    # 1a. Subtitle extraction
    extractor = SubtitleExtractor(
        mode=whisper_mode,
        language=language,
        model=whisper_model,
    )
    subtitle = await extractor.extract(video_path, language=language)

    if not subtitle.segments:
        logger.error("No speech detected in video. Aborting.")
        sys.exit(1)

    total_duration = subtitle.segments[-1].end
    speech_ratio = sum(s.end - s.start for s in subtitle.segments) / total_duration if total_duration > 0 else 0

    logger.info(f"✓ Subtitle extraction done:")
    logger.info(f"  Segments: {len(subtitle.segments)}")
    logger.info(f"  Duration: {total_duration:.1f}s")
    logger.info(f"  Speech ratio: {speech_ratio:.2f}")
    logger.info(f"  Full text preview: {subtitle.full_text[:200]}...")

    # 1b. Audio energy analysis (optional, graceful if librosa not installed)
    audio = None
    try:
        audio_cfg = cfg["analyzer"]["audio"]
        audio_analyzer = AudioEnergyAnalyzer(
            energy_percentile=audio_cfg["energy_percentile"],
            silence_threshold=audio_cfg["silence_threshold"],
            sample_rate=audio_cfg["sample_rate"],
        )
        audio = await audio_analyzer.analyze(video_path)
        logger.info(f"✓ Audio analysis done: {len(audio.peaks)} peaks, {len(audio.silences)} silences")
    except ImportError:
        logger.warning("librosa not installed, skipping audio analysis")
    except Exception as e:
        logger.warning(f"Audio analysis failed: {e}, continuing without it")

    # ─── Phase 2: Plan ───
    logger.info("=" * 60)
    logger.info("Phase 2: Planning clips with LLM...")
    logger.info("=" * 60)

    segmenter = SpeechSegmenter(max_duration=clip_max)
    segments = segmenter.segment(subtitle, audio, max_clip_duration=clip_max)
    logger.info(f"✓ Segmented into {len(segments)} speech segments")

    llm_cfg = cfg["planner"]["llm"]
    detector = HighlightDetector(
        model=llm_cfg["model"],
        temperature=llm_cfg["temperature"],
        api_key=llm_cfg.get("api_key") or None,
    )

    candidates, summary, content_type, tone = await detector.detect(
        segments=segments,
        total_duration=total_duration,
        language=language,
        intent=intent,
        clip_count=clip_count,
        clip_duration_min=clip_min,
        clip_duration_max=clip_max,
        audio=audio,
    )

    logger.info(f"✓ LLM detected {len(candidates)} highlight candidates")
    logger.info(f"  Summary: {summary}")
    logger.info(f"  Content type: {content_type}, Tone: {tone}")

    for i, c in enumerate(candidates):
        logger.info(f"  [{i+1}] {c.start:.1f}s-{c.end:.1f}s | score={c.weighted_score:.2f} | {c.title}")
        logger.info(f"       Reason: {c.reason}")

    # Strategy
    strategy_cfg = cfg["planner"]["strategy"]
    engine = StrategyEngine(
        min_score=strategy_cfg["min_score"],
        min_gap=strategy_cfg["min_gap"],
        snap_margin=strategy_cfg["snap_margin"],
        clip_duration_min=clip_min,
        clip_duration_max=clip_max,
    )

    plan = engine.apply(
        candidates=candidates,
        subtitle=subtitle,
        audio=audio,
        clip_count=clip_count,
        platform=platform,
        with_subtitles=True,
        with_bgm=False,
        summary=summary,
        content_type=content_type,
        tone=tone,
    )

    logger.info(f"✓ Strategy selected {len(plan.clips)} final clips:")
    for i, clip in enumerate(plan.clips):
        logger.info(f"  [{i+1}] {clip.start:.1f}s-{clip.end:.1f}s ({clip.duration:.1f}s) | {clip.title}")

    if analyze_only:
        logger.info("\n--analyze-only mode: skipping execution")
        # Save plan as JSON
        plan_path = os.path.join(output_dir, "edit_plan.json")
        os.makedirs(output_dir, exist_ok=True)
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan.model_dump(), f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Edit plan saved to {plan_path}")
        # Also return structured result
        return {
            "success": True,
            "analyze_only": True,
            "summary": summary,
            "content_type": content_type,
            "tone": tone,
            "plan": plan.model_dump(),
        }

    # ─── Phase 3: Execute ───
    logger.info("=" * 60)
    logger.info("Phase 3: Executing clips...")
    logger.info("=" * 60)

    from smart_clip.executor import ClipExecutor
    from smart_clip.models.plan import ExecuteConfig

    executor = ClipExecutor(use_mcp_video=cfg["executor"]["mcp_video"]["enabled"])
    exec_config = ExecuteConfig(
        video_path=video_path,
        output_dir=output_dir,
        format=cfg["executor"]["output"]["format"],
        quality=cfg["executor"]["output"]["quality"],
        codec=cfg["executor"]["output"]["codec"],
    )

    result = await executor.execute(plan, exec_config)

    if result.success:
        logger.info(f"✓ All done! {len(result.clips)} clips saved to {output_dir}")
        for clip in result.clips:
            logger.info(f"  [{clip.index+1}] {clip.output_path} ({clip.duration:.1f}s)")
    else:
        logger.error(f"Execution failed: {result.error}")


def main():
    parser = argparse.ArgumentParser(description="Smart Clip MCP - Local Test")
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("--intent", default="提取精彩片段", help="Editing intent")
    parser.add_argument("--count", type=int, default=5, help="Number of clips")
    parser.add_argument("--min", type=int, default=15, help="Min clip duration (seconds)")
    parser.add_argument("--max", type=int, default=90, help="Max clip duration (seconds)")
    parser.add_argument("--platform", default="original", help="Target platform")
    parser.add_argument("--output", default="./smart-clip-output", help="Output directory")
    parser.add_argument("--analyze-only", action="store_true", help="Only analyze, don't clip")
    parser.add_argument("--whisper-mode", default="api", choices=["api", "local"], help="Whisper mode")
    parser.add_argument("--whisper-model", default="base", help="Whisper model name (for local mode)")
    parser.add_argument("--language", default="zh", help="Language code")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable is required")
        logger.error("Set it with: export OPENAI_API_KEY=sk-...")
        sys.exit(1)

    asyncio.run(run_test(
        video_path=args.video,
        intent=args.intent,
        clip_count=args.count,
        clip_min=args.min,
        clip_max=args.max,
        platform=args.platform,
        analyze_only=args.analyze_only,
        output_dir=args.output,
        whisper_mode=args.whisper_mode,
        whisper_model=args.whisper_model,
        language=args.language,
    ))


if __name__ == "__main__":
    main()
