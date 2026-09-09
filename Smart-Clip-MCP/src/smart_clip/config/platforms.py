"""Platform-specific configuration presets."""

PLATFORM_CONFIG = {
    "tiktok": {
        "width": 1080,
        "height": 1920,
        "aspect_ratio": "9:16",
        "max_duration": 180,
        "subtitle_style": {
            "font_size": 24,
            "position": "bottom",
            "color": "#ffffff",
        },
    },
    "youtube_shorts": {
        "width": 1080,
        "height": 1920,
        "aspect_ratio": "9:16",
        "max_duration": 180,
        "subtitle_style": {
            "font_size": 24,
            "position": "bottom",
            "color": "#ffffff",
        },
    },
    "instagram_reels": {
        "width": 1080,
        "height": 1920,
        "aspect_ratio": "9:16",
        "max_duration": 90,
        "subtitle_style": {
            "font_size": 24,
            "position": "center",
            "color": "#ffffff",
        },
    },
    "youtube": {
        "width": 1920,
        "height": 1080,
        "aspect_ratio": "16:9",
        "max_duration": None,
        "subtitle_style": {
            "font_size": 20,
            "position": "bottom",
            "color": "#ffffff",
        },
    },
    "original": {
        "width": None,
        "height": None,
        "aspect_ratio": None,
        "max_duration": None,
        "subtitle_style": {
            "font_size": 20,
            "position": "bottom",
            "color": "#ffffff",
        },
    },
}
