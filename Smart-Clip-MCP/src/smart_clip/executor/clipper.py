"""Clip executor — execute edit plans via mcp-video Python Client or FFmpeg fallback."""

from __future__ import annotations

import logging
import os
import subprocess

from smart_clip.models.plan import EditPlan, ClipCandidate, ExecuteConfig
from smart_clip.models.result import ClipOutput, ClipResult

logger = logging.getLogger(__name__)

# Platform → mcp-video template / aspect ratio mapping
PLATFORM_MAP = {
    "tiktok": {"aspect_ratio": "9:16", "template": "tiktok"},
    "youtube_shorts": {"aspect_ratio": "9:16", "template": "youtube_shorts"},
    "instagram_reels": {"aspect_ratio": "9:16", "template": "instagram_reels"},
    "youtube": {"aspect_ratio": "16:9", "template": None},
    "original": {"aspect_ratio": None, "template": None},
}

# mcp-video Client singleton (lazy init)
_mcp_video_client = None


def _get_mcp_video_client():
    """Lazily initialize mcp-video Client."""
    global _mcp_video_client
    if _mcp_video_client is None:
        try:
            from mcp_video import Client
            _mcp_video_client = Client()
            logger.info("mcp-video Python Client initialized")
        except ImportError:
            logger.warning("mcp-video not installed, all operations will use FFmpeg fallback")
            _mcp_video_client = False  # Sentinel: tried but not available
        except Exception as e:
            logger.warning(f"mcp-video Client init failed: {e}, using FFmpeg fallback")
            _mcp_video_client = False
    return _mcp_video_client if _mcp_video_client is not False else None


