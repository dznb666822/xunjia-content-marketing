# -*- coding: utf-8 -*-
"""TTS 语音合成 —— 多供应商门面。

上层（AI 剪辑的 `ttsline.py`、混剪的 `video_mashup.py`）只认这一层，
不关心背后是谁在合成。切换靠环境变量：

    TTS_PROVIDER=volc        ← 默认。火山引擎 · 豆包语音合成大模型（走外网 API）
    TTS_PROVIDER=cosyvoice   ← 退路。本地 CosyVoice-300M-SFT（WSL 里那个 HTTP 服务）

为什么默认是 volc：本地那套要人肉在 WSL 里起服务、跑在 GPU 上、还得自己管端口；
火山是托管的，配一把 key 就能用，而且豆包 2.0 的音色质量/角色数量都更好。

⚠️ 两个 provider 的**音色 ID 不通用**（火山是 `zh_female_xxx_uranus_bigtts`，
   CosyVoice 是「中文女」这种中文名），语速单位也不同（倍率 vs speed 浮点）。
   这些都在这层换算掉；`ttsline.sync()` 会在导出时把失效音色重置为当前默认。

⚠️ 火山的具体协议、错误码、实测结论 → 见 `services/tts_volc.py` 的模块 docstring。
"""
import os

import requests
from loguru import logger

from services import tts_volc

# ---------------------------------------------------------------------------
# 供应商选择
# ---------------------------------------------------------------------------
PROVIDERS = ('volc', 'cosyvoice')


def active_provider():
    forced = (os.environ.get('TTS_PROVIDER') or '').strip().lower()
    return forced if forced in PROVIDERS else 'volc'


# ---------------------------------------------------------------------------
# 门面 API
# ---------------------------------------------------------------------------
def get_voice_library():
    if active_provider() == 'volc':
        return tts_volc.get_voice_library()
    return COSY_VOICE_LIBRARY


def default_voice():
    if active_provider() == 'volc':
        return tts_volc.DEFAULT_VOICE
    return COSY_DEFAULT_VOICE


def default_rate():
    if active_provider() == 'volc':
        return tts_volc.DEFAULT_RATE
    return COSY_DEFAULT_RATE


def audio_ext():
    """落盘扩展名。火山用 mp3（流式返回 wav header 会重复，见 tts_volc 注释）。"""
    return 'mp3' if active_provider() == 'volc' else 'wav'


def has_voice(voice_id):
    return any(v['id'] == voice_id for v in get_voice_library())


def voice_name(voice_id):
    for v in get_voice_library():
        if v['id'] == voice_id:
            return v['name']
    return voice_id


def resolve_voice(style_tone='', script='', preferred=''):
    if active_provider() == 'volc':
        return tts_volc.resolve_voice(style_tone, script, preferred)
    return _cosy_resolve_voice(style_tone, script, preferred)


def synthesize(text, output_path, voice=None, rate=None):
    """文本 → 音频文件。返回落盘路径。异常统一带「去哪儿修」的说明。"""
    voice = voice or default_voice()
    rate = rate if rate not in (None, '') else default_rate()
    if active_provider() == 'volc':
        return tts_volc.synthesize(text, output_path, voice=voice, rate=rate)
    return _cosy_synthesize(text, output_path, voice=voice, rate=rate)


def clone_synthesize(text, output_path, prompt_wav_path, prompt_text='', rate=None):
    """零样本克隆音色 —— 只有本地 CosyVoice 有这能力；火山走「声音复刻」是另一套接口。"""
    if active_provider() == 'volc':
        raise RuntimeError(
            '声音复刻请用火山「豆包声音复刻大模型」（Resource ID: seed-icl-2.0），'
            '需要在控制台先训练音色；本模块暂未接入。')
    return _cosy_clone_synthesize(text, output_path, prompt_wav_path,
                                  prompt_text, rate if rate not in (None, '') else default_rate())


