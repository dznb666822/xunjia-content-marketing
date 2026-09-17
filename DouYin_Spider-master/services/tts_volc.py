# -*- coding: utf-8 -*-
"""火山引擎 · 豆包语音合成大模型（TTS）客户端。

──── 为什么单独一个模块 ────────────────────────────────────────────────

火山方舟的 TTS **不在** `ark.cn-beijing.volces.com/api/v3`（那是 chat 那条线），
它在火山的「语音技术 / 豆包语音」产品线，端点在 `openspeech.bytedance.com`。

2026-09-17 实测（三发三中，别再来一遍）：

| 试探 | 结果 |
|---|---|
| `POST /api/v3/tts/unidirectional` + `X-Api-Key: ark-***` | 401 `45000010 Invalid X-Api-Key` |
| `POST /api/v3/plan/tts/unidirectional` + `X-Api-Key: ark-***` | 200 但内层 `call ark ... 401 AuthenticationError` |
| `POST ark.../api/v3/audio/speech` | 404（方舟没有这个端点） |
| `POST ark.../api/v3/chat/completions` + 同一把 key | **200 正常** → 说明 key 本身有效 |

结论：**方舟的 `ark-` key 做不了 TTS**。TTS 要另外一把凭据，两条线二选一：

① **语音技术控制台**（主流，走流式 HTTP Chunked）
   `POST https://openspeech.bytedance.com/api/v3/tts/unidirectional`
   头：`X-Api-Key: <语音技术控制台的 API Key>` + `X-Api-Resource-Id: seed-tts-2.0`
   → 控制台：console.volcengine.com/speech → 开通「豆包语音合成大模型」→ 创建应用 → API Key

② **方舟 Agent Plan 专属 API Key**（走非流式一次返回）
   `POST https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional`
   头同上。需要订阅方舟 Agent Plan 拿「专属 API Key」，普通方舟 key 会被拒。

两条线的**请求体与响应体同构**，所以本模块一套代码通吃，只靠 `VOLC_TTS_ENDPOINT` 切。

──── 协议要点 ─────────────────────────────────────────────────────────

请求体：
    {"user": {"uid": "..."},
     "req_params": {"text": "...", "speaker": "zh_female_xxx_uranus_bigtts",
                    "audio_params": {"format": "mp3", "sample_rate": 24000,
                                     "speech_rate": -12}}}

响应体是**一串 JSON**（HTTP Chunked / 一行一个）：
    {"code": 0,        "message": "",   "data": "<base64 音频分片>"}   ← 拼起来
    {"code": 20000000, "message": "ok", "data": null}                  ← 结束标志
    {"code": <其它正数>, "message": "...", "data": null}                ← 出错

⚠️ 判结束必须先判 `20000000`：它 > 0，写成 `if code > 0: 出错` 会把正常结束当错误。

⚠️ 音频格式用 **mp3** 不用 wav：官方明确说「流式场景下传 wav 会多次返回 wav header」，
   拼出来的文件是坏的。mp3 浏览器 `<audio>` 直接能放，也省了自拼 WAV 头。

⚠️ 语速单位与 CosyVoice 不同：这里是 `speech_rate ∈ [-50, 100]`（100 = 2.0 倍速）。
   本模块对外仍收 `rate` 这个**倍率浮点**（0.5~2.0），在内部换算，免得上层到处改语义。
"""
import base64
import json
import os
import uuid

import requests
from loguru import logger

ENDPOINT_STREAM = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'
ENDPOINT_PLAN = 'https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional'

DEFAULT_RESOURCE = 'seed-tts-2.0'
DEFAULT_FORMAT = 'mp3'
DEFAULT_SAMPLE_RATE = 24000

# 语速倍率默认值。豆包 2.0 的 1.0 倍本身就是「自然口播」节奏（CosyVoice 那个 0.88
# 是为了把它从 302 字/分压到 254 字/分），所以这里不额外减速，要慢就自己调。
DEFAULT_RATE = 1.0

# 连接复用：官方明确说火山侧 keep-alive 是 1 分钟，别每次新建 TCP。
_session = requests.Session()


