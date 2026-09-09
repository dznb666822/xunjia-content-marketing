# -*- coding: utf-8 -*-
"""
AI 剪辑方案生成服务（VideoPlan V2.0）

核心思路：直接用豆包 Seed 2.0 多模态模型（doubao-seed-2-0-lite）"看"视频，
让模型基于画面内容 + 语义理解，一次性产出完整剪辑方案 JSON（高光片段 + 包装层 + Style）。

不走 whisper 转写 / 字幕文本分析那条重链路——多模态模型直接理解视频，
更贴合「出方案」这个目标的语义粒度与速度要求。

依赖：火山方舟 Ark（ARK_API_KEY），模型 doubao-seed-2-0-lite-260428。
"""
import asyncio
import os
import json

from loguru import logger
from volcenginesdkarkruntime import AsyncArk


VIDEO_PLAN_MODEL = os.getenv("VIDEO_PLAN_MODEL", "doubao-seed-2-0-lite-260428")


def _get_client() -> AsyncArk:
    return AsyncArk(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=os.getenv("ARK_API_KEY", ""),
    )


def _build_prompt(intent: str, clip_count: int, clip_duration_min: int, clip_duration_max: int) -> str:
    return (
        "你是一名资深短视频剪辑导演，作品对标抖音「口播种草 / 自我提升 Vlog」类爆款。\n"
        "请直接观看这条口播视频，输出一份「剪辑执行级脚本」——颗粒度要达到：\n"
        "剪辑师拿到后无需再看原片，即可逐秒执行剪辑、准备素材、上字幕、加特效。\n"
        "\n"
        "剪辑意图：{intent}\n"
        "期望高光片段数：{clip_count} 个\n"
        "单片段时长范围：{clip_duration_min} - {clip_duration_max} 秒\n"
        "\n"
        "【输出要求】严格输出以下结构的 JSON（只输出 JSON，不要 markdown 代码块，不要额外解释）：\n"
        "{{\n"
        '  "overview": {{\n'
        '    "video_type": "内容类型：口播种草/自我提升/知识分享/带货/剧情/Vlog/评测",\n'
        '    "duration_sec": 视频总秒数(数字),\n'
        '    "aspect_ratio": "9:16 或 16:9",\n'
        '    "core_structure": "核心结构，如：口播主线+动作演示插播+前后对比佐证+结尾清单总结",\n'
        '    "rhythm_curve": "整体节奏，分前/中/后三段描述",\n'
        '    "main_asset_desc": "主口播画面描述（人物/服装/机位/背景/手势习惯）"\n'
        '  }},\n'
        '  "material_assets": {{\n'
        '    "A_main": [ {{ "id":"A1", "desc":"主口播描述", "camera":"机位/景别", "usage":"全片叙事主轴", "notes":"剪辑注意点(如保留手势作字幕切换点)" }} ],\n'
        '    "B_demo": [ {{ "id":"B1", "desc":"动作演示插播素材建议", "duration":"建议时长区间", "shot":"拍摄视角(俯拍/侧拍/特写)", "usage":"对应口播哪句话" }} ],\n'
        '    "C_contrast": [ {{ "id":"C1", "desc":"前后对比/佐证素材建议", "duration":"插入时间", "layout":"版式(左右分屏/全屏/上下残边)", "usage":"佐证哪个观点" }} ],\n'
        '    "D_ui": [ {{ "id":"D1", "desc":"UI/截图/卡片素材", "usage":"用途" }} ],\n'
        '    "E_sticker": [ {{ "id":"E1", "desc":"贴纸/特效元素", "usage":"配合哪个词/动作弹出" }} ]\n'
        '  }},\n'
        '  "timeline": [\n'
        '    {{\n'
        '      "start": 秒(数字), "end": 秒(数字),\n'
        '      "asset": "用哪个素材(如 A主口播 / B1 / C2 / D1 / E1)",\n'
        '      "edit": "剪辑手法/特效(硬切/插播/zoom转场/画中画/甩镜/淡入淡出)",\n'
        '      "subtitle": {{ "text":"字幕文字", "style":"白字/黄字/蓝公式字", "position":"下1/3居中/压图底部" }},\n'
        '      "audio": "音频/节奏(口播/BGM副歌/音效/节奏点)"\n'
        '    }}\n'
        '  ],\n'
        '  "subtitle_system": {{\n'
        '    "font_main": "主字幕字体风格(如 衬线斜体/宋体粗斜)",\n'
        '    "font_formula": "公式/强调字字体(如 无衬线黑体加粗)",\n'
        '    "colors": {{ "normal":"普通叙述配色(如 纯白+黑细描边)", "emphasis":"重点情绪词配色(如 柠檬黄#F0D060+黑描边)", "formula":"公式配色(如 浅蓝#BFE3F2+深蓝粗描边)" }},\n'
        '    "position": "统一位置规范(如 画面下1/3居中，单行≤12字)",\n'
        '    "animation": "字幕动画规范(如 整句直接出现，仅公式字pop弹入)",\n'
        '    "font_size": "字号规范(如 主字幕约屏宽1/12，公式字放大1.5倍)"\n'
        '  }},\n'
        '  "effects": [ {{ "name":"特效名", "time":"出现时间段", "desc":"实现描述" }} ],\n'
        '  "rhythm_design": [\n'
        '    {{ "segment":"时间区间", "name":"段落名", "pace":"镜头节奏", "subtitle":"字幕策略", "audio":"音频策略" }}\n'
        '  ],\n'
        '  "style": {{\n'
        '    "name": "knowledge/entertainment/news/vlog/cute/luxury_bilingual_white 选一",\n'
        '    "display_name": "风格中文名",\n'
        '    "description": "为什么选这个风格(1句)",\n'
        '    "config": {{ "subtitle_color":"#hex", "subtitle_font":"字体", "bgm_style":"BGM建议", "accent_color":"#hex" }}\n'
        '  }},\n'
        '  "clips": [\n'
        '    {{ "start":秒,"end":秒,"title":"片段小标题","reason":"为何是高光","quote_text":"关键口播台词","clip_type":"开场钩子/核心干货/情绪高潮/转化引导","energy_level":"低/中/高",\n'
        '       "scores":{{"information_density":0.0,"emotional_tension":0.0,"completeness":0.0,"virality":0.0,"rhythm_fit":0.0}} }}\n'
        '  ],\n'
        '  "packaging": {{\n'
        '    "subtitle_styles": [ {{ "text":"关键句", "style":{{"font":"字体","size":字号,"color":"颜色","effect":"动效","keywords":["词1","词2"]}} }} ],\n'
        '    "sfx_events": [ {{ "time":秒, "category":"转场/强调/氛围", "intensity":"低/中/高" }} ],\n'
        '    "bgm": {{ "track":"BGM风格", "genre":"曲风", "tempo":"BPM" }},\n'
        '    "effect_events": [ {{ "time":秒, "type":"转场/缩放/震动/高亮", "intensity":"低/中/高" }} ]\n'
        '  }}\n'
        '}}\n'
        "\n"
        "【硬性要求】\n"
        "1. timeline 是核心，必须无缝覆盖全片（0 → 视频总时长，不重叠、不断档）；\n"
        "   按 1-3 秒粒度逐段切分（总条目 ≈ 视频秒数/2；若视频超 90 秒可放宽到 3-4 秒/条），每条必须写全「用哪个素材 + 什么剪辑手法 + 什么字幕 + 什么音频」；\n"
        "2. 所有时间戳（timeline/clips/effects/packaging 里的 time）必须是视频内真实秒数，且 end > start；\n"
        "3. 字幕 style 只用三种枚举：白字(普通叙述) / 黄字(重点情绪词) / 蓝公式字(公式或关键数字)；\n"
        "4. material_assets 的 B/C/D/E 是「建议用户额外拍摄/准备的素材」，要具体到能直接开拍/开做（含视角、构图、内容、对应口播句）；\n"
        "5. clips 是与 timeline 对齐的「高光片段」摘要，数量尽量接近 {clip_count}，单片段 {clip_duration_min}-{clip_duration_max} 秒；\n"
        "6. scores 五个维度均为 0-1 小数；\n"
        "7. 只输出 JSON 本身。"
    ).format(
        intent=intent,
        clip_count=clip_count,
        clip_duration_min=clip_duration_min,
        clip_duration_max=clip_duration_max,
    )


