# -*- coding: utf-8 -*-
"""AI 剪辑 · 素材理解（P2）。

目标产物 = **可供编排单元**（`materials.seg_desc` 里的 `units`）：
每个 unit 是「一段画面 + 落在这段时间里的台词 + 这段能胜任什么镜头」。
② 参考脚本的直接输入就是它 —— 剧本给一个镜（"特写产品包装"），
在这一层的 `usable_for` 里检索命中，② 就能把意图映射到素材。

════════════════════ 三条来自实测的硬结论（2026-09-17）════════════════════

① **"有声音"≠"有语音"**。实测 `用补充进去的食物供能.mp4` 有音轨，但
   `has_speech=false`（3D 动画配乐）。所以**不能用音轨存在性分流**，必须实测。

② **视频输入模式下拿不到逐句转写**。模型能听见（会正确判断有没有人说话、
   描述说话人语气），但 `segments[].speech` 恒为空。要逐字稿必须把音频
   单独抽出来走 `input_audio`。→ 所以流水线是**音画分离**的。

③ **模型感知不到 alpha 通道**。RGBA 图的透明区在它眼里是白底。
   "有没有 alpha""真实内容占多大"只能由 probe.py 实测，不能问模型。
   两层不可互相替代，必须都在。

════════════════════ 分流逻辑（按素材形态，不按声音）════════════════════

    视频 ──► 音轨体检（确定性，ffmpeg）──► 有实质音量？──► 抽音频 → ASR 逐句转写
          └─► 视觉理解（低码率代理 + 自适应 fps）      ← 有没有语音都要做
    图片 ──► 视觉理解（缩到长边 1600 以内再内联）

    units 切点以谁为骨架，由素材类型决定：
      · 口播型（有语音 且 画面段数很少）→ **以语音断句为骨架**（信息全在台词）
      · 视觉型（无语音 或 画面变化丰富）→ **以画面切点为骨架**
"""
import os
import re
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from loguru import logger

from services.aiclip import ark, paths, probe, store

# 流水线版本：prompt / 合并策略有实质改动时 +1，据此批量重跑
#   u1 → u2：口播素材（画面无分段）改为以语音断句为骨架（u1 会把 33 句压成 1 个单元）
#   u2 → u3：口播判定改看**语音覆盖率**而非画面段数（u2 会把整句台词挂到每个画面段上）
VER = 'u3'

FFMPEG = os.environ.get('FFMPEG_BIN', 'ffmpeg')
FFPROBE = os.environ.get('FFPROBE_BIN', 'ffprobe')

SILENCE_DB = -45.0        # 低于该峰值视为「没有实质音轨」
TARGET_FRAMES = 60        # 视觉理解的目标采样帧数（fps 由它和时长反推）
FPS_MIN, FPS_MAX = 0.2, 3.0
PROXY_MIN_MB = 15.0       # 超过此体积先做低码率代理再上传
ASR_CHUNK_SEC = 120.0     # 音频切片长度：太长会让模型给的绝对时间戳漂移
IMAGE_MAX_SIDE = 1600     # 送理解前图片长边上限（省 token，视觉理解不需要原尺寸）

_TS = re.compile(r'(\d+\.?\d*)')