# 音色库（豆包语音合成模型 2.0，voice_type 即 speaker）。
# 全部为「2.0」音色 → 需要 X-Api-Resource-Id: seed-tts-2.0（计费商品「语音合成2.0字符版」）。
# 选录原则：优先「视频配音 / 通用场景」里能在带货短视频里直接用上的，
# 加上官方标注「剪映同款 / 抖音同款」的那几个（和爸爸现有工作流同源）。
VOICE_LIBRARY = [
    {"id": "zh_female_shuangkuaisisi_uranus_bigtts", "name": "爽快思思 2.0", "gender": "female",
     "desc": "干脆利落，带货口播",
     "tags": ["带货", "种草", "电商", "促销", "通用", "快节奏", "好物"]},
    {"id": "zh_female_vv_uranus_bigtts", "name": "Vivi 2.0", "gender": "female",
     "desc": "官方主打女声，多语种",
     "tags": ["通用", "品牌", "种草", "多语种", "官方"]},
    {"id": "zh_female_xiaohe_uranus_bigtts", "name": "小何 2.0", "gender": "female",
     "desc": "亲和自然女声",
     "tags": ["通用", "生活", "家居", "情感", "日常"]},
    {"id": "zh_female_wenrouxiaoya_uranus_bigtts", "name": "温柔小雅 2.0", "gender": "female",
     "desc": "温柔治愈女声",
     "tags": ["美妆", "护肤", "母婴", "情感", "治愈", "温馨", "舒缓"]},
    {"id": "zh_female_zhixingnv_uranus_bigtts", "name": "知性女声 2.0", "gender": "female",
     "desc": "知性稳重",
     "tags": ["知识", "干货", "职场", "教育", "讲解"]},
    {"id": "zh_female_qingxinnvsheng_uranus_bigtts", "name": "清新女声 2.0", "gender": "female",
     "desc": "清新干净",
     "tags": ["清新", "护肤", "食品", "日系"]},
    {"id": "zh_female_linjianvhai_uranus_bigtts", "name": "邻家女孩 2.0", "gender": "female",
     "desc": "亲切日常",
     "tags": ["生活", "日常", "好物", "分享"]},
    {"id": "zh_female_tianmeixiaoyuan_uranus_bigtts", "name": "甜美小源 2.0", "gender": "female",
     "desc": "甜美年轻",
     "tags": ["少女", "美妆", "零食", "可爱"]},
    {"id": "zh_female_gaolengyujie_uranus_bigtts", "name": "高冷御姐 2.0", "gender": "female",
     "desc": "高级感女声",
     "tags": ["高端", "轻奢", "大牌", "高级"]},
    {"id": "zh_male_m191_uranus_bigtts", "name": "云舟 2.0", "gender": "male",
     "desc": "官方主打男声",
     "tags": ["通用", "品牌", "科技", "商务", "官方"]},
    {"id": "zh_male_guanggaojieshuo_uranus_bigtts", "name": "广告解说 2.0", "gender": "male",
     "desc": "广告腔解说（剪映同款）",
     "tags": ["广告", "带货", "促销", "解说", "剪映同款", "TVC"]},
    {"id": "zh_male_cixingjieshuonan_uranus_bigtts", "name": "磁性解说男声 2.0", "gender": "male",
     "desc": "磁性解说（抖音同款）",
     "tags": ["解说", "测评", "数码", "抖音同款", "磁性"]},
    {"id": "zh_male_yangguangqingnian_uranus_bigtts", "name": "阳光青年 2.0", "gender": "male",
     "desc": "阳光活力",
     "tags": ["运动", "潮流", "年轻", "活力"]},
    {"id": "zh_male_qingcang_uranus_bigtts", "name": "擎苍 2.0", "gender": "male",
     "desc": "厚重叙述（番茄/抖音同款）",
     "tags": ["纪录片", "品牌故事", "旁白", "厚重", "番茄同款"]},
    {"id": "en_female_dacey_uranus_bigtts", "name": "Dacey", "gender": "female",
     "desc": "美式英语女声",
     "tags": ["英语", "英文", "海外"]},
    {"id": "en_male_tim_uranus_bigtts", "name": "Tim", "gender": "male",
     "desc": "美式英语男声",
     "tags": ["英语", "英文", "海外"]},
]

DEFAULT_VOICE = 'zh_female_shuangkuaisisi_uranus_bigtts'