def friendly_error(e):
    """把底层异常翻成「看得懂 + 知道去哪儿修」。"""
    if isinstance(e, tts_volc.VolcTtsError):
        return str(e)
    name = type(e).__name__
    s = str(e)
    low = s.lower()
    if active_provider() == 'volc':
        if ('connectionerror' in low or 'newconnectionerror' in low
                or 'refused' in low or '拒绝' in s or '无法连接' in s
                or 'getaddrinfo' in low or 'name resolution' in low):
            return ('连不上火山语音合成服务（{}）—— 容器内需要能出外网。'
                    .format(tts_volc.cfg()['endpoint']))
        if 'timeout' in low or 'timed out' in low:
            return '火山语音合成响应超时，稍后重试。'
        return '火山语音合成失败：{}'.format(s[:300])
    # CosyVoice
    if ('connectionerror' in low or 'newconnectionerror' in low
            or 'refused' in low or '拒绝' in s or '无法连接' in s
            or 'name resolution' in low or 'getaddrinfo' in low):
        return ('CosyVoice 服务连不上（{}）—— 需要在 WSL 里把 '
                'custom_server.py 跑起来（监听 0.0.0.0:50000）。'.format(TTS_SERVICE_URL))
    if 'timeout' in low or 'timed out' in low:
        return 'CosyVoice 响应超时（{}）—— 合成排队太长或服务卡住，稍后重试。'.format(TTS_SERVICE_URL)
    if 'httperror' in low:
        return 'CosyVoice 返回错误（{}）：{}'.format(TTS_SERVICE_URL, s[:200])
    return '合成失败：{}'.format(s[:300])


def status():
    """当前 provider 的状态（给前端出参 / 自检脚本用）。"""
    if active_provider() == 'volc':
        st = tts_volc.status()
    else:
        st = {
            'provider': 'cosyvoice',
            'label': '本地 CosyVoice-300M-SFT',
            'configured': True,
            'missing': [],
            'endpoint': TTS_SERVICE_URL,
            'resource_id': None,
            'auth': None,
            'format': 'wav',
            'sample_rate': 22050,
            'emotion': None,
            'voice_count': len(COSY_VOICE_LIBRARY),
        }
    st['default_voice'] = default_voice()
    st['default_rate'] = default_rate()
    st['audio_ext'] = audio_ext()
    return st


# ===========================================================================
# 本地 CosyVoice 落地实现（退路，不删）
# ===========================================================================
# CosyVoice 服务地址（WSL 内监听 0.0.0.0:50000，Windows 侧通过 localhost 访问）
COSYVOICE_URL = os.environ.get('COSYVOICE_URL', 'http://127.0.0.1:50000')
TTS_SERVICE_URL = COSYVOICE_URL      # 老名字，保留：历史脚本/文档还在引用

# 上传参考音频的存储目录（克隆音色用）
CLONE_AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'datas', 'uploads', 'clone_audio'
)

# CosyVoice-300M-SFT 预置音色库
COSY_VOICE_LIBRARY = [
    {
        "id": "中文女", "name": "中文女", "gender": "female", "desc": "自然亲切女声",
        "tags": ["通用", "产品", "带货", "种草", "温馨", "治愈", "情感", "故事", "舒缓",
                 "宠物", "母婴", "家居", "护肤", "美妆"],
    },
    {
        "id": "中文男", "name": "中文男", "gender": "male", "desc": "沉稳自然男声",
        "tags": ["专业", "权威", "新闻", "商务", "企业", "金融", "地产", "科技", "教程",
                 "技术", "干货", "讲解", "测评", "纪录片", "资讯"],
    },
    {"id": "英文女", "name": "英文女", "gender": "female", "desc": "英文女声", "tags": ["英语", "英文"]},
    {"id": "英文男", "name": "英文男", "gender": "male", "desc": "英文男声", "tags": ["英语", "英文"]},
    {"id": "日语男", "name": "日语男", "gender": "male", "desc": "日语男声", "tags": ["日语", "日文"]},
    {"id": "韩语女", "name": "韩语女", "gender": "female", "desc": "韩语女声", "tags": ["韩语", "韩文"]},
    {"id": "粤语女", "name": "粤语女", "gender": "female", "desc": "粤语女声", "tags": ["粤语", "广东话", "港风"]},
]
COSY_DEFAULT_VOICE = '中文女'
# 实测 speed=1.0 约 302 字/分钟，对带货短视频偏快；0.88 约 254 字/分钟，
# 贴合「好物带货 250 字/分钟」的推荐节奏。
COSY_DEFAULT_RATE = 0.88


