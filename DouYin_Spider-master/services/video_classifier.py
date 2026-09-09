# -*- coding: utf-8 -*-
"""
视频自动分类服务
使用豆包 Seed 2.0 多模态模型分析上传视频，自动打标签分类 + 内容时间线拆分
调用方式: 上传文件 → 等预处理 → responses.create (与 video_analyzer.py 一致)
"""
import asyncio
import os
import json
from loguru import logger

from volcenginesdkarkruntime import AsyncArk


def _get_client():
    return AsyncArk(
        base_url='https://ark.cn-beijing.volces.com/api/v3',
        api_key=os.getenv('ARK_API_KEY', '')
    )


CLASSIFY_PROMPT = (
    '你是一名专业的视频内容分类师。请分析以下视频的内容，为其打上分类标签，以JSON格式输出。\n'
    '\n'
    '请从以下维度分析并输出JSON（只输出JSON，不要包含markdown代码块标记）：\n'
    '{{\n'
    '    "scene": "场景类型，如：室内/户外/办公室/居家/商场/街道/自然风光/演播室/工厂/餐厅/健身房等，可多个用逗号分隔",\n'
    '    "style": "视频风格，如：专业正式/轻松日常/科技感/温馨治愈/潮流时尚/简约大气/搞笑娱乐/教育讲解/故事叙事/Vlog",\n'
    '    "mood": "情绪基调，如：激昂/温馨/专业/搞笑/冷静/紧迫/治愈/惊讶/信任/焦虑",\n'
    '    "people": "人物特征，如：单人出镜/多人互动/无人出镜/儿童/年轻人/中年人/老年人/男性/女性/专家/明星等，可多个用逗号分隔",\n'
    '    "topic": "主题分类，选择最匹配的1-3个：产品展示/使用教程/对比测评/开箱体验/Vlog日常/美食/旅游/宠物/美妆/穿搭/科技数码/母婴/家居/运动健身/知识科普/新闻资讯/剧情演绎/广告营销",\n'
    '    "visual_keywords": "画面中出现的显著视觉元素关键词，5-10个，用逗号分隔，如：手机,电脑,厨房,宠物狗,化妆品,汽车,书桌,运动鞋,咖啡,绿植",\n'
    '    "summary": "对视频内容的简要概述，30字以内",\n'
    '    "pace": "节奏快慢：快节奏/中等节奏/慢节奏",\n'
    '    "has_text": true,\n'
    '    "duration_category": "预计时长类别：短视频(15-60s)/中视频(1-5min)/长视频(5min+)"\n'
    '}}\n'
)


TIMELINE_PROMPT = (
    '你是一名专业的视频剪辑分析师。请将以下视频按内容变化拆分为连续的片段，描述每个片段的关键内容，以JSON格式输出。\n'
    '\n'
    '要求：\n'
    '- 拆分粒度：根据内容变化拆分，通常一个1分钟视频拆分为5-12个片段\n'
    '- 每个片段需标注起止时间（秒），必须是连续不重叠的，覆盖从0到视频结束\n'
    '- 描述该片段中画面内容、动作、人物、产品等核心信息（20-50字）\n'
    '- 为每个片段打2-4个关键词标签\n'
    '\n'
    '输出格式（只输出JSON，不要包含markdown代码块标记）：\n'
    '{{\n'
    '    "total_duration": 估计的视频总时长秒数,\n'
    '    "segments": [\n'
    '        {{\n'
    '            "index": 0,\n'
    '            "start": 0.0,\n'
    '            "end": 6.5,\n'
    '            "duration": 6.5,\n'
    '            "description": "该片段的具体画面内容描述",\n'
    '            "keywords": ["关键词1", "关键词2", "关键词3"],\n'
    '            "scene_type": "场景类型如室内/户外/特写/全景等",\n'
    '            "has_speech": true,\n'
    '            "mood": "该片段情绪基调"\n'
    '        }}\n'
    '    ]\n'
    '}}\n'
)


def _parse_json_response(raw_text: str) -> dict:
    """从 API 响应中提取 JSON"""
    if not raw_text:
        return {}
    text = raw_text.strip()
    # 去除可能的 markdown 代码块
    if '```json' in text:
        parts = text.split('```json', 1)
        if len(parts) > 1:
            end = parts[1].find('```')
            if end != -1:
                text = parts[1][:end].strip()
    elif '```' in text:
        parts = text.split('```', 2)
        if len(parts) >= 2:
            text = parts[1].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


