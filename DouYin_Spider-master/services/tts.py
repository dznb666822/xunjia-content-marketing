# -*- coding: utf-8 -*-
"""
TTS 语音合成服务（CosyVoice-300M-SFT 本地服务）

- 内置中文音色库，支持按「品牌风格调性 + 文案内容」智能配对音色
- 调用本地 CosyVoice HTTP 服务（WSL 内）将文案合成为 WAV 音频，供智能混剪叠加配音使用
"""
import os
import requests
from loguru import logger

# CosyVoice 服务地址（WSL 内监听 0.0.0.0:50000，Windows 侧通过 localhost 访问）
TTS_SERVICE_URL = os.environ.get("COSYVOICE_URL", "http://127.0.0.1:50000")

# 上传参考音频的存储目录（克隆音色用）
CLONE_AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'datas', 'uploads', 'clone_audio'
)

# CosyVoice-300M-SFT 预置音色库
VOICE_LIBRARY = [
    {
        "id": "中文女",
        "name": "中文女",
        "gender": "female",
        "desc": "自然亲切女声",
        "tags": ["通用", "产品", "带货", "种草", "温馨", "治愈", "情感", "故事", "舒缓", "宠物", "母婴", "家居", "护肤", "美妆"],
    },
    {
        "id": "中文男",
        "name": "中文男",
        "gender": "male",
        "desc": "沉稳自然男声",
        "tags": ["专业", "权威", "新闻", "商务", "企业", "金融", "地产", "科技", "教程", "技术", "干货", "讲解", "测评", "纪录片", "资讯"],
    },
    {
        "id": "英文女",
        "name": "英文女",
        "gender": "female",
        "desc": "英文女声",
        "tags": ["英语", "英文"],
    },
    {
        "id": "英文男",
        "name": "英文男",
        "gender": "male",
        "desc": "英文男声",
        "tags": ["英语", "英文"],
    },
    {
        "id": "日语男",
        "name": "日语男",
        "gender": "male",
        "desc": "日语男声",
        "tags": ["日语", "日文"],
    },
    {
        "id": "韩语女",
        "name": "韩语女",
        "gender": "female",
        "desc": "韩语女声",
        "tags": ["韩语", "韩文"],
    },
    {
        "id": "粤语女",
        "name": "粤语女",
        "gender": "female",
        "desc": "粤语女声",
        "tags": ["粤语", "广东话", "港风"],
    },
]

DEFAULT_VOICE = "中文女"

# 默认语速（CosyVoice speed 参数）。实测 speed=1.0 约 302 字/分钟，对带货短视频偏快；
# 0.88 约 254 字/分钟，贴合「好物带货 250 字/分钟」的推荐节奏。
DEFAULT_RATE = 0.88


def get_voice_library() -> list:
    """返回音色库（供前端下拉框使用）。"""
    return VOICE_LIBRARY


def _voice_name(voice_id: str) -> str:
    for v in VOICE_LIBRARY:
        if v["id"] == voice_id:
            return v["name"]
    return voice_id


def resolve_voice(style_tone: str = "", script: str = "", preferred: str = "") -> dict:
    """
    智能配对音色：优先使用用户指定音色，否则根据品牌调性和文案关键词匹配。

    Returns:
        {"id": "中文女", "name": "中文女"}
    """
    if preferred and preferred not in ("", "auto"):
        if preferred in [v["id"] for v in VOICE_LIBRARY]:
            return {"id": preferred, "name": _voice_name(preferred)}
        for v in VOICE_LIBRARY:
            if v["name"] == preferred:
                return {"id": v["id"], "name": v["name"]}

    text = "{} {}".format(style_tone or "", script or "")

    # 按优先级顺序匹配（越靠前越优先）
    rules = [
        (["女", "温柔", "温馨", "治愈", "情感", "故事", "舒缓", "宠物", "萌", "可爱", "母婴", "家居", "护肤", "美妆", "种草", "带货"], "中文女"),
        (["专业", "权威", "新闻", "正式", "商务", "企业", "金融", "地产", "发布会", "纪录片", "沉稳", "科技", "教程", "技术", "干货", "讲解", "测评", "数码"], "中文男"),
        (["粤语", "广东话", "港风"], "粤语女"),
        (["英语", "英文"], "英文女"),
    ]

    for keywords, voice_id in rules:
        if any(k in text for k in keywords):
            return {"id": voice_id, "name": _voice_name(voice_id)}

    return {"id": DEFAULT_VOICE, "name": _voice_name(DEFAULT_VOICE)}


def synthesize(text: str, output_path: str, voice: str = DEFAULT_VOICE, rate: float = DEFAULT_RATE) -> str:
    """
    将文本合成为音频文件（WAV）。

    Args:
        text: 待合成文本
        output_path: 输出文件路径（建议 .wav）
        voice: 音色 ID（预置音色，如「中文女」「中文男」）
        rate: 语速倍率（0.5~2.0），映射为 CosyVoice speed

    Returns:
        输出文件路径
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("合成文本为空")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    speed = max(0.5, min(2.0, float(rate or DEFAULT_RATE)))

    resp = requests.post(
        TTS_SERVICE_URL + "/inference_sft",
        data={"tts_text": text, "spk_id": voice, "speed": str(speed)},
        timeout=600,
    )
    resp.raise_for_status()

    audio = resp.content
    if not audio:
        raise RuntimeError("TTS 合成失败：返回空音频")

    with open(output_path, "wb") as f:
        f.write(audio)

    if os.path.getsize(output_path) == 0:
        raise RuntimeError("TTS 合成失败：未生成有效音频")

    logger.info("TTS 合成完成: voice={}, speed={}, len={}字 -> {}".format(voice, speed, len(text), output_path))
    return output_path


def clone_synthesize(text: str, output_path: str, prompt_wav_path: str, prompt_text: str = "", rate: float = DEFAULT_RATE) -> str:
    """
    上传参考音频，零样本克隆其音色后合成语音（WAV）。

    Args:
        text: 待合成文本
        output_path: 输出文件路径（建议 .wav）
        prompt_wav_path: 参考音频文件路径（几秒~十几秒的清晰人声）
        prompt_text: 参考音频对应的文字内容（可选，建议填写以提升克隆效果）
        rate: 语速倍率（0.5~2.0）

    Returns:
        输出文件路径
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("合成文本为空")
    if not prompt_wav_path or not os.path.exists(prompt_wav_path):
        raise ValueError("参考音频不存在")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    speed = max(0.5, min(2.0, float(rate or DEFAULT_RATE)))

    with open(prompt_wav_path, "rb") as f:
        resp = requests.post(
            TTS_SERVICE_URL + "/inference_zero_shot",
            data={"tts_text": text, "prompt_text": prompt_text or "", "speed": str(speed)},
            files={"prompt_wav": (os.path.basename(prompt_wav_path), f, "audio/wav")},
            timeout=600,
        )
    resp.raise_for_status()

    audio = resp.content
    if not audio:
        raise RuntimeError("TTS 克隆合成失败：返回空音频")

    with open(output_path, "wb") as f:
        f.write(audio)

    if os.path.getsize(output_path) == 0:
        raise RuntimeError("TTS 克隆合成失败：未生成有效音频")

    logger.info("TTS 克隆合成完成: len={}字 -> {}".format(len(text), output_path))
    return output_path
