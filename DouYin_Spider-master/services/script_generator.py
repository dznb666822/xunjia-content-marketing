# -*- coding: utf-8 -*-
"""
AI脚本生成器
基于对标视频的文本结构 + 品牌画像，调用AI生成品牌专属参考脚本
"""
import os
import json
import re
from datetime import datetime

import requests
from loguru import logger

from services.storage import find_by_id, update_one, load_all


def _extract_json(text: str) -> dict:
    """
    从AI返回的文本中提取JSON对象，兼容各种格式：
    - 纯JSON
    - markdown代码块包裹
    - 前后有额外文字
    - 双花括号 {{...}}
    """
    if not text:
        raise ValueError("AI响应为空")

    # 去除 markdown 代码块标记
    cleaned = re.sub(r'```(?:json)?\s*', '', text)
    cleaned = cleaned.strip()

    # 尝试直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 尝试提取第一个 { 到最后一个 } 之间的内容
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_str = cleaned[first_brace:last_brace + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 检查是否是双花括号 {{...}}
            if json_str.startswith('{{') and json_str.endswith('}}'):
                json_str = json_str[1:-1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

    raise ValueError("无法从AI响应中提取有效JSON")


def _call_ai(prompt: str, timeout: int = 300) -> str:
    """调用AI API（使用Ark API的responses端点），返回文本内容"""
    api_url = os.getenv('AI_API_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    api_key = os.getenv('AI_API_KEY', '')

    headers = {
        'Authorization': 'Bearer {}'.format(api_key),
        'Content-Type': 'application/json'
    }
    payload = {
        'model': os.getenv('AI_MODEL', 'doubao-seed-2-0-pro-260215'),
        'input': [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
    }
    logger.info('调用AI API, prompt长度={}, timeout={}s'.format(len(prompt), timeout))
    resp = requests.post('{}/responses'.format(api_url), json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # 从Ark API responses端点提取文本内容
    # 推理模型返回多个output项，需遍历找到含content的message类型
    output_list = data.get('output', [])
    for item in output_list:
        # 优先找 type=message 的 content
        content_list = item.get('content', [])
        if content_list:
            for c in content_list:
                text = c.get('text', '')
                if text:
                    logger.debug('AI返回文本长度: {}'.format(len(text)))
                    return text

    # 兜底：尝试从 reasoning 的 summary 中提取
    for item in output_list:
        summary_list = item.get('summary', [])
        if summary_list:
            for s in summary_list:
                text = s.get('text', '')
                if text:
                    logger.warning('仅获取到reasoning文本，非最终回答')
                    return text

    # 最终兜底
    logger.warning('AI响应格式异常，原始数据: {}'.format(str(data)[:500]))
    return str(data)


def generate_script(video_id: str, brand_id: str, num_variants: int = 3) -> dict:
    """
    基于视频分析和品牌信息生成参考脚本。

    Args:
        video_id: 已分析的视频ID
        brand_id: 品牌画像ID
        num_variants: 生成版本数

    Returns:
        dict: {"scripts": [{"hook": "", "body": "", "cta": "", "full_script": ""}], "video_id": "", "brand_id": ""}
    """
    # 1. 加载视频分析结果和品牌信息
    video = find_by_id('videos', video_id)
    brand = find_by_id('brands', brand_id)

    if not video or not brand:
        return {"error": "视频或品牌不存在"}

    text_structure = video.get('text_structure', {})
    video_type = video.get('video_type', '')

    # 2. 构造提示词
    brand_info = """
品牌名称：{name}
品牌品类：{category}
目标人群：{target_audience}
产品描述：{product_desc}
风格调性：{style_tone}
核心卖点：{selling_points}
""".format(
        name=brand.get('name', ''),
        category=brand.get('category', ''),
        target_audience=brand.get('target_audience', ''),
        product_desc=brand.get('product_desc', ''),
        style_tone=brand.get('style_tone', ''),
        selling_points=', '.join(brand.get('selling_points', []))
    )

    ref_structure = """
参考视频的文本结构：
- 钩子（前3秒）：{hook}
- 正文逻辑：{body}
- 转化引导：{cta}
- 视频类型：{video_type}
""".format(
        hook=text_structure.get('hook', ''),
        body=text_structure.get('body', ''),
        cta=text_structure.get('cta', ''),
        video_type=video_type
    )

    prompt = """你是一个专业的内容运营和脚本策划专家。请根据以下信息，为品牌生成 {num_variants} 个不同版本的短视频参考脚本。

{brand_info}

参考对标视频的结构：
{ref_structure}

要求：
1. 保留对标视频的文本结构框架和节奏
2. 内容替换为该品牌的产品/服务信息
3. 保持品牌的风格调性
4. 确保钩子有抓睛力，CTA有转化力
5. 每个版本有不同的切入角度

请以JSON格式输出（只输出JSON，不要markdown代码块）：
{{
    "scripts": [
        {{
            "version": 1,
            "angle": "版本切入角度描述",
            "hook": "钩子脚本文案",
            "body": "正文脚本文案", 
            "cta": "转化引导文案",
            "full_script": "完整脚本（合并hook+body+cta）",
            "estimated_duration": "预估时长（秒）"
        }}
    ]
}}
""".format(num_variants=num_variants, brand_info=brand_info, ref_structure=ref_structure)

    # 3. 调用AI
    try:
        response = _call_ai(prompt)
        logger.debug('AI原始响应前200字符: {}'.format(response[:200]))
        result = _extract_json(response)
    except Exception as e:
        logger.error('脚本生成JSON解析失败: {}'.format(str(e)))
        return {"error": "AI响应解析失败: {}".format(str(e)), "raw_response": response[:500] if 'response' in dir() else ''}

    # 4. 保存脚本
    result['video_id'] = video_id
    result['brand_id'] = brand_id

    # 更新视频的scripts字段
    scripts = result.get('scripts', [])
    update_one('videos', video_id, {'scripts': scripts, 'updated_at': datetime.now().isoformat()})

    return result


def generate_scripts_by_type(video_type: str, brand_id: str, num_variants: int = 3) -> dict:
    """
    按视频类型生成脚本模板（不依赖具体视频，而是基于类型特征）。
    """
    brand = find_by_id('brands', brand_id)
    if not brand:
        return {"error": "品牌不存在"}

    brand_info = """
品牌名称：{name}
品牌品类：{category}
目标人群：{target_audience}
产品描述：{product_desc}
风格调性：{style_tone}
核心卖点：{selling_points}
""".format(
        name=brand.get('name', ''),
        category=brand.get('category', ''),
        target_audience=brand.get('target_audience', ''),
        product_desc=brand.get('product_desc', ''),
        style_tone=brand.get('style_tone', ''),
        selling_points=', '.join(brand.get('selling_points', []))
    )

    prompt = """你是一个专业的内容运营专家。请为以下品牌生成 {num_variants} 个"{video_type}"类型的短视频脚本模板。

{brand_info}

视频类型：{video_type}

请根据该类型的典型结构和该品牌的调性，生成可复用的脚本模板。

请以JSON格式输出（只输出JSON）：
{{
    "scripts": [
        {{
            "version": 1,
            "angle": "切入角度",
            "hook": "钩子模板",
            "body": "正文模板",
            "cta": "CTA模板",
            "full_script": "完整脚本模板",
            "estimated_duration": "预估时长"
        }}
    ]
}}
""".format(num_variants=num_variants, video_type=video_type, brand_info=brand_info)

    try:
        response = _call_ai(prompt)
        result = _extract_json(response)
    except Exception as e:
        logger.error('按类型脚本生成JSON解析失败: {}'.format(str(e)))
        return {"error": "AI响应解析失败: {}".format(str(e)), "raw_response": response[:500] if 'response' in dir() else ''}

    result['video_type'] = video_type
    result['brand_id'] = brand_id
    return result


def generate_from_analysis(video_id: str, user_prompt: str = "", num_variants: int = 1) -> dict:
    """
    基于视频完整分析结果（含分镜脚本）和用户提示词，生成改编后的新剧本。
    保留原有分镜结构和关键帧，根据用户指令修改台词、画面内容等。

    Args:
        video_id: 已分析的视频ID
        user_prompt: 用户的自定义提示词（改编方向、品牌信息、修改要求等）
        num_variants: 生成版本数（默认1）

    Returns:
        dict: {"storyboard": [...], "variants": [...]}
    """
    from services.storage import find_by_id as _find

    video = _find('videos', video_id)
    if not video:
        return {"error": "视频不存在"}

    storyboard = video.get('storyboard', [])
    text_structure = video.get('text_structure', {})
    product_analysis = video.get('product_analysis', {})
    video_type = video.get('video_type', '')
    scene_desc = video.get('scene_desc', '')
    mood = video.get('mood', '')

    if not storyboard:
        return {"error": "该视频暂无分镜脚本数据，请先进行内容分析"}

    # 构建分镜参考信息
    storyboard_ref = ""
    for s in storyboard[:15]:
        storyboard_ref += """镜{sn}: {shot_type} | {camera} | 画面:{visual} | 台词:{dialogue} | 音效:{sound} | {dur}s
""".format(
            sn=s.get('shot_number', '-'),
            shot_type=s.get('shot_type', ''),
            camera=s.get('camera_movement', ''),
            visual=s.get('visual_content', ''),
            dialogue=s.get('dialogue', ''),
            sound=s.get('sound_effect', ''),
            dur=s.get('duration_seconds', '')
        )

    analysis_info = """
【原视频信息】
- 视频类型：{video_type}
- 情绪基调：{mood}
- 拍摄场景：{scene_desc}
- 产品品类：{product_category}
- 目标受众：{target_audience}
- 核心卖点：{selling_points}

【原视频文本结构】
- 钩子：{hook}
- 正文逻辑：{body}
- 转化引导：{cta}

【原视频分镜脚本（请保留景别/运镜/时长/帧图不变，按用户要求修改台词和画面内容）】
{storyboard}
""".format(
        video_type=video_type,
        mood=mood,
        scene_desc=scene_desc or '',
        product_category=product_analysis.get('product_category', ''),
        target_audience=product_analysis.get('target_audience', ''),
        selling_points=', '.join(product_analysis.get('selling_points', [])) if isinstance(product_analysis.get('selling_points'), list) else str(product_analysis.get('selling_points', '')),
        hook=text_structure.get('hook', ''),
        body=text_structure.get('body', ''),
        cta=text_structure.get('cta', ''),
        storyboard=storyboard_ref
    )

    prompt = """你是一名专业的短视频编导。请根据以下原视频的完整分析结果，结合用户的改编要求，生成 {num} 个新版本的编导脚本。

{analysis}

【用户改编要求】
{user_prompt}

【输出要求】
1. 保留原视频的景别/视角/构图（shot_type）、运镜方式（camera_movement）、参考时长（duration_seconds）、关键帧时间点（key_frame_time）——这些不需要修改
2. 画面内容（visual_content）、人物与场景（character_scene）、台词（dialogue）、音效（sound_effect）按照用户要求进行改编
3. 保留分镜数量不变
4. 文本结构（hook/body/cta）也按用户要求改写

请以JSON格式输出（只输出JSON，不含markdown标记）：
{{
    "text_structure": {{
        "hook": "改写后的钩子内容",
        "body": "改写后的正文逻辑",
        "cta": "改写后的转化引导"
    }},
    "variants": [
        {{
            "version": 1,
            "angle": "本次改编的切入角度说明",
            "full_script": "完整脚本文案",
            "storyboard": [
                {{
                    "shot_number": 1,
                    "shot_type": "保持不变，照抄原视频",
                    "camera_movement": "保持不变，照抄原视频",
                    "visual_content": "改编后的画面内容",
                    "character_scene": "改编后的人物与场景",
                    "dialogue": "改编后的台词",
                    "sound_effect": "改编后的音效",
                    "duration_seconds": 3.5,
                    "key_frame_time": 2.0
                }}
            ]
        }}
    ]
}}
""".format(num=num_variants, analysis=analysis_info, user_prompt=user_prompt if user_prompt.strip() else '请保持原视频风格，仅对台词进行润色优化')

    try:
        logger.info('开始基于分析结果生成脚本: video_id={}, prompt长度={}'.format(video_id, len(prompt)))
        response = _call_ai(prompt, timeout=300)
        logger.info('AI返回, 文本长度={}'.format(len(response)))
        logger.debug('AI原始响应前200字符: {}'.format(response[:200]))
        result = _extract_json(response)
    except requests.exceptions.Timeout as e:
        logger.error('AI调用超时: {}'.format(str(e)))
        return {"error": "AI调用超时（300秒），请缩小原视频分镜数量或稍后重试"}
    except Exception as e:
        logger.error('基于分析脚本生成失败: {}'.format(str(e)))
        # response可能未定义，安全处理
        try:
            raw = response[:500]
        except NameError:
            raw = ''
        return {"error": "AI响应解析失败: {}".format(str(e)), "raw_response": raw}

    result['video_id'] = video_id
    result['reference_storyboard'] = storyboard  # 附带原分镜供前端对比

    # 保存到视频记录
    scripts = result.get('variants', [])
    update_one('videos', video_id, {
        'generated_scripts': scripts,
        'script_user_prompt': user_prompt,
        'updated_at': datetime.now().isoformat()
    })

    return result