# ---------------------------------------------------------------------------
# Prompt（这是核心资产，改这里要同时升 VER）
# ---------------------------------------------------------------------------
PROMPT_VISION = '''你是短视频二创素材分析员。下面这段素材将被用于混剪重组，
请把它拆解成**可编排单元**，供后续自动配镜使用。

严格输出以下 JSON（只输出 JSON，不要 markdown 代码块）：
{
  "summary": "一句话说清这段素材是什么内容",
  "kind": "从这几个里选：产品展示 / 真人出镜口播 / 真人演示 / 场景空镜 / 信息图 / 文字板 / 包装特写 / 其他",
  "modality": {
    "has_speech": true,
    "speech_desc": "说话人身份与语气，如'女声讲解，语速快，营销口吻'；没有则空",
    "has_music": true,
    "has_env_sound": true
  },
  "tags": ["3-8个短标签，描述这段素材能表达什么概念或卖点，如'产品开箱''成分表''使用前后对比'"],
  "segments": [
    {
      "start": 0.0,
      "end": 3.2,
      "visual": "这一段画面里具体看到什么（主体、动作、镜头运动、色调）",
      "speech": "",
      "usable_for": ["这段适合承担哪类镜头，如'开场钩子''卖点强调''产品特写''结尾号召'"]
    }
  ],
  "text_on_screen": "画面中出现的所有文字（硬字幕/贴纸/包装上的文案），逐字照抄；没有则空",
  "notes": "使用注意事项，如'开头2秒有某品牌瓶身露出''画面偏暗''带平台水印'；没有则空"
}

要求：
- segments 按画面变化切分，每段 1-6 秒；整段素材都要被覆盖，不要留空档
- start/end 单位是秒，保留 1 位小数
- 如果画面里完全没有人物说话，has_speech 必须为 false，**不要因为存在背景音乐就报 true**
- text_on_screen 必须逐字照抄，包括角标、贴纸、包装上的小字（这些会和成片字幕打架，必须记录）
- 静态图片请只输出 1 个 segment，start 和 end 都为 0
'''

PROMPT_ASR = '''你是语音转写员。请把这段音频**逐句**转写为文字。

严格输出以下 JSON（只输出 JSON，不要 markdown 代码块）：
{
  "has_speech": true,
  "language": "zh",
  "speech_desc": "说话人身份与语气，如'年轻女声，日常分享口吻'；没有说话则空",
  "has_music": false,
  "has_env_sound": false,
  "segments": [
    {"start": 0.0, "end": 3.5, "text": "这一句的逐字原文"}
  ],
  "full_text": "把 segments 里的 text 按顺序拼起来的完整文本"
}

要求：
- **必须逐句完整转写，不许总结、不许跳过、不许省略**，哪怕只是"嗯""对"这类语气词也要写
- 按自然断句切分，每句 1-8 秒
- start/end 单位是秒，保留 1 位小数，覆盖整段音频
- 如果整段音频确实没有任何人说话（只有音乐/环境音），has_speech 为 false 且 segments 为空数组
'''


def _now():
    return datetime.now().isoformat(timespec='seconds')


def _tmp(suffix):
    d = os.path.join(paths.store_root(), 'tmp')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, '{}{}'.format(uuid.uuid4().hex[:10], suffix))


