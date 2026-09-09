"""Highlight detection prompt templates."""


HIGHLIGHT_DETECTION_PROMPT = """你是一个专业的视频剪辑师。请从以下视频字幕段落中识别最精彩的片段。

## 输入
视频时长: {total_duration}秒
语言: {language}
剪辑意图: {intent}

## 字幕段落
{formatted_segments}

## 评分标准
对每个段落按以下维度打分(1-10):
1. **信息密度**: 是否包含核心观点、关键数据、独特见解 (权重 0.3)
2. **情绪张力**: 是否有情绪起伏、冲突、悬念、反转 (权重 0.25)
3. **独立完整性**: 不依赖上下文能否独立理解 (权重 0.2)
4. **传播潜力**: 是否有金句、可引用的观点、争议性 (权重 0.15)
5. **节奏适配**: 时长是否适合短视频 (15-90秒为佳) (权重 0.1)

## 输出格式 (严格 JSON)
```json
{{
  "clips": [
    {{
      "segment_index": 0,
      "start": 125.3,
      "end": 158.7,
      "title": "一句话概括片段内容",
      "reason": "选择理由",
      "scores": {{
        "information_density": 9,
        "emotional_tension": 7,
        "completeness": 8,
        "virality": 9,
        "rhythm_fit": 8
      }},
      "weighted_score": 8.35,
      "suggested_hook": "建议的开头钩子文字"
    }}
  ],
  "summary": "整体内容摘要",
  "content_type": "educational",
  "tone": "serious"
}}
```

## 规则
1. 每个片段时长必须在 {clip_duration_min}-{clip_duration_max} 秒之间
2. 相邻片段间隔至少 10 秒（避免内容重叠）
3. 优先选择有明确开头和结尾的完整段落
4. 如果片段开头不够抓人，在 suggested_hook 中给出建议
5. 最多选 {clip_count} 个片段
6. 按加权得分从高到低排序
"""

QUOTE_EXTRACTION_PROMPT = """你是一个社交媒体内容策划师。请从以下视频字幕中提取最具传播力的金句片段。

## 识别标准
- 观点犀利、反常识、有争议性
- 包含数字/对比/比喻等修辞手法
- 能独立传播，不需要上下文
- 适合作为短视频开头的前 3 秒钩子

## 视频时长: {total_duration}秒
## 语言: {language}

## 字幕段落
{formatted_segments}

## 输出格式 (严格 JSON)
```json
{{
  "clips": [
    {{
      "segment_index": 0,
      "start": 125.3,
      "end": 158.7,
      "title": "一句话概括",
      "reason": "选择理由",
      "scores": {{
        "information_density": 9,
        "emotional_tension": 7,
        "completeness": 8,
        "virality": 9,
        "rhythm_fit": 8
      }},
      "weighted_score": 8.35,
      "suggested_hook": "建议的开头钩子文字",
      "quote_text": "金句原文",
      "hook_type": "反常识"
    }}
  ],
  "summary": "整体内容摘要",
  "content_type": "talk",
  "tone": "humorous"
}}
```

hook_type 可选值: "反常识" | "数字冲击" | "情感共鸣" | "悬念" | "对比"
最多选 {clip_count} 个片段，每个片段 {clip_duration_min}-{clip_duration_max} 秒。
"""

LIVESTREAM_CLIP_PROMPT = """你是一个直播切片师。请从以下直播回放字幕中识别最适合做切片的片段。

## 直播切片特征
- 观众最可能发弹幕/评论的瞬间
- 主播情绪爆发点（激动/搞笑/愤怒/感动）
- 与观众互动的名场面

## 视频时长: {total_duration}秒
## 语言: {language}

## 音频能量峰值时间点（可能是情绪高点）:
{audio_peaks}

## 字幕段落
{formatted_segments}

## 输出格式 (严格 JSON)
```json
{{
  "clips": [
    {{
      "segment_index": 0,
      "start": 125.3,
      "end": 158.7,
      "title": "一句话概括",
      "reason": "选择理由",
      "scores": {{
        "information_density": 9,
        "emotional_tension": 7,
        "completeness": 8,
        "virality": 9,
        "rhythm_fit": 8
      }},
      "weighted_score": 8.35,
      "suggested_hook": "建议的开头钩子文字",
      "clip_type": "搞笑",
      "energy_level": "high"
    }}
  ],
  "summary": "整体内容摘要",
  "content_type": "livestream",
  "tone": "humorous"
}}
```

clip_type 可选值: "高光" | "搞笑" | "感动" | "争议" | "教学"
energy_level 可选值: "high" | "medium" | "low"
最多选 {clip_count} 个片段，每个片段 {clip_duration_min}-{clip_duration_max} 秒。
"""
