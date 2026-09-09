import os
import json
import requests
from services.storage import find_by_id, load_all


def _call_ai(prompt: str) -> str:
    """调用AI API"""
    api_url = os.getenv('AI_API_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    api_key = os.getenv('AI_API_KEY', '')

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': os.getenv('AI_MODEL', 'doubao-seed-2-0-pro-260215'),
        'input': [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
    }
    resp = requests.post(f'{api_url}/responses', json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    # 提取文本
    output_list = data.get('output', [])
    if output_list:
        content_list = output_list[0].get('content', [])
        if content_list:
            return content_list[0].get('text', json.dumps(data))
    return json.dumps(data)


def analyze_ad_potential(video_id: str, budget_range: str = "1000-5000") -> dict:
    """
    分析视频投流潜力。

    Args:
        video_id: 视频ID
        budget_range: 预算范围

    Returns:
        dict: {"recommendation": {...}, "video_id": ""}
    """
    # 1. 加载视频数据
    video = find_by_id('videos', video_id)
    if not video:
        return {"error": "视频不存在"}

    stats = video.get('stats', {})
    text_structure = video.get('text_structure', {})
    video_type = video.get('video_type', '')
    mood = video.get('mood', '')

    # 2. 加载品牌信息（通过competitor关联）
    competitor_id = video.get('competitor_id', '')
    brand_id = ''
    brand_info = ''
    if competitor_id:
        competitor = find_by_id('competitors', competitor_id)
        if competitor:
            brand_id = competitor.get('source_brand_id', '')
            if brand_id:
                brand = find_by_id('brands', brand_id)
                if brand:
                    brand_info = f"""
品牌名称：{brand.get('name', '')}
品牌品类：{brand.get('category', '')}
目标人群：{brand.get('target_audience', '')}
"""

    # 3. 构造分析提示词
    prompt = f"""你是一个专业的抖音投流分析师。请根据以下视频数据，分析是否值得投流以及给出具体建议。

视频数据：
- 点赞数：{stats.get('digg_count', stats.get('like_count', 0))}
- 评论数：{stats.get('comment_count', 0)}
- 分享数：{stats.get('share_count', 0)}
- 播放数：{stats.get('play_count', 0)}
- 收藏数：{stats.get('collect_count', 0)}
- 视频类型：{video_type}
- 情绪基调：{mood}
- 钩子内容：{text_structure.get('hook', '')}
- 正文内容：{text_structure.get('body', '')}
- CTA内容：{text_structure.get('cta', '')}

{brand_info}

可接受预算范围：{budget_range}元

请分析以下维度并给出建议（输出JSON格式，只输出JSON不要markdown代码块）：
{{
    "should_advertise": true/false,
    "confidence": "高/中/低",
    "reason": "推荐或不推荐投流的核心理由",
    "recommended_budget": "建议投流预算（如500-1000元/天）",
    "target_audience": {{
        "age_range": "建议年龄范围",
        "gender": "建议性别",
        "interests": ["建议兴趣标签"],
        "regions": ["建议地域"]
    }},
    "expected_roi": "预期ROI范围",
    "optimization_tips": ["优化建议列表"],
    "risk_warning": "风险提示"
}}
"""

    # 4. 调用AI
    try:
        response = _call_ai(prompt)
        import re
        # 尝试解析JSON
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                result = json.loads(match.group())
            else:
                return {"error": "AI响应解析失败", "raw_response": response}
    except Exception as e:
        return {"error": str(e)}

    result['video_id'] = video_id
    result['brand_id'] = brand_id if brand_id else ''

    return result


def compare_videos(video_ids: list[str]) -> dict:
    """
    对比多个视频的投流潜力，给出优先级排序。
    """
    results = []
    for vid in video_ids:
        analysis = analyze_ad_potential(vid)
        results.append(analysis)

    # 按should_advertise和confidence排序
    priority_order = {"高": 3, "中": 2, "低": 1}
    results.sort(key=lambda x: (
        1 if x.get('should_advertise') else 0,
        priority_order.get(x.get('confidence', ''), 0)
    ), reverse=True)

    return {
        "videos": results,
        "total": len(results),
        "top_recommendation": results[0] if results else None
    }
