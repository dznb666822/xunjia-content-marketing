"""Data models for edit plans and clip candidates.

V2.0: 扩展为 VideoPlan 三层结构(片段层 + 包装层 + 画面素材层) + Style 引用,
对齐 SOP 文档 §3.1 核心概念。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ClipScores(BaseModel):
    """Scoring breakdown for a clip candidate."""

    information_density: float = 0.0
    emotional_tension: float = 0.0
    completeness: float = 0.0
    virality: float = 0.0
    rhythm_fit: float = 0.0


class ClipCandidate(BaseModel):
    """A candidate highlight clip identified by the LLM."""

    segment_index: int = 0
    start: float  # seconds
    end: float  # seconds
    title: str = ""
    reason: str = ""
    scores: ClipScores = ClipScores()
    weighted_score: float = 0.0
    suggested_hook: str = ""
    quote_text: str | None = None
    hook_type: str | None = None
    clip_type: str | None = None
    energy_level: str | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start


class EditPlan(BaseModel):
    """A structured editing plan ready for execution.

    V1 形态:仅含片段层。V2 由 VideoPlan 继承并叠加包装层/画面素材层/Style。
    """

    clips: list[ClipCandidate] = []
    total_selected_duration: float = 0.0
    platform: str = "original"
    with_subtitles: bool = True
    with_bgm: bool = False
    content_type: str = ""
    tone: str = ""
    summary: str = ""


class ExecuteConfig(BaseModel):
    """Configuration for clip execution."""

    video_path: str
    output_dir: str = "./smart-clip-output"
    format: str = "mp4"
    quality: str = "high"
    codec: str = "libx264"


# =========================================================================
# V2.0 — 包装层 / 画面素材层 / Style(对齐 SOP §3.1 / §3.2)
# =========================================================================


class SubtitleStyle(BaseModel):
    """一段字幕的样式与动效(SOP §4.1)。

    - style_preset:Style 预设内的字幕样式标识(如 luxury_bilingual_white)
    - font / font_size / color / stroke_color:字体与配色
    - animation:动效枚举(bounce / fade / typewriter / pop / scale)
    - highlight:是否启用关键词高亮
    - bilingual:是否双语(中英上下双行)
    - position:位置(top / middle / bottom / bottom-left ...)
    """

    style_preset: str = "luxury_bilingual_white"
    font: str = "NotoSansSC-Bold"
    font_size: int = 48
    color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 2
    animation: Literal["bounce", "fade", "typewriter", "pop", "scale", "none"] = "pop"
    highlight: bool = True
    highlight_mode: Literal["bold", "scale", "color", "underline"] = "bold"
    bilingual: bool = True
    position: Literal["top", "middle", "bottom", "bottom-left", "bottom-right"] = "bottom"


class KeywordHighlight(BaseModel):
    """字幕中需要高亮的关键词 + 出现的时间窗口。"""

    text: str
    start: float  # 字幕内的相对时间(秒)
    end: float
    mode: Literal["bold", "scale", "color", "underline"] = "bold"


class StyledSubtitle(BaseModel):
    """带样式 + 关键词高亮的一段字幕。"""

    segment_index: int
    start: float
    end: float
    text: str
    style: SubtitleStyle = SubtitleStyle()
    keywords: list[KeywordHighlight] = Field(default_factory=list)


class SfxEvent(BaseModel):
    """音效触发点(SOP §4.2)。"""

    trigger_at: float  # 触发时间(秒,相对原视频)
    category: Literal[
        "ambient",      # 环境音
        "emphasis",     # 强调音
        "transition",   # 转场音
        "emotional",    # 情绪音(笑声/惊讶/悬念/掌声)
        "foley",        # 拟音
        "beat_sync",    # 卡点音
    ] = "emphasis"
    intensity: float = 0.7  # 0.0 - 1.0
    reason: str = ""  # LLM 触发理由(用于人工 review)


class BgmPlan(BaseModel):
    """BGM 选曲与卡点(SOP §4.3)。"""

    track_id: Optional[str] = None  # 留空待 Resolver 阶段匹配具体曲库
    track_name: str = ""  # LLM 建议的曲名/描述(如 "轻快俏皮 110BPM")
    tone: Literal["inspirational", "humorous", "serious", "conversational"] = "conversational"
    bpm: int = 90
    beat_points: list[float] = Field(default_factory=list)  # 卡点时间戳(秒,相对原视频)
    duck_db: float = -12.0  # 人声避让衰减量


class EffectEvent(BaseModel):
    """画面特效事件(SOP §4.4)。"""

    trigger_at: float
    effect_type: Literal[
        "zoom_in", "zoom_out",   # 缩放运镜
        "speed_up", "speed_down",  # 变速
        "flash_transition",        # 闪白转场
        "slide_transition",        # 滑动转场
        "dissolve",                # 叠化
        "sticker",                 # 贴纸/花字
        "progress_bar",            # 进度条
        "shake",                   # 震动
    ]
    duration: float = 0.5  # 特效持续时长
    params: dict = Field(default_factory=dict)  # 特效参数(如 sticker 的文字/颜色)
    reason: str = ""


class VisualAssetRef(BaseModel):
    """画面素材引用(SOP §3.1 画面素材层)。"""

    trigger_at: float
    asset_type: Literal[
        "broll",            # 空镜 / B-roll
        "chart",            # 数据图表(折线/柱状/饼图)
        "map",              # 地图
        "infographic",      # 信息图
        "portrait",         # 人物
        "scene",            # 场景实拍
    ]
    topic: str = ""  # 主题标签(能源/科技/城市/...)
    content: str = ""  # 内容描述,如"沙特 2030 愿景"
    style_tag: str = "natural"  # 明亮/深色/科技感/自然/...
    source: Literal["retrieve", "programmatic", "aigc"] = "programmatic"
    template_id: Optional[str] = None  # 程序生成时引用 Remotion 模板 ID


class PackagingLayer(BaseModel):
    """V2 包装层:VideoPlan 三大子层之一(SOP §3.1 第二层)。

    LLM 一次性产出,直接对接 SubtitleRenderer / SFXEngine / MusicEngine / EffectEngine 渲染。
    """

    subtitles: list[StyledSubtitle] = Field(default_factory=list)
    sfx_events: list[SfxEvent] = Field(default_factory=list)
    bgm: BgmPlan = BgmPlan()
    effects: list[EffectEvent] = Field(default_factory=list)


class Style(BaseModel):
    """视觉风格预设(SOP §3.2)。"""

    name: str  # luxury_bilingual_white / knowledge / entertainment / news / vlog / cute / custom
    display_name: str = ""
    description: str = ""
    config: dict = Field(default_factory=dict)  # 完整 YAML 配置(Style 引擎将展开)
    is_system: bool = True  # 系统预设 vs 用户自定义


class VideoPlan(BaseModel):
    """V2.0 完整剪辑方案(SOP §3.1)。

    AI 与渲染系统的标准接口,以字幕 segment 为最小单位,明确指定:
    - 保留哪些片段、什么时候切(片段层 — 继承 EditPlan)
    - 字幕样式/动效/关键词高亮(包装层)
    - 音效触发点(包装层)
    - BGM 选曲与卡点(包装层)
    - 画面特效事件(包装层)
    - 套用的 Style 名称
    - 画面素材引用(画面素材层)
    """

    # 片段层(继承)
    clips: list[ClipCandidate] = Field(default_factory=list)
    total_selected_duration: float = 0.0
    platform: str = "original"
    content_type: str = ""
    tone: str = ""
    summary: str = ""

    # V2 新增
    style: Style  # 选定的 Style(由 StyleSelector 决策)
    packaging: PackagingLayer  # 包装层(由 PackagingPlanner 决策)
    visual_assets: list[VisualAssetRef] = Field(default_factory=list)  # 画面素材层

    # 元数据
    source_video: str = ""
    generated_by: str = ""  # 模型名
    schema_version: str = "2.0"
    created_at: str = ""
