"""analyze_content tool — analyze video content without clipping."""

from __future__ import annotations

import logging
import os

from smart_clip.analyzer import SubtitleExtractor, AudioEnergyAnalyzer
from smart_clip.planner import SpeechSegmenter, HighlightDetector
from smart_clip.config import DEFAULT_CONFIG
from smart_clip.utils import run_async

logger = logging.getLogger(__name__)


async def _run_analyze_content(
    video_path: str,
    focus: str = "all",
) -> dict:
    """Core logic for analyze_content tool."""
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
    speech_ratio = sum(s.end - s.start for s in subtitle.segments) / total_duration if total_duration > 0 else 0.0

    result = {
        "success": True,
        "metadata": {
            "total_duration": round(total_duration, 1),
            "speech_ratio": round(speech_ratio, 2),
            "language": subtitle.language,
            "segment_count": len(subtitle.segments),
            "audio_peaks": len(audio.peaks),
            "silence_count": len(audio.silences),
            "estimated_tempo": round(audio.tempo, 1),
        },
    }

    # Optional: Highlight analysis
    if focus in ("highlights", "all"):
        segmenter = SpeechSegmenter()
        segments = segmenter.segment(subtitle, audio)

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
            intent="识别精彩片段",
            clip_count=10,
            clip_duration_min=15,
            clip_duration_max=90,
            audio=audio,
        )

        result["highlights"] = [
            {
                "index": i,
                "start": c.start,
                "end": c.end,
                "duration": round(c.duration, 1),
                "title": c.title,
                "reason": c.reason,
                "score": c.weighted_score,
            }
            for i, c in enumerate(candidates)
        ]
        result["content_analysis"] = {
            "summary": summary,
            "content_type": content_type,
            "tone": tone,
        }

    # Optional: Structure analysis
    if focus in ("structure", "all"):
        segmenter = SpeechSegmenter()
        segments = segmenter.segment(subtitle, audio)

        result["structure"] = [
            {
                "index": seg.index,
                "start": seg.start,
                "end": seg.end,
                "duration": round(seg.duration, 1),
                "text_preview": seg.text[:100] + "..." if len(seg.text) > 100 else seg.text,
            }
            for seg in segments
        ]

    # Optional: Sentiment analysis
    if focus in ("sentiment", "all") and subtitle.segments:
        result["sentiment"] = {
            "full_text_preview": subtitle.full_text[:500] + "..." if len(subtitle.full_text) > 500 else subtitle.full_text,
        }

    return result


def analyze_content_tool(
    video_path: str,
    focus: str = "all",
) -> dict:
    """
    分析视频内容，输出结构化报告，不执行剪辑。用于预览和决策。

    Args:
        video_path: 输入视频文件路径
        focus: 分析重点 (highlights/structure/sentiment/all)

    Returns:
        包含内容分析报告的字典
    """
    return run_async(_run_analyze_content(video_path=video_path, focus=focus))
