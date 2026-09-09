"""get_video_plan tool —— 生成 V2.0 完整 VideoPlan(剪辑方案)。

与 get_edit_plan 的区别:
- get_edit_plan:V1,只决策"剪什么",返回片段层
- get_video_plan:V2,决策"剪什么 + 怎么包装",返回 VideoPlan 三层结构(片段 + 包装 + 画面素材 + Style)

不执行剪辑,只产出方案;后续接 smart_clip 走完整渲染。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta

from smart_clip.analyzer import SubtitleExtractor, AudioEnergyAnalyzer
from smart_clip.planner import SpeechSegmenter, HighlightDetector
from smart_clip.planner.packaging import PackagingPlanner
from smart_clip.planner.style_selector import select_style
from smart_clip.config import DEFAULT_CONFIG
from smart_clip.models.plan import VideoPlan
from smart_clip.utils import run_async

logger = logging.getLogger(__name__)

# 时区(对齐 web 的 docker-compose:Asia/Shanghai)
_TZ_CN = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_TZ_CN).strftime("%Y-%m-%d %H:%M:%S")


async def _run_get_video_plan(
    video_path: str,
    intent: str = "提取精彩片段",
    clip_count: int = 5,
    clip_duration_min: int = 15,
    clip_duration_max: int = 90,
    style: str | None = None,
    custom_style_config: dict | None = None,
) -> dict:
    """Core logic for get_video_plan tool.

    Args:
        video_path: 视频文件路径
        intent: 剪辑意图
        clip_count: 期望片段数
        clip_duration_min/max: 单片段时长范围
        style: 强制指定 Style 名(None 则由 StyleSelector 决策)
        custom_style_config: custom 模式的覆盖配置

    Returns:
        含完整 VideoPlan JSON 的字典(SOP §3.1 三层结构)
    """
    if not os.path.exists(video_path):
        return {"success": False, "error": f"Video file not found: {video_path}"}

    cfg = DEFAULT_CONFIG

    # ---- Phase 1: Analyze(Whisper 字幕 + 音频能量) ----
    logger.info("[get_video_plan] Phase 1: analyzing video...")
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
    logger.info(
        f"[get_video_plan] Analysis: {len(subtitle.segments)} segments, "
        f"{total_duration:.1f}s, audio bpm={getattr(audio, 'bpm', None)}"
    )

    # ---- Phase 2: Highlight Detection(片段层) ----
    logger.info("[get_video_plan] Phase 2: detecting highlights via LLM...")
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
    logger.info(
        f"[get_video_plan] HighlightDetector: {len(candidates)} candidates, "
        f"content_type={content_type}, tone={tone}"
    )

    # ---- Phase 3: Style Selection ----
    logger.info("[get_video_plan] Phase 3: selecting Style...")
    if style and style != "auto":
        # 强制指定
        from smart_clip.planner.style_selector import get_style_by_name
        chosen_style = get_style_by_name(style)
    else:
        chosen_style = select_style(
            content_type=content_type,
            tone=tone,
            custom_config=custom_style_config,
        )
    logger.info(f"[get_video_plan] Style selected: {chosen_style.name} ({chosen_style.display_name})")

    # ---- Phase 4: Packaging Decision(包装层 + 画面素材层) ----
    logger.info("[get_video_plan] Phase 4: deciding packaging via LLM...")
    planner = PackagingPlanner(
        model=cfg["planner"]["llm"]["model"],
        temperature=cfg["planner"]["llm"]["temperature"],
        api_key=cfg["planner"]["llm"].get("api_key") or None,
        base_url=cfg["planner"]["llm"].get("base_url") or None,
    )
    packaging, visual_assets = await planner.decide(
        clips=candidates,
        segments=segments,
        style=chosen_style,
        total_duration=total_duration,
        audio=audio,
        language=subtitle.language,
    )
    logger.info(
        f"[get_video_plan] Packaging: {len(packaging.subtitles)} subtitles, "
        f"{len(packaging.sfx_events)} sfx, {len(packaging.effects)} effects, "
        f"{len(visual_assets)} visual_assets"
    )

    # ---- Phase 5: 组装 VideoPlan ----
    plan = VideoPlan(
        clips=candidates,
        total_selected_duration=sum(c.duration for c in candidates),
        platform="original",
        content_type=content_type,
        tone=tone,
        summary=summary,
        style=chosen_style,
        packaging=packaging,
        visual_assets=visual_assets,
        source_video=video_path,
        generated_by=cfg["planner"]["llm"]["model"],
        schema_version="2.0",
        created_at=_now_iso(),
    )

    return {
        "success": True,
        "video_plan": plan.model_dump(),
        "video_path": video_path,
        "note": "V2.0 完整剪辑方案,包含片段层+包装层+画面素材层+Style。审核通过后可接 smart_package 工具一键渲染成片。",
    }


def get_video_plan_tool(
    video_path: str,
    intent: str = "提取精彩片段",
    clip_count: int = 5,
    clip_duration_min: int = 15,
    clip_duration_max: int = 90,
    style: str | None = None,
    custom_style_config: str | None = None,
) -> dict:
    """
    生成 V2.0 完整 VideoPlan(剪辑方案),不执行剪辑,只产出方案供人工审核。
    返回的 video_plan 包含 SOP §3.1 定义的三层结构:
    - 片段层(clips + summary + content_type + tone)
    - 包装层(packaging: subtitles + sfx_events + bgm + effects)
    - 画面素材层(visual_assets)
    - Style(style: name + display_name + config)

    Args:
        video_path: 视频文件路径
        intent: 剪辑意图
        clip_count: 期望片段数
        clip_duration_min/max: 单片段时长范围
        style: 强制 Style 名(luxury_bilingual_white/knowledge/entertainment/news/vlog/cute/custom),None 则自动
        custom_style_config: custom 模式的 JSON 字符串,覆盖默认配置

    Returns:
        含完整 VideoPlan JSON 的字典(未执行)
    """
    parsed_custom: dict | None = None
    if custom_style_config:
        try:
            parsed_custom = json.loads(custom_style_config)
        except Exception as e:
            return {"success": False, "error": f"custom_style_config 解析失败: {e}"}

    return run_async(_run_get_video_plan(
        video_path=video_path,
        intent=intent,
        clip_count=clip_count,
        clip_duration_min=clip_duration_min,
        clip_duration_max=clip_duration_max,
        style=style,
        custom_style_config=parsed_custom,
    ))
