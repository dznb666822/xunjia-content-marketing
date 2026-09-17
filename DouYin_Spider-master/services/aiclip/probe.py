# -*- coding: utf-8 -*-
"""AI 剪辑 · 素材体检（确定性，零 LLM）。

体检出的硬数据是后面所有编排的前提：**时长 / 有没有语音 / 真实内容是多大**
—— 这三样必须是实测，不许猜。

    sha1_file()    内容指纹（稳定 asset_id + 天然去重）
    probe_image()  几何：画幅、是否有 alpha、内容 bbox、content_ratio
    probe_video()  媒体：fps / 时长 / 码率 / 编码 / 旋转 / 有无音轨
    probe()        统一入口（视频再抽一帧跑几何体检，能查出黑边）
    make_thumb()   缩略图（图 → PIL，视频 → ffmpeg 抽帧）

content_ratio 的意义：`坚果_cut.png` 文件是 235×420，但真实内容只有 97×168
（外面全是透明边），直接按画幅摆位就会「看起来很小、还偏」。体检把它量出来，
P3 编译期按落位档（A/B 带内 840px / C 全屏 1080px）现算裁切。
"""
import hashlib
import json
import os
import subprocess
import tempfile

from loguru import logger

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover
    Image = None
    ImageChops = None

FFPROBE = os.environ.get('FFPROBE_BIN', 'ffprobe')
FFMPEG = os.environ.get('FFMPEG_BIN', 'ffmpeg')

ALPHA_THRESHOLD = 12   # alpha 低于该值视为透明（抗锯齿边缘）
COLOR_THRESHOLD = 16   # 与背景色差异低于该值视为背景
THUMB_MAX = 420


# ---------------------------------------------------------------------------
# 指纹
# ---------------------------------------------------------------------------
def sha1_file(path, chunk=1024 * 1024):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 图片几何体检
# ---------------------------------------------------------------------------
def _dominant_corner_color(rgb, w, h):
    """取四角像素中出现次数最多的那个当背景色（去掉全透明图的干扰）。"""
    px = rgb.load()
    pts = [(0, 0), (max(w - 1, 0), 0), (0, max(h - 1, 0)),
           (max(w - 1, 0), max(h - 1, 0))]
    votes = {}
    for p in pts:
        c = px[p]
        if isinstance(c, int):  # 'L' 模式
            c = (c, c, c)
        key = tuple(int(v) // 8 * 8 for v in c[:3])
        votes[key] = votes.get(key, 0) + 1
    return max(votes.items(), key=lambda kv: kv[1])[0]


def probe_image(path):
    """返回 geom dict；PIL 不可用或读不开时返回 None。"""
    if Image is None:
        return None
    try:
        with Image.open(path) as im:
            w, h = im.size
            has_alpha = (im.mode in ('RGBA', 'LA')
                         or (im.mode == 'P' and 'transparency' in im.info))
            bbox = None
            bg = None
            if has_alpha:
                alpha = im.convert('RGBA').getchannel('A')
                alpha = alpha.point(lambda v: 255 if v > ALPHA_THRESHOLD else 0)
                bbox = alpha.getbbox()
            else:
                rgb = im.convert('RGB')
                bg = _dominant_corner_color(rgb, w, h)
                flat = Image.new('RGB', (w, h), tuple(bg))
                diff = ImageChops.difference(rgb, flat).convert('L')
                mask = diff.point(lambda v: 255 if v > COLOR_THRESHOLD else 0)
                bbox = mask.getbbox()
            if not bbox:
                bbox = (0, 0, w, h)
            cw = max(bbox[2] - bbox[0], 0)
            ch = max(bbox[3] - bbox[1], 0)
            ratio = round((cw * ch) / float(w * h), 6) if w and h else 1.0
            return {
                'w': w,
                'h': h,
                'has_alpha': bool(has_alpha),
                'bbox_px': [bbox[0], bbox[1], bbox[2], bbox[3]],
                'bbox': [round(bbox[0] / w, 6), round(bbox[1] / h, 6),
                         round(cw / w, 6), round(ch / h, 6)] if w and h else [],
                'content_ratio': ratio,
                'bg': list(bg) if bg else None,
            }
    except Exception as e:
        logger.warning('图片体检失败 {}: {}'.format(path, e))
        return None


# ---------------------------------------------------------------------------
# 视频媒体体检
# ---------------------------------------------------------------------------
def _ratio_to_float(s):
    if not s:
        return None
    try:
        if '/' in s:
            a, b = s.split('/')
            b = float(b)
            return round(float(a) / b, 4) if b else None
        return round(float(s), 4)
    except (ValueError, ZeroDivisionError):
        return None


def _ffprobe(path):
    cmd = [FFPROBE, '-v', 'error', '-print_format', 'json',
           '-show_format', '-show_streams', path]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60)
        if out.returncode != 0:
            logger.warning('ffprobe 失败 {}: {}'.format(
                path, out.stderr.decode('utf-8', 'replace')[:200]))
            return None
        return json.loads(out.stdout.decode('utf-8', 'replace') or '{}')
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        logger.warning('ffprobe 异常 {}: {}'.format(path, e))
        return None


