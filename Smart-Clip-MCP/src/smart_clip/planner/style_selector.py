"""Style 预设与选择器(SOP §3.2)。

7 个系统 Style(对齐文档 §3.2.1 的 YAML),提供:
- STYLE_LIBRARY:系统 Style 字典
- select_style(content_type, tone):按内容+语气选最匹配的 Style
- list_styles():列出全部系统 Style(给前端/CLI)
"""

from __future__ import annotations

from typing import Literal

from smart_clip.models.plan import Style

# ---------------------------------------------------------------------------
# 7 个系统 Style 配置(对齐 SOP §3.2.1)
# ---------------------------------------------------------------------------

_STYLE_LIBRARY_RAW: dict[str, dict] = {
    "luxury_bilingual_white": {
        "display_name": "轻奢双语白",
        "description": "默认基础模板:对标开拍网感剪辑,适合大多数口播/讲书/讲财经",
        "config": {
            "subtitle": {"style_preset": "luxury_bilingual_white", "bilingual": True},
            "sfx": {"emphasis": True, "transition": True},
            "bgm": {"tone": "serious", "beat_sync": True},
            "effect": {"zoom": True, "progress_bar": True},
            "visual_assets": {
                "broll": "minimal_white",
                "chart": "line_bar_clean",
                "infographic": "luxury_cards",
            },
        },
    },
    "knowledge": {
        "display_name": "知识口播",
        "description": "知识科普/讲解:深色科技感,关键词放大高亮,数据图表走 explainer_cards",
        "config": {
            "subtitle": {"style_preset": "luxury_bilingual_white", "highlight_mode": "bold_scale"},
            "sfx": {"emphasis": True, "transition": True},
            "bgm": {"tone": "serious", "beat_sync": True},
            "effect": {"zoom": True, "progress_bar": True},
            "visual_assets": {
                "broll": "dark_moody",
                "chart": "knowledge_charts",
                "infographic": "explainer_cards",
            },
        },
    },
    "entertainment": {
        "display_name": "娱乐搞笑",
        "description": "搞笑/段子/游戏解说:SmileySans 倾斜字体,打字机字幕,笑声/悬念音效密集",
        "config": {
            "subtitle": {"font": "SmileySans-Oblique", "highlight": True, "animation": "typewriter"},
            "sfx": {"laugh": True, "suspense": True},
            "bgm": {"tone": "humorous"},
            "effect": {"zoom": True, "speed": True, "sticker": True},
            "visual_assets": {
                "broll": "high_energy",
                "chart": "playful_3d",
                "infographic": "meme_cards",
            },
        },
    },
    "news": {
        "display_name": "资讯新闻",
        "description": "新闻/资讯:NotoSansSC-Bold,左下角字幕,克制过渡+闪光转场",
        "config": {
            "subtitle": {"font": "NotoSansSC-Bold", "position": "bottom-left"},
            "sfx": {"emphasis": True},
            "bgm": {"tone": "serious"},
            "effect": {"transitions": "flash"},
            "visual_assets": {
                "broll": "editorial_news",
                "chart": "news_flash",
                "infographic": "factbox",
            },
        },
    },
    "vlog": {
        "display_name": "生活记录",
        "description": "vlog/日常:NotoSansSC-Medium 淡入字幕,环境音铺底",
        "config": {
            "subtitle": {"font": "NotoSansSC-Medium", "animation": "fade_in"},
            "sfx": {"ambient": True, "transition": True},
            "bgm": {"tone": "conversational"},
            "effect": {"zoom": True, "progress_bar": True},
            "visual_assets": {
                "broll": "natural_daily",
                "chart": "soft_minimal",
                "infographic": "vlog_cards",
            },
        },
    },
    "cute": {
        "display_name": "可爱萌系",
        "description": "宠物/萌娃/童趣:SmileySans 倾斜字体,bounce 弹入,贴纸+可爱音效",
        "config": {
            "subtitle": {"font": "SmileySans-Oblique", "animation": "bounce"},
            "sfx": {"cute": True, "pop": True},
            "bgm": {"tone": "humorous"},
            "effect": {"sticker": True, "zoom": True},
            "visual_assets": {
                "broll": "soft_pastel",
                "chart": "rounded_pastel",
                "infographic": "sticker_cards",
            },
        },
    },
    "custom": {
        "display_name": "自定义",
        "description": "占位:实际配置由调用方传入,本选择器不会自动选 custom",
        "config": {
            "subtitle": {},
            "sfx": {},
            "bgm": {},
            "effect": {},
            "visual_assets": {},
        },
    },
}