def _cosy_voice_name(voice_id):
    for v in COSY_VOICE_LIBRARY:
        if v['id'] == voice_id:
            return v['name']
    return voice_id


def _cosy_resolve_voice(style_tone='', script='', preferred=''):
    if preferred and preferred not in ('', 'auto'):
        if preferred in [v['id'] for v in COSY_VOICE_LIBRARY]:
            return {'id': preferred, 'name': _cosy_voice_name(preferred)}
        for v in COSY_VOICE_LIBRARY:
            if v['name'] == preferred:
                return {'id': v['id'], 'name': v['name']}

    text = '{} {}'.format(style_tone or '', script or '')
    rules = [
        (["女", "温柔", "温馨", "治愈", "情感", "故事", "舒缓", "宠物", "萌", "可爱",
          "母婴", "家居", "护肤", "美妆", "种草", "带货"], "中文女"),
        (["专业", "权威", "新闻", "正式", "商务", "企业", "金融", "地产", "发布会",
          "纪录片", "沉稳", "科技", "教程", "技术", "干货", "讲解", "测评", "数码"], "中文男"),
        (["粤语", "广东话", "港风"], "粤语女"),
        (["英语", "英文"], "英文女"),
    ]
    for keywords, voice_id in rules:
        if any(k in text for k in keywords):
            return {'id': voice_id, 'name': _cosy_voice_name(voice_id)}
    return {'id': COSY_DEFAULT_VOICE, 'name': _cosy_voice_name(COSY_DEFAULT_VOICE)}


def _cosy_synthesize(text, output_path, voice=COSY_DEFAULT_VOICE, rate=COSY_DEFAULT_RATE):
    text = (text or '').strip()
    if not text:
        raise ValueError('合成文本为空')

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    speed = max(0.5, min(2.0, float(rate or COSY_DEFAULT_RATE)))

    resp = requests.post(
        TTS_SERVICE_URL + '/inference_sft',
        data={'tts_text': text, 'spk_id': voice, 'speed': str(speed)},
        timeout=600,
    )
    resp.raise_for_status()

    audio = resp.content
    if not audio:
        raise RuntimeError('TTS 合成失败：返回空音频')

    with open(output_path, 'wb') as f:
        f.write(audio)

    if os.path.getsize(output_path) == 0:
        raise RuntimeError('TTS 合成失败：未生成有效音频')

    logger.info('CosyVoice 合成完成: voice={}, speed={}, len={}字 -> {}'.format(
        voice, speed, len(text), output_path))
    return output_path


def _cosy_clone_synthesize(text, output_path, prompt_wav_path, prompt_text='',
                           rate=COSY_DEFAULT_RATE):
    text = (text or '').strip()
    if not text:
        raise ValueError('合成文本为空')
    if not prompt_wav_path or not os.path.exists(prompt_wav_path):
        raise ValueError('参考音频不存在')

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    speed = max(0.5, min(2.0, float(rate or COSY_DEFAULT_RATE)))

    with open(prompt_wav_path, 'rb') as f:
        resp = requests.post(
            TTS_SERVICE_URL + '/inference_zero_shot',
            data={'tts_text': text, 'prompt_text': prompt_text or '', 'speed': str(speed)},
            files={'prompt_wav': (os.path.basename(prompt_wav_path), f, 'audio/wav')},
            timeout=600,
        )
    resp.raise_for_status()

    audio = resp.content
    if not audio:
        raise RuntimeError('TTS 克隆合成失败：返回空音频')

    with open(output_path, 'wb') as f:
        f.write(audio)

    if os.path.getsize(output_path) == 0:
        raise RuntimeError('TTS 克隆合成失败：未生成有效音频')

    logger.info('CosyVoice 克隆合成完成: len={}字 -> {}'.format(len(text), output_path))
    return output_path


# 模块级快照 —— 给还在直接读常量的历史代码留的（video_mashup 等）。别在新代码里用。
# ★ 必须放在 COSY_VOICE_LIBRARY 等常量定义**之后**：provider=cosyvoice 时
#   get_voice_library() 会去读 COSY_VOICE_LIBRARY，提前求值就是 NameError。
VOICE_LIBRARY = get_voice_library()
DEFAULT_VOICE = default_voice()
DEFAULT_RATE = default_rate()