def probe_video(path):
    """返回 (media, geom_or_None)。"""
    info = _ffprobe(path)
    if not info:
        return None, None
    streams = info.get('streams') or []
    fmt = info.get('format') or {}
    v = next((s for s in streams if s.get('codec_type') == 'video'), None)
    a = next((s for s in streams if s.get('codec_type') == 'audio'), None)

    fps = None
    rotation = 0
    w = h = None
    if v:
        fps = _ratio_to_float(v.get('avg_frame_rate')) or _ratio_to_float(v.get('r_frame_rate'))
        w, h = v.get('width'), v.get('height')
        tags = v.get('tags') or {}
        try:
            rotation = int(float(tags.get('rotate', 0)))
        except (TypeError, ValueError):
            rotation = 0
        for sd in (v.get('side_data_list') or []):
            if 'rotation' in sd:
                try:
                    rotation = int(float(sd['rotation']))
                except (TypeError, ValueError):
                    pass

    duration = None
    try:
        duration = round(float(fmt.get('duration')), 3)
    except (TypeError, ValueError):
        if v and v.get('duration'):
            try:
                duration = round(float(v['duration']), 3)
            except (TypeError, ValueError):
                pass
    bitrate = None
    try:
        bitrate = int(fmt.get('bit_rate'))
    except (TypeError, ValueError):
        pass

    media = {
        'fps': fps,
        'duration': duration,
        'bitrate': bitrate,
        'codec': (v or {}).get('codec_name'),
        'width': w,
        'height': h,
        'rotation': rotation,
        'has_audio': bool(a),
        'audio_codec': (a or {}).get('codec_name'),
        'format': fmt.get('format_name'),
    }

    # 抽一帧跑几何体检：能查出黑边 / 白边（竖屏填充时的常见坑）
    geom = None
    if duration and duration > 0.2:
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(suffix='.jpg')
            os.close(fd)
            ts = max(min(duration * 0.1, 5.0), 0.0)
            cmd = [FFMPEG, '-y', '-v', 'error', '-ss', '{:.3f}'.format(ts),
                   '-i', path, '-frames:v', '1', '-vf', 'scale=480:-2', tmp]
            out = subprocess.run(cmd, capture_output=True, timeout=90)
            if out.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                geom = probe_image(tmp)
                if geom:
                    geom['sampled_at'] = round(ts, 3)
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning('抽帧失败 {}: {}'.format(path, e))
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    return media, geom


def probe(path, kind):
    """统一入口。返回 dict(geom, media, duration)。"""
    res = {'geom': None, 'media': None, 'duration': 0.0}
    if kind == 'video':
        media, geom = probe_video(path)
        res['media'] = media
        res['geom'] = geom
        if media and media.get('duration'):
            res['duration'] = float(media['duration'])
    elif kind == 'image':
        res['geom'] = probe_image(path)
    return res


# ---------------------------------------------------------------------------
# 缩略图
# ---------------------------------------------------------------------------
def make_thumb(src, kind, dst):
    """生成缩略图，成功返回 True。"""
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
    except OSError:
        pass
    if kind == 'video':
        cmd = [FFMPEG, '-y', '-v', 'error', '-ss', '0.5', '-i', src,
               '-frames:v', '1', '-vf', 'scale={}:-2'.format(THUMB_MAX), dst]
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=90)
            return out.returncode == 0 and os.path.exists(dst)
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning('视频缩略图失败 {}: {}'.format(src, e))
            return False
    if Image is None:
        return False
    try:
        with Image.open(src) as im:
            im = im.convert('RGBA')
            im.thumbnail((THUMB_MAX, THUMB_MAX))
            bg = Image.new('RGB', im.size, (241, 245, 249))
            bg.paste(im, mask=im.getchannel('A'))
            bg.save(dst, 'JPEG', quality=86)
        return True
    except Exception as e:
        logger.warning('图片缩略图失败 {}: {}'.format(src, e))
        return False


def speech_probe(media):
    """语音段落的占位（P1）。

    P1 只给「有没有音轨」这个实测结论；ASR 转写要等接入 ASR 引擎（P2），
    这里**不编造**内容，显式标 pending。
    """
    has_audio = bool(media and media.get('has_audio'))
    return {
        'has_speech': None,
        'probable': has_audio,
        'asr_status': 'pending' if has_audio else 'skipped',
        'asr_text': '',
        'segments': [],
    }