async def generate_video_plan(
    video_path: str,
    intent: str = "提取精彩片段",
    clip_count: int = 5,
    clip_duration_min: int = 15,
    clip_duration_max: int = 90,
) -> dict:
    """多模态直出剪辑方案 VideoPlan。

    Returns:
        dict: {"success": True, "video_plan": {...}} 或 {"success": False, "error": "..."}
    """
    if not video_path or not os.path.exists(video_path):
        return {"success": False, "error": "视频文件不存在: {}".format(video_path)}

    prompt = _build_prompt(intent, clip_count, clip_duration_min, clip_duration_max)
    client = _get_client()
    file_obj = None
    file = None

    try:
        logger.info("[video_plan] 上传视频: {}".format(video_path))
        file_obj = open(video_path, "rb")
        file = await client.files.create(
            file=file_obj,
            purpose="user_data",
            preprocess_configs={"video": {"fps": 0.5}},
        )
        logger.info("[video_plan] 上传成功 file_id={}".format(file.id))

        logger.info("[video_plan] 等待预处理 file_id={}".format(file.id))
        await client.files.wait_for_processing(file.id)

        logger.info("[video_plan] 多模态分析中 file_id={}".format(file.id))
        response = await client.responses.create(
            model=VIDEO_PLAN_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_video", "file_id": file.id},
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
        )

        raw_text = ""
        if hasattr(response, "output") and response.output:
            for item in response.output:
                if hasattr(item, "content") and item.content:
                    for block in item.content:
                        if hasattr(block, "text"):
                            raw_text += block.text
        if not raw_text:
            raw_text = str(response)

        logger.info("[video_plan] 分析完成，响应 {} 字符".format(len(raw_text)))

        video_plan = _parse_plan_json(raw_text)
        if video_plan is None:
            return {
                "success": False,
                "error": "多模态响应无法解析为 JSON",
                "raw_response": raw_text[:2000],
            }

        # 注入生成元信息（落库时用于 planner_model / analyzer_meta）
        video_plan.setdefault("generated_by", VIDEO_PLAN_MODEL)
        video_plan.setdefault("schema_version", "3.0")

        return {"success": True, "video_plan": video_plan}

    except Exception as e:
        logger.error("[video_plan] 生成失败: {}".format(e))
        return {"success": False, "error": str(e)}
    finally:
        if file_obj is not None:
            try:
                file_obj.close()
            except Exception:
                pass
        if file is not None:
            try:
                await client.files.delete(file.id)
                logger.info("[video_plan] 已清理方舟临时文件 {}".format(file.id))
            except Exception as e:
                logger.warning("[video_plan] 清理临时文件失败: {}".format(e))


def _parse_plan_json(raw_text: str) -> dict | None:
    """从多模态响应中容错提取 VideoPlan JSON。"""
    text = (raw_text or "").strip()
    if not text:
        return None

    # 直接解析
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 去掉 ```json ... ``` 包裹
    import re
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # 提取第一个 { ... } 块
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def generate_video_plan_sync(
    video_path: str,
    intent: str = "提取精彩片段",
    clip_count: int = 5,
    clip_duration_min: int = 15,
    clip_duration_max: int = 90,
) -> dict:
    """同步版本。"""
    return asyncio.run(generate_video_plan(
        video_path=video_path,
        intent=intent,
        clip_count=clip_count,
        clip_duration_min=clip_duration_min,
        clip_duration_max=clip_duration_max,
    ))
