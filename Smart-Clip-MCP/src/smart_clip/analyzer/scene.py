"""Scene detection module using PySceneDetect."""

from __future__ import annotations

import logging

from smart_clip.models.subtitle import SubtitleResult

logger = logging.getLogger(__name__)


class SceneResult:
    """Result of scene detection."""

    def __init__(self, scenes: list[dict]):
        self.scenes = scenes  # [{"time": float, "type": str, "confidence": float}]


class SceneDetector:
    """Detect scene change boundaries in video."""

    def __init__(self, threshold: float = 27.0):
        self.threshold = threshold

    async def detect(self, video_path: str) -> SceneResult:
        """
        Detect scene boundaries in video.

        Args:
            video_path: Path to the input video file.

        Returns:
            SceneResult with list of scene boundaries.
        """
        try:
            from scenedetect import detect, ContentDetector

            scene_list = detect(video_path, ContentDetector(threshold=self.threshold))

            scenes = []
            for i, (start, end) in enumerate(scene_list):
                scenes.append({
                    "time": start.get_seconds(),
                    "type": "cut",
                    "confidence": 1.0,
                })

            return SceneResult(scenes=scenes)
        except ImportError:
            logger.warning("scenedetect not installed, skipping scene detection")
            return SceneResult(scenes=[])
        except Exception as e:
            logger.warning(f"Scene detection failed: {e}")
            return SceneResult(scenes=[])