def _rm(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _run(cmd, timeout=300):
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning('aiclip understand: 命令失败 {}: {}'.format(cmd[0], e))
        return None


def _f(v, default=0.0):
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 确定性前置：音轨体检 / 抽音频 / 代理 / fps
# ---------------------------------------------------------------------------
def audio_metrics(path):
    """ffmpeg volumedetect：判「有没有实质音轨」。故意不用模型 —— 这一步要可复现。"""
    out = {'has_track': False, 'max_db': None, 'mean_db': None, 'usable': False}
    info = probe._ffprobe(path)
    if info:
        out['has_track'] = any(
            s.get('codec_type') == 'audio' for s in (info.get('streams') or []))
    if not out['has_track']:
        return out
    r = _run([FFMPEG, '-v', 'info', '-i', path, '-af', 'volumedetect',
              '-f', 'null', os.devnull], timeout=180)
    if not r:
        return out
    err = r.stderr.decode('utf-8', 'replace')
    m = re.search(r'max_volume:\s*(-?\d+\.?\d*)', err)
    n = re.search(r'mean_volume:\s*(-?\d+\.?\d*)', err)
    if m:
        out['max_db'] = float(m.group(1))
    if n:
        out['mean_db'] = float(n.group(1))
    out['usable'] = bool(out['max_db'] is not None and out['max_db'] > SILENCE_DB)
    return out


def extract_audio(src, dst, start=None, dur=None):
    """抽音频（16k 单声道 mp3，ASR 够用且极小）。"""
    cmd = [FFMPEG, '-y', '-v', 'error']
    if start is not None:
        cmd += ['-ss', '{:.3f}'.format(start)]
    cmd += ['-i', src]
    if dur is not None:
        cmd += ['-t', '{:.3f}'.format(dur)]
    cmd += ['-vn', '-ar', '16000', '-ac', '1', '-c:a', 'libmp3lame', '-b:a', '48k', dst]
    r = _run(cmd, timeout=300)
    return bool(r and r.returncode == 0 and os.path.exists(dst)
                and os.path.getsize(dst) > 1024)


def make_proxy(src, dst, max_w=480):
    """低码率代理：理解不需要高清，原片 300MB 上传太慢。"""
    r = _run([FFMPEG, '-y', '-v', 'error', '-i', src,
              '-vf', 'scale={}:-2'.format(max_w),
              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '30',
              '-c:a', 'aac', '-b:a', '48k', '-ar', '16000', '-ac', '1', dst],
             timeout=900)
    return bool(r and r.returncode == 0 and os.path.exists(dst)
                and os.path.getsize(dst) > 1024)


def pick_fps(duration):
    """按时长反推采样帧率，让总帧数落在目标附近。"""
    if not duration or duration <= 0:
        return FPS_MAX
    fps = TARGET_FRAMES / float(duration)
    fps = max(FPS_MIN, min(FPS_MAX, fps))
    return round(fps, 2)


def _prepare_image(path):
    """图片送理解前缩到长边 IMAGE_MAX_SIDE，返回 (临时路径, 是否新建)。"""
    if probe.Image is None:
        return path, False
    try:
        with probe.Image.open(path) as im:
            w, h = im.size
            if max(w, h) <= IMAGE_MAX_SIDE:
                return path, False
            # Pillow 10+ 把重采样常量挪进 Image.Resampling，老别名在新版可能消失
            resampling = getattr(probe.Image, 'Resampling', probe.Image)
            # 模型看不到 alpha（透明区在它眼里是黑/白），统一贴白底再送，接近最终呈现
            im = im.convert('RGBA')
            flat = probe.Image.new('RGB', im.size, (255, 255, 255))
            flat.paste(im, mask=im.getchannel('A'))
            k = IMAGE_MAX_SIDE / float(max(w, h))
            flat = flat.resize((max(int(w * k), 1), max(int(h * k), 1)),
                               getattr(resampling, 'LANCZOS', 1))
            tmp = _tmp('.jpg')
            flat.save(tmp, 'JPEG', quality=88)
            return tmp, True
    except Exception as e:
        logger.warning('aiclip understand: 图片预处理失败 {}: {}'.format(path, e))
        return path, False


# ---------------------------------------------------------------------------
# 模型调用：语音 / 视觉
# ---------------------------------------------------------------------------
def understand_speech(media_path, duration, thinking=False):
    """音频 → 逐句转写。超长音频切片，各片独立转写后拼时间轴（防漂移累积）。"""
    if not duration or duration <= 0:
        duration = 0.0
    chunks = []
    if duration > ASR_CHUNK_SEC * 1.2:
        n = int(duration // ASR_CHUNK_SEC) + (1 if duration % ASR_CHUNK_SEC else 0)
        for i in range(n):
            s = i * ASR_CHUNK_SEC
            d = min(ASR_CHUNK_SEC, duration - s)
            if d < 3:
                continue
            chunks.append((s, d))
    else:
        chunks.append((0.0, duration or None))

    merged = {'has_speech': False, 'language': '', 'speech_desc': '',
              'has_music': False, 'has_env_sound': False,
              'segments': [], 'full_text': '', 'chunks': []}
    usages = []
    tmp_audio = _tmp('.mp3')
    src = media_path
    try:
        for idx, (start, dur) in enumerate(chunks):
            if start == 0.0 and dur is None:
                ok = extract_audio(src, tmp_audio)
            else:
                ok = extract_audio(src, tmp_audio, start=start, dur=dur)
            if not ok:
                merged['chunks'].append({'start': start, 'error': '抽音频失败'})
                continue
            try:
                blocks = [
                    {'type': 'input_audio', 'audio_url': ark.data_uri(tmp_audio, 'audio/mpeg')},
                    {'type': 'input_text', 'text': PROMPT_ASR},
                ]
            except ValueError as e:
                merged['chunks'].append({'start': start, 'error': str(e)})
                continue
            data, usage, raw, err = ark.call(
                blocks, thinking=thinking, tag='asr#{}'.format(idx))
            usages.append(usage)
            if err or not isinstance(data, dict):
                merged['chunks'].append({'start': start, 'error': err or '空返回'})
                continue
            segs = data.get('segments') or []
            raw_end = max([_f(s.get('end')) for s in segs] or [0.0])
            real = dur if dur else duration
            # 模型给的绝对秒数会漂移（实测 30s 音频报到 36.2s）→ 按实测时长等比校正
            k = (real / raw_end) if (raw_end and real and abs(raw_end - real) > 0.5) else 1.0
            fixed = []
            for s in segs:
                text = (s.get('text') or '').strip()
                if not text:
                    continue
                fixed.append({
                    'start': round(start + _f(s.get('start')) * k, 1),
                    'end': round(start + _f(s.get('end')) * k, 1),
                    'text': text,
                })
            merged['chunks'].append({
                'start': start, 'dur': real, 'count': len(fixed),
                'raw_end': raw_end, 'scale': round(k, 4)})
            if fixed:
                merged['segments'].extend(fixed)
                merged['has_speech'] = True
                if data.get('language'):
                    merged['language'] = data['language']
                if data.get('speech_desc'):
                    merged['speech_desc'] = data['speech_desc']
            merged['has_music'] = merged['has_music'] or bool(data.get('has_music'))
            merged['has_env_sound'] = merged['has_env_sound'] or bool(data.get('has_env_sound'))
    finally:
        _rm(tmp_audio)
    merged['segments'].sort(key=lambda x: x['start'])
    merged['full_text'] = ''.join(s['text'] for s in merged['segments'])
    merged['usage'] = _sum_usage(usages)
    return merged


def understand_visual_media(path, duration, kind, thinking=False):
    """视频 → 画面分段。走低码率代理 + 服务端抽帧。"""
    src = path
    proxy = None
    size_mb = os.path.getsize(path) / 1048576.0
    if size_mb > PROXY_MIN_MB:
        proxy = _tmp('.mp4')
        if make_proxy(path, proxy):
            src = proxy
            logger.info('aiclip understand: 代理 {:.1f}MB -> {:.1f}MB'.format(
                size_mb, os.path.getsize(proxy) / 1048576.0))
        else:
            _rm(proxy)
            proxy = None
    fps = pick_fps(duration)
    file_id = None
    usages = []
    try:
        file_id = ark.upload_video(src, fps)
        # fps 只在上传时通过 preprocess_configs 生效（实测路径），content block 里不重复传
        blocks = [
            {'type': 'input_video', 'file_id': file_id},
            {'type': 'input_text', 'text': PROMPT_VISION},
        ]
        data, usage, raw, err = ark.call(blocks, thinking=thinking, tag='vision#video')
        usages.append(usage)
        if err or not isinstance(data, dict):
            return None, _sum_usage(usages), err or '空返回'
        data['_fps'] = fps
        data['_sampled_frames'] = int(duration * fps) if duration else 0
        return data, _sum_usage(usages), None
    finally:
        ark.delete_file(file_id)
        if proxy:
            _rm(proxy)


def understand_image_visual(path):
    """图片 → 单段描述 + OCR。"""
    src, created = _prepare_image(path)
    try:
        blocks = [
            {'type': 'input_image', 'image_url': ark.data_uri(src)},
            {'type': 'input_text', 'text': PROMPT_VISION},
        ]
        data, usage, raw, err = ark.call(blocks, thinking=False, tag='vision#image')
        if err or not isinstance(data, dict):
            return None, usage, err or '空返回'
        return data, usage, None
    finally:
        if created:
            _rm(src)


def _sum_usage(usages):
    """汇总开销。注意 calls 是**累加**（ASR 会分片多次调用）而不是列表长度。"""
    out = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0,
           'reasoning_tokens': 0, 'seconds': 0.0, 'model': ark.MODEL}
    for u in usages:
        if not u:
            continue
        for k in ('input_tokens', 'output_tokens', 'reasoning_tokens'):
            out[k] += int(u.get(k) or 0)
        out['calls'] += int(u.get('calls') or 1)
        out['seconds'] = round(out['seconds'] + float(u.get('seconds') or 0), 1)
    return out


# ---------------------------------------------------------------------------
# 合并：画面段 + 语音段 → 可编排单元 units
# ---------------------------------------------------------------------------
def _overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


# 从 kind 推默认可编排意图（视觉理解没给 usable_for 时兜底）
_KIND_DEFAULTS = (
    ('真人出镜口播', ['出镜讲解', '口播段落']),
    ('真人演示', ['演示过程', '操作展示']),
    ('产品展示', ['产品特写', '卖点展示']),
    ('包装特写', ['产品特写', '细节展示']),
    ('场景空镜', ['氛围铺垫', '转场过渡']),
    ('信息图', ['知识点注解', '原理演示']),
    ('文字板', ['信息强调', '标题卡']),
)


def _kind_defaults(kind):
    for key, vals in _KIND_DEFAULTS:
        if key in (kind or ''):
            return list(vals)
    return []


def _visual_for(vsegs, start, end):
    """取与 [start,end] 重叠最多的画面段的描述。"""
    best, score = None, 0.0
    for v in vsegs:
        ov = _overlap(start, end, _f(v.get('start')), _f(v.get('end')) or end)
        if ov > score:
            best, score = v, ov
    if best:
        return best.get('visual') or ''
    return vsegs[0].get('visual', '') if vsegs else ''


def _usable_for(vsegs, start, end):
    best, score = None, 0.0
    for v in vsegs:
        ov = _overlap(start, end, _f(v.get('start')), _f(v.get('end')) or end)
        if ov > score:
            best, score = v, ov
    return (best or {}).get('usable_for') or []


def _speech_between(ssegs, start, end):
    parts = []
    for s in ssegs:
        if _overlap(start, end, _f(s.get('start')), _f(s.get('end'))) > 0.05:
            t = (s.get('text') or '').strip()
            if t:
                parts.append(t)
    return ''.join(parts)


def merge_units(vdata, sdata, duration, kind=''):
    """★ 关键的切点决策：口播型以语音断句为骨架，视觉型以画面切点为骨架。"""
    vsegs = [v for v in ((vdata or {}).get('segments') or []) if isinstance(v, dict)]
    ssegs = [s for s in ((sdata or {}).get('segments') or []) if isinstance(s, dict)]
    has_speech = bool(sdata and sdata.get('has_speech') and ssegs)

    if not vsegs and not ssegs:
        return []
    summary = (vdata or {}).get('summary') or ''
    # ★ 画面**没有**分段信息 —— 口播素材的常态（固定机位，整段就是一个镜）。
    #   这时必须以语音断句为骨架：否则 33 句台词会被压成 1 个单元（实测踩过）。
    #   信息全在台词里，画面描述退化为整体 summary。
    if not vsegs:
        if ssegs:
            return [{
                'start': _f(s.get('start')), 'end': _f(s.get('end')),
                'visual': summary,
                'speech': (s.get('text') or '').strip(),
                'usable_for': _kind_defaults(kind),
            } for s in ssegs]
        return [{
            'start': 0.0, 'end': round(duration, 1) if duration else 0.0,
            'visual': summary, 'speech': '',
            'usable_for': _kind_defaults(kind),
        }]

    # ★ 口播判定：**看语音覆盖率，不看画面段数**。
    #   实测教训（u2）：246s 口播源片被视觉切成 59 段（每 4.2s，其实只是手势在动），
    #   而 ASR 给 24 句（每 10.3s，因为口播连续无停顿）→ 按段数判会误走视觉骨架，
    #   于是一个 4s 的画面段被挂上整句 10s 台词，同一段台词在多个 unit 里重复。
    #   覆盖率才是本质：说话几乎占满整条时间轴 → 台词是天然的信息单元，以它切。
    speech_span = sum(max(0.0, _f(s.get('end')) - _f(s.get('start'))) for s in ssegs)
    coverage = (speech_span / float(duration)) if duration else 0.0
    talky = has_speech and (coverage >= 0.6 or len(vsegs) <= max(2, len(ssegs) // 4))

    units = []
    if talky:
        for s in ssegs:
            st, en = _f(s.get('start')), _f(s.get('end'))
            units.append({
                'start': st, 'end': en,
                'visual': _visual_for(vsegs, st, en),
                'speech': (s.get('text') or '').strip(),
                'usable_for': _usable_for(vsegs, st, en),
            })
    else:
        for v in vsegs:
            st, en = _f(v.get('start')), _f(v.get('end'))
            if en <= st:
                en = min(st + 3.0, duration) if duration else st + 3.0
            units.append({
                'start': st, 'end': round(en, 1),
                'visual': (v.get('visual') or '').strip(),
                'speech': _speech_between(ssegs, st, en),
                'usable_for': [str(x) for x in (v.get('usable_for') or [])],
            })
    # 单段素材（无任何切点信息）兜底
    if len(units) == 1 and not units[0]['usable_for']:
        units[0]['usable_for'] = []
    return units


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def understand_material(material_id, force=False):
    """理解一条素材并落库。返回 (row, error)。"""
    row = store.fetch_by_id('materials', material_id)
    if not row:
        return None, '素材不存在'
    if (not force) and row.get('classify_status') == 'done' \
            and row.get('understand_ver') == VER:
        return row, None

    sha1 = row.get('sha1')
    src = paths.find_asset(sha1) if sha1 else None
    if not src:
        store.update('materials', material_id, {
            'classify_status': 'failed',
            'understand_error': '磁盘上找不到素材文件',
            'updated_at': _now()})
        return store.fetch_by_id('materials', material_id), '磁盘上找不到素材文件'

    if not ark.available():
        store.update('materials', material_id, {
            'classify_status': 'failed',
            'understand_error': '未配置 ARK_API_KEY',
            'updated_at': _now()})
        return store.fetch_by_id('materials', material_id), '未配置 ARK_API_KEY'

    store.update('materials', material_id, {
        'classify_status': 'running',
        'understand_error': None,
        # 重跑 = 重新问模型，结果回到「模型原文」状态，人工校对标记必须一起清掉。
        # 不清的后果有两个：前端会把模型原文标成「已人工校对」（骗人），
        # 且 reprobe 的保护逻辑会以为这版转写是人工改过的（见 materials.reprobe）。
        'understand_edited_at': None,
        'understand_edited_by': None,
        'updated_at': _now()})

    kind = row.get('type') or 'image'
    media = row.get('media') or {}
    duration = float(media.get('duration')
                     or store_row_float(row, 'duration') or 0)
    usages = []
    vdata = sdata = None
    err = None
    am = {'has_track': False, 'usable': False, 'max_db': None, 'mean_db': None}

    try:
        if kind == 'video':
            am = audio_metrics(src)
            if am['usable']:
                sdata = understand_speech(src, duration)
                usages.append(sdata.get('usage'))
            else:
                sdata = {'has_speech': False, 'segments': [], 'full_text': '',
                         'reason': '音轨低于 {:.0f}dB 或无音轨'.format(SILENCE_DB),
                         'audio_metrics': am}
            vdata, vu, verr = understand_visual_media(src, duration, kind)
            usages.append(vu)
            if verr and not vdata:
                err = '视觉理解失败: {}'.format(verr)
        else:
            vdata, vu, verr = understand_image_visual(src)
            usages.append(vu)
            if verr and not vdata:
                err = '视觉理解失败: {}'.format(verr)
            sdata = {'has_speech': False, 'segments': [], 'full_text': ''}

        if err:
            store.update('materials', material_id, {
                'classify_status': 'failed',
                'understand_error': err[:500],
                'understand_cost': _sum_usage([u for u in usages if u]),
                'updated_at': _now()})
            return store.fetch_by_id('materials', material_id), err

        vdata = vdata or {}
        units = merge_units(vdata, sdata, duration, vdata.get('kind', ''))
        mod = vdata.get('modality') or {}
        # 音轨体检的确定性结论优先于模型判断（模型只听，我们测过 dB）
        if kind == 'video' and not am['usable']:
            mod['has_speech'] = False
        tags = {
            'list': [str(t) for t in (vdata.get('tags') or [])][:12],
            'summary': vdata.get('summary') or '',
            'modality': {
                'has_speech': bool(mod.get('has_speech') or (sdata or {}).get('has_speech')),
                'speech_desc': mod.get('speech_desc') or (sdata or {}).get('speech_desc') or '',
                'has_music': bool(mod.get('has_music')),
                'has_env_sound': bool(mod.get('has_env_sound')),
                'audio_metrics': am if kind == 'video' else None,
            },
            'text_on_screen': vdata.get('text_on_screen') or '',
            'notes': vdata.get('notes') or '',
            'unit_count': len(units),
        }
        speech = {
            'has_speech': bool((sdata or {}).get('has_speech')),
            'language': (sdata or {}).get('language') or '',
            'speech_desc': (sdata or {}).get('speech_desc') or '',
            'segments': (sdata or {}).get('segments') or [],
            'full_text': (sdata or {}).get('full_text') or '',
            'chunks': (sdata or {}).get('chunks') or [],
        }
        cost = _sum_usage([u for u in usages if u])
        store.update('materials', material_id, {
            'ai_classify': (vdata.get('kind') or '')[:64] or None,
            'classify_status': 'done',
            'tags': tags,
            'speech': speech,
            'seg_desc': units,
            'understand_at': _now(),
            'understand_error': None,
            'understand_ver': VER,
            'understand_cost': cost,
            'updated_at': _now(),
        })
        logger.info('aiclip understand: {} 完成 kind={} units={} speech={} ({:.1f}s)'.format(
            row.get('name'), vdata.get('kind'), len(units), speech['has_speech'],
            cost.get('seconds', 0)))
        return store.fetch_by_id('materials', material_id), None
    except Exception as e:
        logger.exception('aiclip understand: 理解异常 {}'.format(material_id))
        store.update('materials', material_id, {
            'classify_status': 'failed',
            'understand_error': str(e)[:500],
            'updated_at': _now()})
        return store.fetch_by_id('materials', material_id), str(e)


def store_row_float(row, key):
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def understand_batch(material_ids, concurrency=3, force=False, on_progress=None):
    """批量理解。返回 {total, done, failed, skipped, errors, cost}。"""
    ids = [i for i in (material_ids or []) if i]
    out = {'total': len(ids), 'done': 0, 'failed': 0, 'skipped': 0,
           'errors': [], 'cost': {'input_tokens': 0, 'output_tokens': 0,
                                  'seconds': 0.0, 'calls': 0}}
    if not ids:
        return out
    workers = max(1, min(int(concurrency or 1), 4))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(understand_material, mid, force): mid for mid in ids}
        for fu in as_completed(futs):
            mid = futs[fu]
            try:
                row, err = fu.result()
            except Exception as e:
                row, err = None, str(e)
            if err:
                out['failed'] += 1
                out['errors'].append({'id': mid, 'error': err})
            elif row and row.get('classify_status') == 'done':
                out['done'] += 1
            else:
                out['skipped'] += 1
            cost = (row or {}).get('understand_cost') or {}
            for k in ('input_tokens', 'output_tokens', 'calls'):
                out['cost'][k] += int(cost.get(k) or 0)
            out['cost']['seconds'] = round(
                out['cost']['seconds'] + float(cost.get('seconds') or 0), 1)
            if on_progress:
                try:
                    on_progress(out)
                except Exception:
                    pass
    return out