def list_styles() -> list[Style]:
    """列出全部 7 个系统 Style(给前端/CLI 选择器用)。"""
    return [
        Style(
            name=name,
            display_name=raw["display_name"],
            description=raw["description"],
            config=raw["config"],
            is_system=True,
        )
        for name, raw in _STYLE_LIBRARY_RAW.items()
        if name != "custom"
    ]


# ---------------------------------------------------------------------------
# 内容+语气 → Style 关键词映射(规则化,V2 不上 LLM)
# ---------------------------------------------------------------------------

_CONTENT_TO_STYLE: dict[str, str] = {
    # knowledge
    "知识": "knowledge", "科普": "knowledge", "讲解": "knowledge", "讲书": "knowledge",
    "教学": "knowledge", "课程": "knowledge", "财经": "knowledge", "深度": "knowledge",
    "分析": "knowledge", "解读": "knowledge", "行业": "knowledge",
    # entertainment
    "搞笑": "entertainment", "娱乐": "entertainment", "段子": "entertainment",
    "幽默": "entertainment", "游戏": "entertainment", "解说": "entertainment",
    "吐槽": "entertainment",
    # news
    "新闻": "news", "资讯": "news", "报道": "news", "时事": "news", "快讯": "news",
    # vlog
    "vlog": "vlog", "日常": "vlog", "生活": "vlog", "记录": "vlog", "旅行": "vlog",
    "美食": "vlog", "开箱": "vlog",
    # cute
    "萌": "cute", "可爱": "cute", "宠物": "cute", "童趣": "cute", "宝宝": "cute",
    "萌娃": "cute", "猫": "cute", "狗": "cute",
}

_TONE_BOOST: dict[str, str] = {
    # tone 强烈时压过 content_type 的弱匹配
    "humorous": "entertainment",
    "inspirational": "knowledge",
    "serious": "news",
    "conversational": "vlog",
}


def select_style(
    content_type: str = "",
    tone: str = "",
    custom_config: dict | None = None,
) -> Style:
    """根据 content_type + tone 选最匹配的 Style。

    匹配规则:
    1. 若 custom_config 显式传入 → 走 custom
    2. tone 强信号(humorous / serious / inspirational / conversational)优先
    3. content_type 关键词命中 → 对应 Style
    4. 兜底 → luxury_bilingual_white(默认)
    """
    if custom_config is not None:
        raw = _STYLE_LIBRARY_RAW["custom"]
        return Style(
            name="custom",
            display_name=raw["display_name"],
            description=raw["description"],
            config={"subtitle": {}, "sfx": {}, "bgm": {}, "effect": {}, "visual_assets": {}, **custom_config},
            is_system=False,
        )

    # 1) tone 优先
    tone_norm = (tone or "").strip().lower()
    if tone_norm in _TONE_BOOST:
        style_name = _TONE_BOOST[tone_norm]
    else:
        # 2) content_type 关键词匹配
        style_name = "luxury_bilingual_white"  # 兜底
        for kw, name in _CONTENT_TO_STYLE.items():
            if kw in content_type:
                style_name = name
                break

    raw = _STYLE_LIBRARY_RAW[style_name]
    return Style(
        name=style_name,
        display_name=raw["display_name"],
        description=raw["description"],
        config=raw["config"],
        is_system=True,
    )


# ---------------------------------------------------------------------------
# 便捷导出
# ---------------------------------------------------------------------------

DEFAULT_STYLE_NAME = "luxury_bilingual_white"


def get_style_by_name(name: str) -> Style:
    """按名称取 Style(未命中兜底到 default)。"""
    raw = _STYLE_LIBRARY_RAW.get(name) or _STYLE_LIBRARY_RAW[DEFAULT_STYLE_NAME]
    return Style(
        name=name if name in _STYLE_LIBRARY_RAW else DEFAULT_STYLE_NAME,
        display_name=raw["display_name"],
        description=raw["description"],
        config=raw["config"],
        is_system=(name != "custom"),
    )
