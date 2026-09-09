# -*- coding: utf-8 -*-
"""
豆包 Seed 2.0 视频内容分析服务
使用火山方舟 Ark SDK 调用多模态模型分析视频结构、类型、场景和情绪
"""
import asyncio
import os
import json
from loguru import logger

from volcenginesdkarkruntime import AsyncArk


def _get_client():
    """获取 AsyncArk 客户端实例"""
    return AsyncArk(
        base_url='https://ark.cn-beijing.volces.com/api/v3',
        api_key=os.getenv('ARK_API_KEY', '')
    )


async def analyze_video(video_path: str, video_title: str = "", video_desc: str = "") -> dict:
    """
    使用豆包 Seed 2.0 多模态模型分析视频内容。

    Args:
        video_path: 视频文件本地路径
        video_title: 视频标题
        video_desc: 视频文案描述

    Returns:
        dict: {
            "text_structure": {"hook": "钩子内容", "body": "正文叙事逻辑", "cta": "转化引导"},
            "video_type": "视频类型标签",
            "scene_desc": "画面场景描述",
            "mood": "情绪基调",
            "raw_response": "原始响应"
        }
        出错时返回包含 "error" 字段的字典
    """
    prompt = (
        '你是一名专业的带货短视频编导分析师。请深度分析以下带货短视频的内容结构、营销策略和分镜设计，以JSON格式输出。\n'
        '\n'
        '视频标题：{title}\n'
        '视频文案：{desc}\n'
        '\n'
        '请从以下几个维度进行分析，并输出以下结构的JSON（只输出JSON，不要包含markdown代码块标记）：\n'
        '{{\n'
        '    "text_structure": {{\n'
        '        "hook": "前3秒的抓睛点/痛点切入/好奇钩子是什么，用了什么具体手法",\n'
        '        "body": "正文的叙事逻辑、产品展示方式、卖点阐述顺序、使用场景还原、信任建立手段",\n'
        '        "cta": "结尾的转化引导策略（限时优惠/点击购物车/引导主页/评论区互动等）"\n'
        '    }},\n'
        '    "video_type": "带货类型：纯产品展示/使用教程/对比测评/剧情植入/专家讲解/用户证言/开箱体验/Vlog种草",\n'
        '    "scene_desc": "拍摄场景与视觉风格：拍摄环境、人物状态、画面切换节奏、色调风格、产品呈现方式",\n'
        '    "mood": "情绪基调：紧迫/温馨/专业/搞笑/惊讶/信任/焦虑",\n'
        '    "product_analysis": {{\n'
        '        "product_category": "产品品类",\n'
        '        "selling_points": "提炼出的核心卖点（1-3点）",\n'
        '        "target_audience": "目标受众画像",\n'
        '        "pain_points": "解决的痛点" \n'
        '    }},\n'
        '    "marketing_strategy": {{\n'
        '        "trust_building": "信任建立方式（权威背书/效果展示/用户评价/数据证明等）",\n'
        '        "urgency_tactics": "紧迫感营造手法（限时/限量/错过不再有等）",\n'
        '        "interaction_guide": "互动引导手法（评论区话题/点赞引导/关注理由等）"\n'
        '    }},\n'
        '    "storyboard": [\n'
        '        {{\n'
        '            "shot_number": 1,\n'
        '            "shot_type": "景别/视角/构图，如：特写/中景/全景/俯拍/平视/三分法构图",\n'
        '            "camera_movement": "运镜方式，如：固定/推镜/拉镜/摇镜/跟随/手持",\n'
        '            "visual_content": "画面中看到的具体内容，包括产品、人物动作、文字等",\n'
        '            "character_scene": "人物状态与拍摄场景描述",\n'
        '            "dialogue": "对应的台词或旁白内容",\n'
        '            "sound_effect": "音效/背景音乐描述",\n'
        '            "duration_seconds": 3.5,\n'
        '            "key_frame_time": 2.0\n'
        '        }}\n'
        '    ]\n'
        '}}\n'
        '\n'
        '注意：storyboard 中的 key_frame_time 是该分镜中最具代表性的一帧的时间点（以秒为单位，从视频开头开始计算），\n'
        '请尽可能精确到秒，每个分镜提供1个最关键的帧时间点。duration_seconds 是该分镜的预估持续时长。\n'
        '\n'
        '请将整个视频拆分为5-15个核心分镜，覆盖视频从开头到结尾的所有关键画面转换。'
    ).format(title=video_title, desc=video_desc)

    # 1. 检查文件是否存在
    if not video_path or not os.path.exists(video_path):
        error_msg = '视频文件不存在: {}'.format(video_path)
        logger.error(error_msg)
        return {"error": error_msg}

    client = _get_client()
    file_obj = None
    file = None

    try:
        # 2. 上传视频文件
        logger.info('开始上传视频文件: {}'.format(video_path))
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
        logger.info('视频文件上传成功, file_id: {}'.format(file.id))

        # 3. 等待预处理完成
        logger.info('等待视频预处理: file_id={}'.format(file.id))
        await client.files.wait_for_processing(file.id)
        logger.info('视频预处理完成: file_id={}'.format(file.id))

        # 4. 发送多模态分析请求
        logger.info('开始多模态分析: file_id={}'.format(file.id))
        response = await client.responses.create(
            model="doubao-seed-2-0-lite-260428",
            input=[
                {"role": "user", "content": [
                    {"type": "input_video", "file_id": file.id},
                    {"type": "input_text", "text": prompt}
                ]},
            ]
        )

        # 5. 提取响应文本
        raw_text = ""
        try:
            # Ark SDK responses API 返回格式：response.output 中包含消息列表
            if hasattr(response, 'output') and response.output:
                for item in response.output:
                    if hasattr(item, 'content') and item.content:
                        for block in item.content:
                            if hasattr(block, 'text'):
                                raw_text += block.text
            if not raw_text:
                raw_text = str(response)
        except Exception as e:
            logger.warning('提取响应文本时出错，使用原始响应: {}'.format(e))
            raw_text = str(response)

        logger.info('分析请求完成，原始响应长度: {} 字符'.format(len(raw_text)))

        # 6. 解析JSON
        try:
            # 去除可能包裹的markdown代码块标记
            clean_text = raw_text.strip()
            if clean_text.startswith("```"):
                lines = clean_text.split("\n")
                # 去掉第一行 ```json 或 ```
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                # 去掉最后一行 ```
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                clean_text = "\n".join(lines)

            parsed = json.loads(clean_text)
            storyboard = parsed.get("storyboard", [])
            result = {
                "text_structure": parsed.get("text_structure", {}),
                "video_type": parsed.get("video_type", ""),
                "scene_desc": parsed.get("scene_desc", ""),
                "mood": parsed.get("mood", ""),
                "product_analysis": parsed.get("product_analysis", {}),
                "marketing_strategy": parsed.get("marketing_strategy", {}),
                "storyboard": storyboard,
                "raw_response": raw_text
            }
            logger.info('JSON解析成功, video_type: {}'.format(result.get("video_type")))
            return result

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning('JSON解析失败: {}'.format(e))
            return {
                "text_structure": {},
                "video_type": "",
                "scene_desc": "",
                "mood": "",
                "raw_response": raw_text,
                "error": "JSON解析失败: {}".format(str(e))
            }

    except Exception as e:
        error_msg = '视频分析失败: {}'.format(str(e))
        logger.error(error_msg)
        return {"error": error_msg}
    finally:
        if file_obj is not None:
            try:
                file_obj.close()
            except Exception:
                pass
        # 分析完成后删除上传的文件，释放方舟文件存储配额
        if file is not None:
            try:
                await client.files.delete(file.id)
                logger.info('已删除方舟临时文件: {}'.format(file.id))
            except Exception as e:
                logger.warning('删除方舟临时文件失败: {}'.format(e))