async def _analyze_with_responses(video_path: str, prompt: str, label: str = "") -> dict:
    """
    核心方法：上传视频 → 等预处理 → responses.create 分析 → 解析JSON
    与 video_analyzer.py 使用相同的调用方式
    """
    if not video_path or not os.path.exists(video_path):
        return {"error": f"视频文件不存在: {video_path}"}

    client = _get_client()
    file_obj = None
    file = None

    try:
        # 1. 上传视频（按官方示例配置 fps 预处理）
        logger.info(f'[{label}] 上传视频: {os.path.basename(video_path)}')
        file_obj = open(video_path, "rb")
        file = await client.files.create(
            file=file_obj,
            purpose="user_data",
            preprocess_configs={
                "video": {
                    "fps": 0.3,
                }
            }
        )
        logger.info(f'[{label}] 上传成功, file_id={file.id}')

        # 2. 等待预处理
        await client.files.wait_for_processing(file.id)
        logger.info(f'[{label}] 预处理完成')

        # 3. 发送分析请求
        response = await client.responses.create(
            model="doubao-seed-2-0-lite-260428",
            input=[
                {"role": "user", "content": [
                    {"type": "input_video", "file_id": file.id},
                    {"type": "input_text", "text": prompt}
                ]},
            ]
        )

        # 4. 提取响应文本
        raw_text = ""
        try:
            if hasattr(response, 'output') and response.output:
                for item in response.output:
                    if hasattr(item, 'content') and item.content:
                        for block in item.content:
                            if hasattr(block, 'text'):
                                raw_text += block.text
            if not raw_text:
                raw_text = str(response)
        except Exception:
            raw_text = str(response)

        logger.info(f'[{label}] 分析完成, 响应长度={len(raw_text)}')

        return {"output": raw_text}

    except Exception as e:
        logger.error(f'[{label}] 分析失败: {type(e).__name__}: {e}')
        return {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    finally:
        if file_obj:
            try:
                file_obj.close()
            except Exception:
                pass
        # 分析完成后删除上传的文件，释放方舟文件存储配额
        if file is not None:
            try:
                await client.files.delete(file.id)
                logger.info(f'[{label}] 已删除方舟临时文件: {file.id}')
            except Exception as e:
                logger.warning(f'[{label}] 删除方舟临时文件失败: {e}')


async def classify_video(video_path: str, video_filename: str = "") -> dict:
    """
    对单个视频进行标签分类。

    Returns:
        dict: 分类标签结果，包含 scene/style/mood/people/topic/visual_keywords/summary 等
    """
    try:
        result = await _analyze_with_responses(video_path, CLASSIFY_PROMPT, label=f"分类-{video_filename}")
        if "error" in result:
            result["video_filename"] = video_filename
            return result

        parsed = _parse_json_response(result["output"])
        parsed["video_filename"] = video_filename
        return parsed

    except Exception as e:
        logger.error(f'视频分类异常 [{video_filename}]: {e}')
        return {"error": str(e)[:200], "video_filename": video_filename}


async def classify_video_with_timeline(video_path: str, video_filename: str = "") -> dict:
    """
    对单个视频进行内容时间线分析，拆分片段并标注时间戳。
    """
    try:
        result = await _analyze_with_responses(video_path, TIMELINE_PROMPT, label=f"时间线-{video_filename}")
        if "error" in result:
            result["video_filename"] = video_filename
            result["segments"] = []
            return result

        parsed = _parse_json_response(result["output"])

        if "segments" in parsed:
            for seg in parsed["segments"]:
                seg.setdefault("index", 0)
                seg.setdefault("start", 0.0)
                seg.setdefault("end", 0.0)
                seg.setdefault("duration", max(1.0, seg.get("end", 0) - seg.get("start", 0)))
                seg.setdefault("description", "")
                seg.setdefault("keywords", [])
                seg.setdefault("scene_type", "")
                seg.setdefault("has_speech", False)
                seg.setdefault("mood", "")

        parsed["video_filename"] = video_filename
        parsed["raw_response"] = result.get("output", "")
        logger.info(f'时间线分析完成 [{video_filename}]: {len(parsed.get("segments", []))} 个片段')
        return parsed

    except json.JSONDecodeError:
        logger.warning(f'时间线JSON解析失败: {video_filename}')
        raw = result.get("output", "")[:300] if result else ""
        return {"error": "JSON解析失败", "raw_response": raw, "video_filename": video_filename, "segments": []}
    except Exception as e:
        logger.error(f'时间线分析异常 [{video_filename}]: {e}')
        return {"error": str(e)[:200], "video_filename": video_filename, "segments": []}


def generate_classification_summary(results: list) -> dict:
    """根据分类结果生成汇总统计"""
    total = len(results)
    success = sum(1 for r in results if 'error' not in r)
    failed = total - success
    all_tags = []
    categories = {}
    for r in results:
        if 'error' in r:
            continue
        topic = r.get('topic', '')
        if topic:
            for t in topic.split(','):
                t = t.strip()
                if t:
                    categories[t] = categories.get(t, 0) + 1
        kw = r.get('visual_keywords', '')
        if kw:
            for k in kw.split(','):
                k = k.strip()
                if k:
                    all_tags.append(k)
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "categories": categories,
        "all_tags": list(set(all_tags))
    }


async def classify_videos_batch(video_paths: list) -> list:
    """批量标签分类"""
    tasks = [classify_video(path, name) for path, name in video_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = []
    for i, r in enumerate(results):
        fname = video_paths[i][1] if i < len(video_paths) else ""
        if isinstance(r, Exception):
            output.append({"error": f"{type(r).__name__}: {str(r)[:200]}", "video_filename": fname})
        else:
            output.append(r)
    return output


def classify_videos_sync(video_paths: list) -> list:
    return asyncio.run(classify_videos_batch(video_paths))


async def classify_videos_with_timeline_batch(video_paths: list) -> list:
    """批量时间线分析"""
    tasks = [classify_video_with_timeline(path, name) for path, name in video_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = []
    for i, r in enumerate(results):
        fname = video_paths[i][1] if i < len(video_paths) else ""
        if isinstance(r, Exception):
            output.append({"error": f"{type(r).__name__}: {str(r)[:200]}", "video_filename": fname, "segments": []})
        else:
            output.append(r)
    return output


def classify_videos_with_timeline_sync(video_paths: list) -> list:
    return asyncio.run(classify_videos_with_timeline_batch(video_paths))