class VolcTtsError(RuntimeError):
    """带 code / logid 的火山错误 —— 排查时要 logid。"""

    def __init__(self, message, code=None, logid=None):
        super(VolcTtsError, self).__init__(message)
        self.code = code
        self.logid = logid


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
def cfg():
    """读环境变量。凭据两种给法：新版单头 X-Api-Key，或旧版双头 AppId + AccessKey。"""
    return {
        'api_key': (os.environ.get('VOLC_TTS_API_KEY') or '').strip(),
        'app_id': (os.environ.get('VOLC_TTS_APP_ID') or '').strip(),
        'access_key': (os.environ.get('VOLC_TTS_ACCESS_TOKEN') or '').strip(),
        'resource_id': (os.environ.get('VOLC_TTS_RESOURCE_ID') or '').strip(),
        'endpoint': (os.environ.get('VOLC_TTS_ENDPOINT') or '').strip() or ENDPOINT_STREAM,
        'emotion': (os.environ.get('VOLC_TTS_EMOTION') or '').strip(),
        'uid': (os.environ.get('VOLC_TTS_UID') or 'xunjia-aiclip').strip(),
    }


def configured():
    """返回 (是否可调用, 缺什么)。"""
    c = cfg()
    if c['api_key']:
        return True, []
    if c['app_id'] and c['access_key']:
        return True, []
    missing = []
    if not c['app_id']:
        missing.append('VOLC_TTS_API_KEY（新版控制台，推荐）')
    else:
        missing.append('VOLC_TTS_ACCESS_TOKEN（旧版控制台，配了 App ID 就得配它）')
    return False, missing


def headers_for(voice_id=None):
    """鉴权头。`X-Api-Resource-Id` 必填 —— 漏了会被 403 挡回去（45000030）。"""
    c = cfg()
    resource = c['resource_id'] or _voice_resource(voice_id) or DEFAULT_RESOURCE
    h = {
        'Content-Type': 'application/json',
        'X-Api-Resource-Id': resource,
        'X-Api-Request-Id': str(uuid.uuid4()),
    }
    if c['app_id'] and c['access_key']:
        h['X-Api-App-Id'] = c['app_id']
        h['X-Api-Access-Key'] = c['access_key']
    else:
        h['X-Api-Key'] = c['api_key']
    return h


def _voice_resource(voice_id):
    for v in VOICE_LIBRARY:
        if v['id'] == voice_id:
            return v.get('resource')
    return None


def get_voice_library():
    return VOICE_LIBRARY


def voice_name(voice_id):
    for v in VOICE_LIBRARY:
        if v['id'] == voice_id:
            return v['name']
    return voice_id


def has_voice(voice_id):
    return any(v['id'] == voice_id for v in VOICE_LIBRARY)


def resolve_voice(style_tone='', script='', preferred=''):
    """按「品牌调性 + 文案关键词」挑音色。与 CosyVoice 那套同形，便于上层无感切换。"""
    if preferred and preferred not in ('', 'auto'):
        if has_voice(preferred):
            return {'id': preferred, 'name': voice_name(preferred)}
        for v in VOICE_LIBRARY:
            if v['name'] == preferred:
                return {'id': v['id'], 'name': v['name']}

    text = '{} {}'.format(style_tone or '', script or '')
    rules = [
        (['广告', '带货', '促销', '秒杀', '福利', '上链接', '好物'], 'zh_male_guanggaojieshuo_uranus_bigtts'),
        (['测评', '数码', '参数', '对比', '硬核', '拆解'], 'zh_male_cixingjieshuonan_uranus_bigtts'),
        (['高端', '轻奢', '大牌', '高级', '质感'], 'zh_female_gaolengyujie_uranus_bigtts'),
        (['美妆', '护肤', '母婴', '温柔', '治愈', '情感', '故事'], 'zh_female_wenrouxiaoya_uranus_bigtts'),
        (['知识', '干货', '教程', '职场', '教育', '科普'], 'zh_female_zhixingnv_uranus_bigtts'),
        (['纪录片', '品牌故事', '历程', '厚重', '旁白'], 'zh_male_qingcang_uranus_bigtts'),
        (['英文', '海外', '英语'], 'en_female_dacey_uranus_bigtts'),
    ]
    for keywords, vid in rules:
        if any(k in text for k in keywords):
            return {'id': vid, 'name': voice_name(vid)}
    return {'id': DEFAULT_VOICE, 'name': voice_name(DEFAULT_VOICE)}


