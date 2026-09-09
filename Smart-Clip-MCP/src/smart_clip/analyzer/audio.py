"""Audio energy analysis module using librosa."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile

import numpy as np

from smart_clip.models.audio import AudioProfile, Peak, SilenceInterval

logger = logging.getLogger(__name__)


class AudioEnergyAnalyzer:
    """Analyze audio energy curve, detect peaks and silences."""

    def __init__(
        self,
        energy_percentile: int = 90,
        silence_threshold: float = 0.3,
        sample_rate: int = 22050,
    ):
        self.energy_percentile = energy_percentile
        self.silence_threshold = silence_threshold
        self.sample_rate = sample_rate

    async def analyze(self, video_path: str) -> AudioProfile:
        """
        Analyze audio energy profile from video.

        Args:
            video_path: Path to the input video file.

        Returns:
            AudioProfile with energy curve, peaks, silences, and tempo.
        """
        import librosa

        # Extract audio
        audio_path = await self._extract_audio(video_path)

        try:
            y, sr = librosa.load(audio_path, sr=self.sample_rate)

            # RMS energy per second
            hop_length = self.sample_rate  # 1 second per frame
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            energy_curve = rms.tolist()

            # Detect peaks
            threshold = np.percentile(rms, self.energy_percentile)
            peaks = self._detect_peaks(rms, threshold)

            # Detect silences
            silences = self._detect_silences(rms)

            # Estimate tempo
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            tempo_value = float(tempo) if not isinstance(tempo, np.ndarray) else float(tempo[0])

            return AudioProfile(
                energy_curve=energy_curve,
                peaks=peaks,
                silences=silences,
                tempo=tempo_value,
            )
        finally:
            if audio_path != video_path and os.path.exists(audio_path):
                os.remove(audio_path)

    def _detect_peaks(self, rms: np.ndarray, threshold: float) -> list[Peak]:
        """Detect energy peaks above threshold with minimum gap."""
        peaks = []
        last_peak_time = -5.0  # enforce 2-second gap between peaks

        for i, val in enumerate(rms):
            time = float(i)
            if val > threshold and time - last_peak_time >= 2.0:
                baseline = np.median(rms)
                intensity = float(val / baseline) if baseline > 0 else 1.0
                peaks.append(Peak(time=time, intensity=intensity))
                last_peak_time = time

        return peaks

    def _detect_silences(self, rms: np.ndarray) -> list[SilenceInterval]:
        """Detect silence intervals (energy below 10th percentile for > 0.3s)."""
        silence_level = np.percentile(rms, 10)
        silences = []
        in_silence = False
        silence_start = 0.0

        for i, val in enumerate(rms):
            time = float(i)
            if val <= silence_level:
                if not in_silence:
                    in_silence = True
                    silence_start = time
            else:
                if in_silence:
                    duration = time - silence_start
                    if duration >= self.silence_threshold:
                        silences.append(
                            SilenceInterval(start=silence_start, end=time)
                        )
                    in_silence = False

        # Handle trailing silence
        if in_silence:
            duration = float(len(rms)) - silence_start
            if duration >= self.silence_threshold:
                silences.append(
                    SilenceInterval(start=silence_start, end=float(len(rms)))
                )

        return silences

    async def _extract_audio(self, video_path: str) -> str:
        """Extract audio from video as WAV."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()

        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(self.sample_rate), "-ac", "1",
            "-y", tmp.name,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return tmp.name
