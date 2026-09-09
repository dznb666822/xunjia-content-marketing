"""LLM-driven highlight detection module."""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from smart_clip.models.plan import ClipCandidate, ClipScores
from smart_clip.models.audio import AudioProfile
from smart_clip.planner.segmenter import SpeechSegment
from smart_clip.planner.prompts import (
    HIGHLIGHT_DETECTION_PROMPT,
    QUOTE_EXTRACTION_PROMPT,
    LIVESTREAM_CLIP_PROMPT,
)

logger = logging.getLogger(__name__)

# Scoring weights for weighted_score calculation
SCORE_WEIGHTS = {
    "information_density": 0.3,
    "emotional_tension": 0.25,
    "completeness": 0.2,
    "virality": 0.15,
    "rhythm_fit": 0.1,
}


class HighlightDetector:
    """Use LLM to identify highlight clips from speech segments."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model
        self.temperature = temperature
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)

    async def detect(
        self,
        segments: list[SpeechSegment],
        total_duration: float,
        language: str = "zh",
        intent: str = "提取精彩片段",
        clip_count: int = 5,
        clip_duration_min: int = 15,
        clip_duration_max: int = 90,
        audio: AudioProfile | None = None,
        template: str = "default",
    ) -> list[ClipCandidate]:
        """
        Detect highlight clips using LLM.

        Args:
            segments: Speech segments from the segmenter.
            total_duration: Total video duration in seconds.
            language: Content language code.
            intent: User's editing intent (natural language).
            clip_count: Desired number of clips.
            clip_duration_min: Minimum clip duration in seconds.
            clip_duration_max: Maximum clip duration in seconds.
            audio: Optional audio profile for livestream template.
            template: Prompt template to use ("default", "quote", "livestream").

        Returns:
            List of ClipCandidate sorted by weighted_score descending.
        """
        prompt = self._build_prompt(
            segments=segments,
            total_duration=total_duration,
            language=language,
            intent=intent,
            clip_count=clip_count,
            clip_duration_min=clip_duration_min,
            clip_duration_max=clip_duration_max,
            audio=audio,
            template=template,
        )

        logger.info(f"Calling LLM ({self.model}) for highlight detection")
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "你是专业视频剪辑师，擅长识别精彩片段。严格按 JSON 格式输出。",
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        clips = []
        for clip_data in result.get("clips", []):
            scores = ClipScores(
                information_density=clip_data.get("scores", {}).get("information_density", 0),
                emotional_tension=clip_data.get("scores", {}).get("emotional_tension", 0),
                completeness=clip_data.get("scores", {}).get("completeness", 0),
                virality=clip_data.get("scores", {}).get("virality", 0),
                rhythm_fit=clip_data.get("scores", {}).get("rhythm_fit", 0),
            )

            # Recalculate weighted score to ensure consistency
            weighted = sum(
                getattr(scores, k) * v for k, v in SCORE_WEIGHTS.items()
            )

            clips.append(
                ClipCandidate(
                    segment_index=clip_data.get("segment_index", 0),
                    start=float(clip_data.get("start", 0)),
                    end=float(clip_data.get("end", 0)),
                    title=clip_data.get("title", ""),
                    reason=clip_data.get("reason", ""),
                    scores=scores,
                    weighted_score=round(weighted, 2),
                    suggested_hook=clip_data.get("suggested_hook", ""),
                    quote_text=clip_data.get("quote_text"),
                    hook_type=clip_data.get("hook_type"),
                    clip_type=clip_data.get("clip_type"),
                    energy_level=clip_data.get("energy_level"),
                )
            )

        # Sort by weighted score descending
        clips.sort(key=lambda c: c.weighted_score, reverse=True)

        # Validate time codes against segments
        clips = self._validate_clips(clips, segments)

        return clips, result.get("summary", ""), result.get("content_type", ""), result.get("tone", "")

    def _build_prompt(
        self,
        segments: list[SpeechSegment],
        total_duration: float,
        language: str,
        intent: str,
        clip_count: int,
        clip_duration_min: int,
        clip_duration_max: int,
        audio: AudioProfile | None,
        template: str,
    ) -> str:
        formatted = "\n".join(seg.format_for_prompt() for seg in segments)

        common_kwargs = {
            "total_duration": total_duration,
            "language": language,
            "formatted_segments": formatted,
            "clip_count": clip_count,
            "clip_duration_min": clip_duration_min,
            "clip_duration_max": clip_duration_max,
        }

        if template == "quote":
            return QUOTE_EXTRACTION_PROMPT.format(**common_kwargs)
        elif template == "livestream":
            peaks_text = ""
            if audio and audio.peaks:
                peaks_text = "\n".join(
                    f"  - {p.time:.1f}s (强度: {p.intensity:.1f}x)" for p in audio.peaks[:20]
                )
            else:
                peaks_text = "  (未检测到明显峰值)"
            return LIVESTREAM_CLIP_PROMPT.format(
                **common_kwargs, audio_peaks=peaks_text
            )
        else:
            return HIGHLIGHT_DETECTION_PROMPT.format(**common_kwargs, intent=intent)

    def _validate_clips(
        self, clips: list[ClipCandidate], segments: list[SpeechSegment]
    ) -> list[ClipCandidate]:
        """Validate that clip time codes fall within the video's segment range."""
        if not segments:
            return clips

        max_time = segments[-1].end
        valid_clips = []

        for clip in clips:
            # Clamp to valid range
            clip.start = max(0.0, min(clip.start, max_time))
            clip.end = max(clip.start, min(clip.end, max_time))

            if clip.end - clip.start >= 5.0:  # Minimum 5 seconds
                valid_clips.append(clip)
            else:
                logger.warning(f"Dropping clip with invalid duration: {clip.start}-{clip.end}")

        return valid_clips