# ---------------------------------------------------------------------------
# 语速换算：对外「倍率」→ 对内 speech_rate ∈ [-50, 100]
# ---------------------------------------------------------------------------
def to_speech_rate(rate):
    try:
        r = float(rate if rate not in (None, '') else DEFAULT_RATE)
    except (TypeError, ValueError):
        r = DEFAULT_RATE
    return max(-50, min(100, int(round((r - 1.0) * 100))))


def from_speech_rate(speech_rate):
    try:
        return round(1.0 + float(speech_rate) / 100.0, 3)
    except (TypeError, ValueError):
        return DEFAULT_RATE


# ---------------------------------------------------------------------------
# 错误码 → 人话
# ---------------------------------------------------------------------------
_HINTS = {
    45000010: '凭据无效或没配 —— 方舟的 ark- 开头的 key 不能用于语音合成，'
              '要用语音技术控制台的 API Key（console.volcengine.com/speech）。',
    45000000: '鉴权/授权失败 —— 常见原因：音色没在控制台的「音色管理」里开通，'
              '或者 Resource ID 与音色版本不匹配。',
    45000030: '请求没带 X-Api-Resource-Id（模型版本 ID）。',
    40402003: '文本超过单次合成长度上限 —— 回参考脚本把这一镜拆短。',
    55000000: '火山服务端错误，稍后重试。',
}


def friendly(code, message, logid=''):
    hint = _HINTS.get(code)
    body = message or ''
    parts = []
    if hint:
        parts.append(hint)
    if body:
        parts.append('火山原话：{}'.format(body[:200]))
    if code is not None:
        parts.append('code={}'.format(code))
    if logid:
        parts.append('logid={}'.format(logid))
    return ' ｜ '.join(parts) or '火山语音合成失败'


def _parse_obj(obj, logid):
    """拆一条响应。返回 (audio_b64 or None, done: bool)；出错直接抛。"""
    if not isinstance(obj, dict):
        return None, False
    # 错误响应会包一层 header：{"header": {"code": ..., "message": ...}}
    head = obj.get('header') if isinstance(obj.get('header'), dict) else obj
    code = head.get('code')
    if code in (None, 0):
        return obj.get('data') or None, False
    if code == 20000000:
        return None, True
    raise VolcTtsError(friendly(code, head.get('message'), logid), code, logid)