class ClipExecutor:
    """Execute edit plans: trim, add subtitles, resize, merge.

    Strategy:
        1. Try mcp-video Python Client (structured, high-level API)
        2. Fallback to direct FFmpeg (raw command-line)
    """

    def __init__(self, use_mcp_video: bool = True):
        self.use_mcp_video = use_mcp_video
        self._editor = None

    @property
    def editor(self):
        """Get or lazily init mcp-video Client."""
        if self._editor is None and self.use_mcp_video:
            self._editor = _get_mcp_video_client()
        return self._editor

    async def execute(self, plan: EditPlan, config: ExecuteConfig) -> ClipResult:
        """Execute an edit plan and generate output clips."""
        os.makedirs(config.output_dir, exist_ok=True)
        outputs = []

        for i, clip in enumerate(plan.clips):
            logger.info(f"Processing clip {i + 1}/{len(plan.clips)}: {clip.start:.1f}s - {clip.end:.1f}s")

            # Step 1: Trim
            clip_path = await self._trim_clip(
                config.video_path, clip, config.output_dir, i
            )

            # Step 2: Add subtitles (if enabled)
            if plan.with_subtitles and clip.title:
                clip_path = await self._add_subtitles(clip_path, clip, plan.platform)

            # Step 3: Resize / template for platform
            if plan.platform in PLATFORM_MAP and PLATFORM_MAP[plan.platform]["aspect_ratio"]:
                clip_path = await self._resize_for_platform(clip_path, plan.platform, config.output_dir, i)

            outputs.append(
                ClipOutput(
                    index=i,
                    output_path=clip_path,
                    start=clip.start,
                    end=clip.end,
                    duration=clip.duration,
                    reason=clip.reason,
                    score=clip.weighted_score,
                )
            )

        return ClipResult(
            success=True,
            clips=outputs,
            output_dir=config.output_dir,
        )

    # ------------------------------------------------------------------
    # Trim
    # ------------------------------------------------------------------

    async def _trim_clip(
        self, video_path: str, clip: ClipCandidate, output_dir: str, index: int
    ) -> str:
        """Trim a single clip from the video."""
        output_path = os.path.join(output_dir, f"clip_{index + 1:02d}.mp4")
        duration = clip.end - clip.start

        # Try mcp-video Python Client
        if self.editor:
            try:
                result = self.editor.trim(
                    video_path,
                    start=self._fmt_time(clip.start),
                    duration=self._fmt_time(duration),
                    output=output_path,
                )
                if result and os.path.exists(output_path):
                    logger.info(f"mcp-video trim OK: {output_path}")
                    return output_path
                logger.warning(f"mcp-video trim returned no output, falling back")
            except Exception as e:
                logger.warning(f"mcp-video trim failed: {e}, falling back to FFmpeg")

        # Fallback: direct FFmpeg
        cmd = [
            "ffmpeg", "-i", video_path,
            "-ss", str(clip.start),
            "-t", str(duration),
            "-c:v", "libx264", "-c:a", "aac",
            "-avoid_negative_ts", "1",
            "-y", output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)
        return output_path

    # ------------------------------------------------------------------
    # Subtitles
    # ------------------------------------------------------------------

    async def _add_subtitles(
        self, clip_path: str, clip: ClipCandidate, platform: str
    ) -> str:
        """Add subtitle overlay to clip."""
        srt_content = self._generate_srt(clip)
        if not srt_content.strip():
            return clip_path

        srt_path = clip_path.rsplit(".", 1)[0] + ".srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        output_path = clip_path.rsplit(".", 1)[0] + "_subtitled.mp4"

        # Try mcp-video Python Client
        if self.editor:
            try:
                result = self.editor.add_subtitles(
                    clip_path,
                    subtitles_path=srt_path,
                    output=output_path,
                )
                if result and os.path.exists(output_path):
                    logger.info(f"mcp-video add_subtitles OK: {output_path}")
                    self._cleanup(clip_path)
                    return output_path
                logger.warning("mcp-video add_subtitles returned no output, falling back")
            except Exception as e:
                logger.warning(f"mcp-video add_subtitles failed: {e}, falling back to FFmpeg")

        # Fallback: direct FFmpeg
        font_size = 24 if platform in ("tiktok", "youtube_shorts", "instagram_reels") else 20
        cmd = [
            "ffmpeg", "-i", clip_path,
            "-vf", f"subtitles={srt_path}:force_style='FontSize={font_size},PrimaryColour=&Hffffff&'",
            "-c:a", "copy",
            "-y", output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=300)
            self._cleanup(clip_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.warning(f"FFmpeg subtitle burn failed: {e}")
            return clip_path

    # ------------------------------------------------------------------
    # Platform resize / template
    # ------------------------------------------------------------------

    async def _resize_for_platform(
        self, clip_path: str, platform: str, output_dir: str, index: int
    ) -> str:
        """Resize clip for target platform using mcp-video template or FFmpeg."""
        preset = PLATFORM_MAP.get(platform)
        if not preset or not preset["aspect_ratio"]:
            return clip_path

        output_path = clip_path.rsplit(".", 1)[0] + f"_{platform}.mp4"

        # Try mcp-video template (one-step: resize + styling + captions)
        if self.editor and preset.get("template"):
            try:
                result = self.editor.template(
                    preset["template"],
                    clip_path,
                    output=output_path,
                )
                if result and os.path.exists(output_path):
                    logger.info(f"mcp-video template({preset['template']}) OK: {output_path}")
                    self._cleanup(clip_path)
                    return output_path
                logger.warning("mcp-video template returned no output, falling back")
            except Exception as e:
                logger.warning(f"mcp-video template failed: {e}, falling back to FFmpeg")

        # Try mcp-video resize
        if self.editor:
            try:
                result = self.editor.resize(
                    clip_path,
                    aspect_ratio=preset["aspect_ratio"],
                    output=output_path,
                )
                if result and os.path.exists(output_path):
                    logger.info(f"mcp-video resize OK: {output_path}")
                    self._cleanup(clip_path)
                    return output_path
                logger.warning("mcp-video resize returned no output, falling back")
            except Exception as e:
                logger.warning(f"mcp-video resize failed: {e}, falling back to FFmpeg")

        # Fallback: direct FFmpeg
        w, h = (1080, 1920) if "9:16" in preset["aspect_ratio"] else (1920, 1080)
        cmd = [
            "ffmpeg", "-i", clip_path,
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
            "-c:a", "copy",
            "-y", output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=300)
            self._cleanup(clip_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.warning(f"FFmpeg resize failed: {e}")
            return clip_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_srt(self, clip: ClipCandidate) -> str:
        """Generate SRT subtitle content for a clip."""
        text = clip.title or clip.reason or ""
        if not text:
            return ""
        start_ts = self._seconds_to_srt_time(0)
        end_ts = self._seconds_to_srt_time(clip.duration)
        return f"1\n{start_ts} --> {end_ts}\n{text}\n"

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        """Format seconds to HH:MM:SS for mcp-video."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @staticmethod
    def _seconds_to_srt_time(seconds: float) -> str:
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _cleanup(path: str):
        """Remove intermediate file if it exists and is not the final output."""
        try:
            if os.path.exists(path) and "_subtitled" not in path and f"_" not in os.path.basename(path).replace("clip_", ""):
                os.remove(path)
        except OSError:
            pass
