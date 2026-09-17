# -*- coding: utf-8 -*-
"""AI 剪辑素材仓路径规则。

存储布局（宿主机 `D:/aiclip_store` 挂载到容器 `/app/aiclip_store`）：

    <store_root>/assets/<xx>/<sha1>.<ext>    原素材，xx = sha1 前两位分桶
    <store_root>/thumbs/<xx>/<sha1>.jpg      缩略图
    <store_root>/tts/<pid>/<track_id>.wav    TTS 旁白（一镜一段，见文件末尾）

扫描来源目录（宿主机 `D:/aiclip_inbox` 挂载到容器 `/app/aiclip_inbox`）：

    用户把待导入素材丢进这里，页面里勾选导入（小文件走浏览器上传，大文件走这里）

⚠️ 文件落盘路径**只用 sha1**，原始文件名只做展示字段。这样中文名 / 重名 /
   特殊字符都不会影响磁盘布局，改名也不会失效（这正是 sha1 当 asset_id 的意义）。
"""
import os

IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi'}
ALLOWED_EXT = IMAGE_EXT | VIDEO_EXT


def store_root():
    return os.environ.get('AICLIP_STORE_ROOT', '/app/aiclip_store')


def inbox_root():
    return os.environ.get('AICLIP_INBOX_ROOT', '/app/aiclip_inbox')


def bucket(sha1):
    """sha1 前两位分桶，避免单目录堆几万个文件。"""
    s = (sha1 or '').strip()
    return s[:2] if len(s) >= 2 else '00'


def asset_dir(sha1):
    return os.path.join(store_root(), 'assets', bucket(sha1))


def thumb_dir(sha1):
    return os.path.join(store_root(), 'thumbs', bucket(sha1))


def asset_path(sha1, ext):
    ext = (ext or '').lower()
    if not ext.startswith('.'):
        ext = '.' + ext if ext else '.bin'
    return os.path.join(asset_dir(sha1), '{}{}'.format(sha1, ext))


def thumb_path(sha1):
    return os.path.join(thumb_dir(sha1), '{}.jpg'.format(sha1))


def file_url(sha1):
    return '/api/aiclip/file/{}'.format(sha1)


def thumb_url(sha1):
    return '/api/aiclip/thumb/{}'.format(sha1)


# ---------------------------------------------------------------------------
# TTS 语音（P5c）
#   一镜一段旁白，按项目分目录：<store_root>/tts/<pid>/<track_id>.wav
#   文件名用 audio_tracks.id（不是 seq）：重新生成 = 覆盖同一路径，
#   所以 URL 要带 ?v=<updated_at> 破缓存，否则浏览器一直播旧音频。
# ---------------------------------------------------------------------------
def tts_dir(pid):
    return os.path.join(store_root(), 'tts', str(pid or '_orphan'))


def tts_path(pid, tid):
    return os.path.join(tts_dir(pid), '{}.wav'.format(tid))


def tts_url(tid):
    return '/api/aiclip/tts/{}'.format(tid)


def ensure_tts_dir(pid):
    d = tts_dir(pid)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def ensure_dirs(sha1=None):
    """建目录。传 sha1 则只建该素材的两个分桶目录。"""
    targets = [store_root(), inbox_root()]
    if sha1:
        targets += [asset_dir(sha1), thumb_dir(sha1)]
    else:
        targets += [os.path.join(store_root(), 'assets'),
                    os.path.join(store_root(), 'thumbs'),
                    os.path.join(store_root(), 'tts')]
    for d in targets:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass


def file_kind(path):
    """按扩展名判定 media 类型：image / video / 其它 None。"""
    ext = os.path.splitext(path or '')[1].lower()
    if ext in IMAGE_EXT:
        return 'image'
    if ext in VIDEO_EXT:
        return 'video'
    return None


def find_asset(sha1):
    """按 sha1 在分桶里找已落盘的原素材（扩展名未知，扫目录）。"""
    d = asset_dir(sha1)
    if not os.path.isdir(d):
        return None
    for name in os.listdir(d):
        if name.startswith(sha1 + '.'):
            return os.path.join(d, name)
    return None