# ---------------------------------------------------------------------------
# 合成
# ---------------------------------------------------------------------------
def synthesize(text, output_path, voice=DEFAULT_VOICE, rate=DEFAULT_RATE):
    """文本 → 音频文件（默认 mp3）。返回落盘路径。"""
    text = (text or '').strip()
    if not text:
        raise ValueError('合成文本为空')

    ok, missing = configured()
    if not ok:
        raise VolcTtsError(
            '火山语音合成凭据没配：缺 {}。'
            '到 .env 里补上 VOLC_TTS_API_KEY（或 VOLC_TTS_APP_ID + VOLC_TTS_ACCESS_TOKEN）'
            '再重启 xunjia-web。'.format('、'.join(missing)), None, '')

    c = cfg()
    speaker = voice or DEFAULT_VOICE
    fmt = (os.path.splitext(output_path)[1] or '.' + DEFAULT_FORMAT).lstrip('.').lower()
    body = {
        'user': {'uid': c['uid']},
        'req_params': {
            'text': text,
            'speaker': speaker,
            'audio_params': {
                'format': fmt if fmt in ('mp3', 'ogg_opus', 'pcm', 'wav') else DEFAULT_FORMAT,
                'sample_rate': DEFAULT_SAMPLE_RATE,
                'speech_rate': to_speech_rate(rate),
            },
        },
    }
    if c['emotion']:
        body['req_params']['audio_params']['emotion'] = c['emotion']

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    logid = ''
    try:
        resp = _session.post(c['endpoint'], headers=headers_for(speaker), json=body,
                             stream=True, timeout=(15, 300))
    except requests.RequestException as e:
        raise VolcTtsError('连不上火山语音合成服务（{}）：{}'.format(c['endpoint'], e), None, '')

    logid = resp.headers.get('X-Tt-Logid') or resp.headers.get('x-tt-logid') or ''

    if resp.status_code != 200:
        raw = b''
        try:
            for chunk in resp.iter_content(4096):
                raw += chunk
                if len(raw) > 4096:
                    break
        except Exception:
            pass
        code, message = None, raw[:300].decode('utf-8', 'replace')
        try:
            code, message = _peek_error(raw)
        except Exception:
            pass
        resp.close()
        raise VolcTtsError(friendly(code, message, logid), code, logid)

    audio = bytearray()
    done = False
    pending = ''
    try:
        for raw_line in resp.iter_lines(decode_unicode=False):
            if raw_line is None:
                continue
            line = raw_line.decode('utf-8', 'replace').strip()
            if not line:
                continue
            if line.startswith('data:'):          # 兼容 SSE 形态
                line = line[5:].strip()
                if not line:
                    continue
            pending = (pending + line) if pending else line
            try:
                obj = json.loads(pending)
            except ValueError:
                # 跨行的 JSON 还没读完。攒到 2MB 还读不出来就是真坏了。
                if len(pending) > 2 * 1024 * 1024:
                    raise VolcTtsError('火山返回的数据解析不了（前 200 字：{}）'
                                       .format(pending[:200]), None, logid)
                continue
            pending = ''
            b64, done = _parse_obj(obj, logid)
            if b64:
                try:
                    audio.extend(base64.b64decode(b64))
                except Exception:
                    raise VolcTtsError('火山返回的音频分片不是合法 base64', None, logid)
            if done:
                break
    finally:
        resp.close()

    if not audio:
        raise VolcTtsError('火山返回了空音频（speaker={}，检查音色是否已授权）'
                           .format(speaker), None, logid)

    with open(output_path, 'wb') as f:
        f.write(bytes(audio))

    if os.path.getsize(output_path) == 0:
        raise VolcTtsError('写入的音频文件是空的', None, logid)

    logger.info('火山 TTS 完成: speaker={} speech_rate={} len={}字 {}KB -> {}'.format(
        speaker, to_speech_rate(rate), len(text), len(audio) // 1024, output_path))
    return output_path


def _peek_error(raw):
    """从错误响应体里抠 code / message（可能是单对象，也可能是 NDJSON 首行）。"""
    text = raw.decode('utf-8', 'replace').strip()
    for candidate in (text, text.split('\n')[0] if text else ''):
        candidate = candidate.strip()
        if not candidate.startswith('{'):
            continue
        try:
            obj = json.loads(candidate)
        except ValueError:
            continue
        head = obj.get('header') if isinstance(obj.get('header'), dict) else obj
        return head.get('code'), head.get('message')
    return None, text[:300]


def status():
    """给前端/自检用的配置状态。"""
    ok, missing = configured()
    c = cfg()
    return {
        'provider': 'volc',
        'label': '火山引擎 · 豆包语音合成大模型',
        'configured': ok,
        'missing': missing,
        'endpoint': c['endpoint'],
        'resource_id': c['resource_id'] or DEFAULT_RESOURCE,
        'auth': '旧版双头（X-Api-App-Id + X-Api-Access-Key）' if c['app_id'] else '新版单头（X-Api-Key）',
        'format': DEFAULT_FORMAT,
        'sample_rate': DEFAULT_SAMPLE_RATE,
        'emotion': c['emotion'] or None,
        'voice_count': len(VOICE_LIBRARY),
    }


if __name__ == '__main__':
    # 自检：python services/tts_volc.py  → 打印配置 + 试合成一句
    import sys
    s = status()
    print('provider  : {}'.format(s['label']))
    print('endpoint  : {}'.format(s['endpoint']))
    print('resource  : {}'.format(s['resource_id']))
    print('auth      : {}'.format(s['auth']))
    print('configured: {}'.format(s['configured']))
    if not s['configured']:
        print('missing   : {}'.format('、'.join(s['missing'])))
        sys.exit(2)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tts_selftest.mp3')
    try:
        synthesize('这是火山语音合成的一次自检。', out, voice=DEFAULT_VOICE, rate=DEFAULT_RATE)
        print('OK -> {}  ({} bytes)'.format(out, os.path.getsize(out)))
    except VolcTtsError as e:
        print('FAIL: {}'.format(e))
        sys.exit(1)