def analyze_video_sync(video_path: str, video_title: str = "", video_desc: str = "") -> dict:
    """同步版本，内部调用 asyncio.run(analyze_video(...))"""
    return asyncio.run(analyze_video(video_path, video_title, video_desc))


async def _analyze_cover_image(cover_url: str, video_title: str = "") -> dict:
    """
    使用豆包 Seed 2.0 多模态模型分析视频封面图片内容。

    Args:
        cover_url: 封面图片URL
        video_title: 视频标题（用于辅助理解）

    Returns:
        dict: {"cover_desc": "封面内容描述", "error": "..."}
    """
    if not cover_url:
        return {"cover_desc": "", "error": "无封面URL"}

    prompt = (
        '请简要描述这张视频封面的内容（1-2句话即可），包括：\n'
        '1. 画面主体（人物/产品/场景）\n'
        '2. 色调和视觉风格\n'
        '3. 封面上是否有文字，文字内容是什么\n'
        '\n'
        '视频标题：{title}\n'
        '\n'
        '请直接输出描述，无需JSON格式。'
    ).format(title=video_title)

    client = _get_client()

    try:
        logger.info('开始分析封面图片: title={}'.format(video_title[:50]))
        response = await client.responses.create(
            model="doubao-seed-2-0-lite-260428",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": cover_url},
                    {"type": "input_text", "text": prompt}
                ]
            }]
        )

        raw_text = ""
        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'content') and item.content:
                    for block in item.content:
                        if hasattr(block, 'text'):
                            raw_text += block.text
        if not raw_text:
            raw_text = str(response)

        desc = raw_text.strip()
        logger.info('封面分析完成: {} ({})'.format(desc[:80], len(desc)))
        return {"cover_desc": desc}

    except Exception as e:
        logger.error('封面分析失败: {}'.format(str(e)))
        return {"cover_desc": "", "error": str(e)}


def analyze_cover_image_sync(cover_url: str, video_title: str = "") -> dict:
    """同步版本：分析视频封面图片内容"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_analyze_cover_image(cover_url, video_title))
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()
