"""包装层 LLM 决策器(SOP §3.1 第二层 / §4 四大引擎)。

PackagingPlanner:基于已选定的 clips + 完整字幕 + Style 名,一次性调 LLM 产出
完整 PackagingLayer JSON(字幕样式/动效/关键词高亮 + SFX 触发点 + BGM 卡点 + 画面特效 + 画面素材引用)。

V2 不实现 SFX/BGM/Effect 引擎的代码执行,只做"决策",引擎本身在后续 M5/M6 阶段实现。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from smart_clip.models.plan import (
    BgmPlan,
    EffectEvent,
    KeywordHighlight,
    PackagingLayer,
    SfxEvent,
    StyledSubtitle,
    SubtitleStyle,
    VisualAssetRef,
)
from smart_clip.planner.prompts import PACKAGING_DECISION_PROMPT
from smart_clip.planner.segmenter import SpeechSegment
from smart_clip.planner.style_selector import get_style_by_name
from smart_clip.models.plan import Style
from smart_clip.models.audio import AudioProfile

logger = logging.getLogger(__name__)


class PackagingPlanner:
    """基于 LLM 的包装层决策器。"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model
        self.temperature = temperature
        kwargs: dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)

    async def decide(
        self,
        clips: list,
        segments: list[SpeechSegment],
        style: Style,
        total_duration: float,
        audio: AudioProfile | None = None,
        language: str = "zh",
    ) -> tuple[PackagingLayer, list[VisualAssetRef]]:
        """调 LLM 决策包装层 + 画面素材层。

        Args:
            clips: HighlightDetector 选定的 ClipCandidate 列表
            segments: 完整字幕分段(用于 LLM 参考时间窗)
            style: 已选定的 Style(含 name/display_name/description/config)
            total_duration: 视频总时长
            audio: 可选音频 profile(用于参考 BPM/能量峰)
            language: 字幕语言

        Returns:
            (packaging_layer, visual_assets)
        """
        prompt = self._build_prompt(
            clips=clips,
            segments=segments,
            style=style,
            total_duration=total_duration,
            audio=audio,
        )

        logger.info(f"PackagingPlanner: calling LLM ({self.model}) for packaging decision")
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是短视频网感剪辑师,负责为已选定的精彩片段产出完整包装层方案(字幕样式+音效+BGM+特效+画面素材)。"
                        "严格按 JSON 格式输出,时间字段用秒数,所有枚举值严格按 prompt 规定。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or "{}"
        result = json.loads(content)

        # 解析为 Pydantic 模型
        packaging = self._parse_packaging(result, style)
        visual_assets = self._parse_visual_assets(result)

        return packaging, visual_assets

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        clips: list,
        segments: list[SpeechSegment],
        style: Style,
        total_duration: float,
        audio: AudioProfile | None,
    ) -> str:
        clips_json = json.dumps(
            [
                {
                    "index": i,
                    "start": c.start,
                    "end": c.end,
                    "duration": round(c.duration, 1),
                    "title": c.title,
                    "reason": c.reason,
                }
                for i, c in enumerate(clips)
            ],
            ensure_ascii=False,
            indent=2,
        )
        formatted_segments = "\n".join(seg.format_for_prompt() for seg in segments[:50])

        # Style 字幕样式基准
        sub_cfg = style.config.get("subtitle", {})
        style_subtitle_font = sub_cfg.get("font", "NotoSansSC-Bold")
        style_subtitle_animation = sub_cfg.get("animation", "pop")
        style_subtitle_highlight = sub_cfg.get("highlight", True)
        style_subtitle_position = sub_cfg.get("position", "bottom")

        # 音频节拍参考
        beat_info = "  (未提供音频节拍数据)"
        if audio and getattr(audio, "bpm", None):
            beat_info = f"  - 估算 BPM: {audio.bpm:.0f}\n  - 能量峰(前 20): "
            peaks = getattr(audio, "peaks", None) or []
            if peaks:
                beat_info += "; ".join(
                    f"{p.time:.1f}s ({p.intensity:.1f}x)" for p in peaks[:20]
                )
            else:
                beat_info += "(未检测到明显峰值)"

        return PACKAGING_DECISION_PROMPT.format(
            clip_count=len(clips),
            total_duration=total_duration,
            style_name=style.name,
            style_display_name=style.display_name,
            style_description=style.description,
            style_subtitle_font=style_subtitle_font,
            style_subtitle_animation=style_subtitle_animation,
            style_subtitle_highlight=style_subtitle_highlight,
            style_subtitle_position=style_subtitle_position,
            clips_json=clips_json,
            formatted_segments=formatted_segments,
            beat_info=beat_info,
        )

    def _parse_packaging(self, result: dict, style: Style) -> PackagingLayer:
        """解析 LLM 输出的 subtitles/sfx_events/bgm/effects 为 PackagingLayer。"""
        # 1. subtitles
        subs: list[StyledSubtitle] = []
        for s in result.get("subtitles", []):
            try:
                style_dict = s.get("style", {})
                # Style 基准合并子句样式
                merged = {
                    "style_preset": style.config.get("subtitle", {}).get("style_preset", "luxury_bilingual_white"),
                    "font": style_dict.get("font", style.config.get("subtitle", {}).get("font", "NotoSansSC-Bold")),
                    "animation": style_dict.get("animation", style.config.get("subtitle", {}).get("animation", "pop")),
                    "highlight": style_dict.get("highlight", style.config.get("subtitle", {}).get("highlight", True)),
                    "bilingual": style_dict.get("bilingual", style.config.get("subtitle", {}).get("bilingual", True)),
                    "position": style_dict.get("position", style.config.get("subtitle", {}).get("position", "bottom")),
                }
                kw_list: list[KeywordHighlight] = []
                for kw in s.get("keywords", []):
                    kw_list.append(
                        KeywordHighlight(
                            text=str(kw.get("text", "")),
                            start=float(kw.get("start", 0)),
                            end=float(kw.get("end", 0)),
                            mode=kw.get("mode", "bold"),
                        )
                    )
                subs.append(
                    StyledSubtitle(
                        segment_index=int(s.get("segment_index", 0)),
                        start=float(s.get("start", 0)),
                        end=float(s.get("end", 0)),
                        text=str(s.get("text", "")),
                        style=SubtitleStyle(**merged),
                        keywords=kw_list,
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping malformed subtitle: {e}")

        # 2. sfx_events
        sfx_list: list[SfxEvent] = []
        for ev in result.get("sfx_events", []):
            try:
                sfx_list.append(
                    SfxEvent(
                        trigger_at=float(ev.get("trigger_at", 0)),
                        category=ev.get("category", "emphasis"),
                        intensity=float(ev.get("intensity", 0.7)),
                        reason=ev.get("reason", ""),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping malformed sfx_event: {e}")

        # 3. bgm
        bgm_raw = result.get("bgm", {})
        try:
            bgm = BgmPlan(
                track_id=bgm_raw.get("track_id"),
                track_name=str(bgm_raw.get("track_name", "")),
                tone=bgm_raw.get("tone", "conversational"),
                bpm=int(bgm_raw.get("bpm", 90)),
                beat_points=[float(b) for b in bgm_raw.get("beat_points", [])],
                duck_db=float(bgm_raw.get("duck_db", -12.0)),
            )
        except Exception as e:
            logger.warning(f"Fallback BgmPlan due to: {e}")
            bgm = BgmPlan()

        # 4. effects
        eff_list: list[EffectEvent] = []
        for ev in result.get("effects", []):
            try:
                eff_list.append(
                    EffectEvent(
                        trigger_at=float(ev.get("trigger_at", 0)),
                        effect_type=ev.get("effect_type", "zoom_in"),
                        duration=float(ev.get("duration", 0.5)),
                        params=ev.get("params", {}) or {},
                        reason=ev.get("reason", ""),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping malformed effect: {e}")

        return PackagingLayer(subtitles=subs, sfx_events=sfx_list, bgm=bgm, effects=eff_list)

    def _parse_visual_assets(self, result: dict) -> list[VisualAssetRef]:
        """解析 visual_assets 列表。"""
        out: list[VisualAssetRef] = []
        for va in result.get("visual_assets", []):
            try:
                out.append(
                    VisualAssetRef(
                        trigger_at=float(va.get("trigger_at", 0)),
                        asset_type=va.get("asset_type", "broll"),
                        topic=str(va.get("topic", "")),
                        content=str(va.get("content", "")),
                        style_tag=va.get("style_tag", "natural"),
                        source=va.get("source", "programmatic"),
                        template_id=va.get("template_id"),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping malformed visual_asset: {e}")
        return out
