"""Video input resolver — detects URL vs file, fetches subtitles with fallback chain.

Priority order for subtitles:
  1. Platform auto-captions (yt-dlp download for URLs)
  2. User-provided SRT/VTT file (auto-detect alongside video)
  3. Whisper transcription (local faster-whisper or API)
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_clip.models.subtitle import SubtitleResult

logger = logging.getLogger(__name__)


class VideoResolver:
    """Resolve video input (URL or file) into video path + subtitles."""

    def __init__(self, whisper_mode: str = "local", language: str = "zh", whisper_model: str = "base",
                 api_key: str | None = None, max_video_size_mb: int = 500):
        self.whisper_mode = whisper_mode
        self.language = language
        self.whisper_model = whisper_model
        self.api_key = api_key
        self.max_video_size_mb = max_video_size_mb
        self._work_dir: str | None = None

    async def resolve(self, user_input: str, srt_path: str | None = None) -> tuple[str, "SubtitleResult", dict]:
        """
        Resolve video input into a local video path and subtitles.

        Args:
            user_input: URL or local file path.
            srt_path: Optional explicit SRT file path (only for file inputs).

        Returns:
            (video_path, subtitle_result, source_info) tuple.
            source_info: {"type": "url"|"file", "platform": str|None, "url": str|None}
        """
        if self._is_url(user_input):
            return await self._resolve_url(user_input)
        else:
            return await self._resolve_file(user_input, srt_path)

    def cleanup(self):
        """Remove temporary files created for URL downloads."""
        import shutil
        if self._work_dir and os.path.exists(self._work_dir):
            shutil.rmtree(self._work_dir, ignore_errors=True)
            logger.info(f"Cleaned up work dir: {self._work_dir}")
            self._work_dir = None

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_url(s: str) -> bool:
        return bool(re.match(r"^https?://", s))

    # ------------------------------------------------------------------
    # URL resolution
    # ------------------------------------------------------------------

    async def _resolve_url(self, url: str) -> tuple[str, "SubtitleResult", dict]:
        """Download video + subtitles via yt-dlp."""
        logger.info(f"Resolving URL: {url}")

        # Detect platform
        platform = self._detect_platform(url)

        # Check yt-dlp availability
        try:
            subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("yt-dlp not installed, installing...")
            subprocess.run(
                ["pip", "install", "yt-dlp", "--quiet"],
                capture_output=True,
                check=False,
            )

        # Create temp work directory
        self._work_dir = tempfile.mkdtemp(prefix="smart_clip_")
        logger.info(f"Work dir: {self._work_dir}")

        # Step 1: Download subtitles only (fast, no video)
        subtitle = await self._download_subtitles(url, platform)

        # Step 2: If no platform subtitles, we'll need Whisper later
        need_whisper = subtitle is None

        # Step 3: Download video
        video_path = await self._download_video(url)

        # Step 4: Fallback to Whisper if no subtitles
        if need_whisper:
            subtitle = await self._transcribe(video_path)

        source_info = {
            "type": "url",
            "platform": platform,
            "url": url,
        }
        return video_path, subtitle, source_info

    @staticmethod
    def _detect_platform(url: str) -> str | None:
        if "bilibili.com" in url or "b23.tv" in url:
            return "bilibili"
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        if "douyin.com" in url or "tiktok.com" in url:
            return "douyin"
        return None

    async def _download_subtitles(self, url: str, platform: str | None) -> "SubtitleResult | None":
        """Try to download platform subtitles as SRT, return parsed result or None."""
        sub_dir = os.path.join(self._work_dir, "subs")
        os.makedirs(sub_dir, exist_ok=True)

        # yt-dlp args for subtitle extraction
        cmd = [
            "yt-dlp",
            "--skip-download",           # don't download video yet
            "--write-subs",              # write manual subtitles
            "--write-auto-subs",         # write auto-generated subtitles
            "--sub-format", "srt/vtt/ass",
            "--convert-subs", "srt",
            "--sub-langs", f"{self.language},zh-Hans,zh-Hant,en,ja,ko,all",
            "-o", f"{sub_dir}/%(title)s.%(ext)s",
            "--no-playlist",
            url,
        ]

        try:
            logger.info("Downloading subtitles from platform...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            logger.debug(f"yt-dlp sub output: {result.stdout[-500:] if result.stdout else ''}")

            # Find output SRT files
            srt_files = list(Path(sub_dir).rglob("*.srt"))
            vtt_files = list(Path(sub_dir).rglob("*.vtt"))

            # Prioritize zh subtitles
            all_sub_files = srt_files + vtt_files
            zh_files = [f for f in all_sub_files if any(
                tag in str(f).lower() for tag in ["zh", "chinese", "chinese (simplified)", "zh-hans", "zh-cn", "chs"]
            )]

            target = zh_files[0] if zh_files else (all_sub_files[0] if all_sub_files else None)
            if target:
                logger.info(f"Platform subtitles downloaded: {target}")
                return await self._parse_subtitle_file(str(target))
        except subprocess.TimeoutExpired:
            logger.warning("Subtitle download timed out")
        except Exception as e:
            logger.warning(f"Subtitle download failed: {e}")

        return None

    async def _download_video(self, url: str) -> str:
        """Download video to work dir, return local path."""
        video_dir = os.path.join(self._work_dir, "video")
        os.makedirs(video_dir, exist_ok=True)

        max_mb = self.max_video_size_mb
        cmd = [
            "yt-dlp",
            "-f", f"best[filesize<{max_mb}M]/best",  # cap file size
            "-o", f"{video_dir}/%(title)s.%(ext)s",
            "--no-playlist",
            url,
        ]

        logger.info(f"Downloading video (max {max_mb}MB)...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        logger.debug(f"yt-dlp video output: {result.stdout[-500:] if result.stdout else ''}")

        # Find the downloaded video
        video_files = list(Path(video_dir).glob("*"))
        video_files = [f for f in video_files if f.suffix.lower() in (".mp4", ".mkv", ".webm", ".flv", ".mov")]
        if video_files:
            path = str(video_files[0])
            logger.info(f"Video downloaded: {path} ({os.path.getsize(path) / 1024 / 1024:.1f}MB)")
            return path

        raise FileNotFoundError(f"No video found after download in {video_dir}")

    # ------------------------------------------------------------------
    # File resolution
    # ------------------------------------------------------------------

    async def _resolve_file(self, path: str, srt_path: str | None) -> tuple[str, "SubtitleResult", dict]:
        """Resolve local file: auto-detect SRT, fall back to Whisper."""
        logger.info(f"Resolving file: {path}")

        # Normalize path
        video_path = os.path.abspath(path)
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Try SRT first
        subtitle = None
        if srt_path:
            subtitle = await self._parse_subtitle_file(srt_path)
        else:
            # Auto-detect
            srt_file = self._find_subtitle_file(video_path)
            if srt_file:
                subtitle = await self._parse_subtitle_file(srt_file)

        # Fallback to Whisper
        if subtitle is None:
            subtitle = await self._transcribe(video_path)

        source_info = {"type": "file", "platform": None, "url": None}
        return video_path, subtitle, source_info

    # ------------------------------------------------------------------
    # Shared subtitle helpers
    # ------------------------------------------------------------------

    async def _parse_subtitle_file(self, srt_path: str) -> "SubtitleResult":
        """Parse an SRT or VTT file into SubtitleResult."""
        from smart_clip.analyzer.subtitle import SubtitleExtractor
        extractor = SubtitleExtractor(mode=self.whisper_mode, language=self.language)
        return await extractor._from_srt(srt_path, self.language)

    async def _transcribe(self, video_path: str) -> "SubtitleResult":
        """Transcribe using Whisper (local or API)."""
        from smart_clip.analyzer.subtitle import SubtitleExtractor
        extractor = SubtitleExtractor(
            mode=self.whisper_mode,
            language=self.language,
            model=self.whisper_model,
            api_key=self.api_key,
        )
        return await extractor.extract(video_path, language=self.language)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _find_subtitle_file(video_path: str) -> str | None:
        base = os.path.splitext(video_path)[0]
        for ext in (".srt", ".vtt"):
            candidate = base + ext
            if os.path.exists(candidate):
                logger.info(f"Found external subtitle: {candidate}")
                return candidate
        return None
