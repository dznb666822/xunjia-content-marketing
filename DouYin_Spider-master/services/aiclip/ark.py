# -*- coding: utf-8 -*-
"""AI 剪辑 · 火山方舟全模态调用层。

只用三个能力，都是实测验证过的（2026-09-17）：

    input_image  + base64 data URI   →  画面描述 / OCR / 语义标签
    input_video  + file_id           →  音画分段 / 屏幕文字 / 意图
    input_audio  + base64 data URI   →  逐句转写 + 时间戳   ← 视频输入**不给**转写原文

⚠️ 一条实测结论：**视频输入模式下模型能听见声音（会正确判断有没有人说话），
但不会输出逐句转写**。要拿逐字稿必须把音频单独抽出来走 input_audio。
所以理解流水线是"音画分离"的，见 understand.py。

另一条：多模态模型**感知不到 alpha 通道** —— RGBA 图的透明区在它眼里是白底/黑底。
所以"有没有 alpha""真实内容占多大"这类几何事实只能由 probe.py 实测，不能问模型。
"""
import base64
import json
import mimetypes
import os
import time

from loguru import logger

MODEL = os.environ.get('AICLIP_VLM_MODEL', 'doubao-seed-2-0-lite-260428')
BASE_URL = os.environ.get('AI_API_URL', 'https://ark.cn-beijing.volces.com/api/v3')
DEFAULT_TIMEOUT = float(os.environ.get('AICLIP_VLM_TIMEOUT', '300'))

# 方舟对单文件的限制（保守取值，超了先压缩再传）
MAX_INLINE_MB = 24.0


def api_key():
    return (os.environ.get('ARK_API_KEY')
            or os.environ.get('AI_API_KEY')
            or '').strip()


def available():
    return bool(api_key())


def client(timeout=None):
    from volcenginesdkarkruntime import Ark
    return Ark(base_url=BASE_URL, api_key=api_key(),
               timeout=timeout or DEFAULT_TIMEOUT, max_retries=2)


# ---------------------------------------------------------------------------
# 内联编码
# ---------------------------------------------------------------------------
def data_uri(path, default_mime=None):
    """文件 → data URI（base64 内联，省一次上传+预处理往返）。"""
    size_mb = os.path.getsize(path) / 1048576.0
    if size_mb > MAX_INLINE_MB:
        raise ValueError('文件 {:.1f}MB 超过内联上限 {:.0f}MB'.format(size_mb, MAX_INLINE_MB))
    mime = mimetypes.guess_type(path)[0] or default_mime or 'application/octet-stream'
    with open(path, 'rb') as f:
        return 'data:{};base64,{}'.format(mime, base64.b64encode(f.read()).decode())


# ---------------------------------------------------------------------------
# 响应解析
# ---------------------------------------------------------------------------
def extract_text(resp):
    """从 responses.create 的返回里取出全部文本块。"""
    out = ''
    for item in getattr(resp, 'output', None) or []:
        for block in getattr(item, 'content', None) or []:
            t = getattr(block, 'text', None)
            if t:
                out += t
    if not out:
        out = str(resp)
    return out


def parse_json(raw):
    """容错解析模型输出：剥 markdown 围栏 → 截取最外层花括号/方括号 → loads。"""
    txt = (raw or '').strip()
    if txt.startswith('```'):
        lines = txt.split('\n')[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        txt = '\n'.join(lines).strip()
    try:
        return json.loads(txt)
    except ValueError:
        pass
    # 模型在 JSON 前后夹了解释文字：截取最外层
    for opener, closer in (('{', '}'), ('[', ']')):
        i, j = txt.find(opener), txt.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(txt[i:j + 1])
            except ValueError:
                continue
    raise ValueError('无法从模型输出解析 JSON: {}'.format(txt[:200]))


def usage_of(resp):
    u = getattr(resp, 'usage', None)
    if not u:
        return {}
    get = (lambda k: getattr(u, k, None)) if not isinstance(u, dict) else u.get
    details = get('output_tokens_details')
    reasoning = None
    if details is not None:
        reasoning = (getattr(details, 'reasoning_tokens', None)
                     if not isinstance(details, dict) else details.get('reasoning_tokens'))
    return {
        'calls': 1,
        'input_tokens': get('input_tokens'),
        'output_tokens': get('output_tokens'),
        'reasoning_tokens': reasoning,
        'total_tokens': get('total_tokens'),
    }


# ---------------------------------------------------------------------------
# 调用
# ---------------------------------------------------------------------------
def call(blocks, want_json=True, timeout=None, thinking=None, tag=''):
    """统一的 responses.create 调用。

    blocks       content 数组（媒体块 + 文本块）
    want_json    True 时解析 JSON，失败返回 (None, ...) 并把原文放进 raw
    thinking     None=服务端默认；False=显式关闭思考（快很多，质量需实测）
    返回 (data_or_None, usage_dict, raw_text, error_or_None)
    """
    if not available():
        return None, {}, '', '未配置 ARK_API_KEY'
    kwargs = {}
    if thinking is False:
        kwargs['thinking'] = {'type': 'disabled'}
    t0 = time.time()
    try:
        cli = client(timeout)
        try:
            resp = cli.responses.create(
                model=MODEL,
                input=[{'role': 'user', 'content': blocks}],
                **kwargs)
        except TypeError:
            # SDK/服务端不接受 thinking 参数时退回默认
            resp = cli.responses.create(
                model=MODEL, input=[{'role': 'user', 'content': blocks}])
        raw = extract_text(resp)
        usage = usage_of(resp)
        usage['seconds'] = round(time.time() - t0, 1)
        usage['model'] = MODEL
        if tag:
            usage['tag'] = tag
        if not want_json:
            return raw, usage, raw, None
        try:
            return parse_json(raw), usage, raw, None
        except ValueError as e:
            logger.warning('aiclip ark: JSON 解析失败 ({}): {}'.format(tag, e))
            return None, usage, raw, 'JSON 解析失败'
    except Exception as e:
        logger.error('aiclip ark: 调用失败 ({}): {}'.format(tag, e))
        return None, {'seconds': round(time.time() - t0, 1), 'model': MODEL}, '', str(e)


# ---------------------------------------------------------------------------
# 上传视频（长素材走这条，服务端抽帧）
# ---------------------------------------------------------------------------
def upload_video(path, fps, timeout=None):
    """上传视频并等预处理。返回 file_id。用完务必 delete_file。"""
    cli = client(timeout)
    with open(path, 'rb') as fo:
        f = cli.files.create(
            file=fo, purpose='user_data',
            preprocess_configs={'video': {'fps': float(fps)}})
    cli.files.wait_for_processing(f.id)
    return f.id


def delete_file(file_id):
    if not file_id:
        return
    try:
        client().files.delete(file_id)
    except Exception as e:
        logger.warning('aiclip ark: 删除方舟文件失败 {}: {}'.format(file_id, e))
