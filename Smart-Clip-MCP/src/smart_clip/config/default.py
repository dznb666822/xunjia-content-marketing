"""Default configuration for Smart Clip MCP."""

import os

DEFAULT_CONFIG = {
    "analyzer": {
        "whisper": {
            "mode": os.getenv("SMART_CLIP_WHISPER_MODE", "local"),
            "model": os.getenv("SMART_CLIP_WHISPER_MODEL", "base"),
            "language": os.getenv("SMART_CLIP_LANGUAGE", "zh"),
            # Whisper API uses OpenAI only (no alternative provider)
            "api_key": os.getenv("OPENAI_API_KEY", ""),
        },
        "audio": {
            "sample_rate": 22050,
            "energy_percentile": 90,
            "silence_threshold": 0.3,
        },
        "scene": {
            "threshold": 27.0,
        },
    },
    "planner": {
        "llm": {
            "model": os.getenv("SMART_CLIP_LLM_MODEL", "gpt-4o-mini"),
            "temperature": 0.0,
            "max_tokens": 4096,
            "api_key": os.getenv("SMART_CLIP_LLM_API_KEY", "") or os.getenv("OPENAI_API_KEY", ""),
            "base_url": os.getenv("SMART_CLIP_LLM_BASE_URL", ""),  # e.g. https://api.deepseek.com/v1
        },
        "strategy": {
            "min_score": 6.0,
            "min_gap": 10.0,
            "snap_margin": 0.5,
        },
    },
    "executor": {
        "mcp_video": {
            "enabled": True,
        },
        "output": {
            "format": "mp4",
            "quality": "high",
            "codec": "libx264",
        },
    },
}
