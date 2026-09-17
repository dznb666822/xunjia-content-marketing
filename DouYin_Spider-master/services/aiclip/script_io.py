# -*- coding: utf-8 -*-
"""AI 剪辑 · 剧本导入（SOP ① 的产物）。

剧本原件是 xlsx，sheet 名「分镜脚本」，9 列：

    镜号 | 参考拍摄图片 | 景别/构图 | 运镜 | 画面内容 | 人物&场景 | 台词 | 音效 | 参考时长(s)

三条实测约束（对着真实剧本 1/2 核过，不是猜的）：

1. **「景别/构图」一格三义** —— 原文写的是"中景/平视/三分法构图"，
   而 frame_shots 拆成了 shot_size / angle / composition 三列 → 必须切分，
   否则这一列的语义会一半落在 shot_size、一半丢掉。
2. **表头别按固定下标读** —— 剧本是人工维护的，中英文括号、多余空格都出现过
   （"参考时长(s)" / "参考时长（s）"）。所以按**精确名 → 关键词**两级匹配定位列。
3. **别用 `pandas.read_excel` 猜表头** —— 有的剧本前几行是说明文字，表头不在第 0 行。
   这里显式找表头行（命中 ≥3 个已知列名的那一行）。

产出落库（**JSON 是权威，DB 行是它的投影**）：
    frame_scripts  1 行   source='import'   script_json = {shots:[...]}
    frame_shots    N 行   script_id 指回去   纯剧本信息，**不带任何素材引用**
                          （素材引用是 ② 参考脚本才填的，见 §frame_shots 补列注释）

版本化：每导入一次 = 一个新 version，supersedes_version 指向上一版。
"""
import io
import os
import re
import uuid
from datetime import datetime

from loguru import logger

from services.aiclip import store

# ---------------------------------------------------------------------------
# 表头 → 字段
# ---------------------------------------------------------------------------
# 精确名（归一化后比对）。剧本列名是人工维护的，所以精确名只覆盖主形态。
_EXACT_HEADER = {
    '镜号': 'seq', '序号': 'seq', '镜头号': 'seq', 'shot': 'seq', 'no': 'seq',
    '参考拍摄图片': 'ref_image', '参考图片': 'ref_image', '参考图': 'ref_image',
    '景别/构图': 'shot_size_raw', '景别': 'shot_size_raw', '景别构图': 'shot_size_raw',
    '运镜': 'camera_move', '镜头运动': 'camera_move', '机位运动': 'camera_move',
    '画面内容': 'content', '画面': 'content', '内容': 'content',
    '人物&场景': 'characters_scene', '人物场景': 'characters_scene',
    '人物与场景': 'characters_scene', '人物': 'characters_scene', '场景': 'characters_scene',
    '台词': 'subtitle_text', '字幕': 'subtitle_text', '文案': 'subtitle_text',
    '音效': 'audio_note', '音频': 'audio_note', '音乐': 'audio_note', 'bgm': 'audio_note',
    '参考时长(s)': 'duration', '参考时长': 'duration', '时长': 'duration',
    '时长(s)': 'duration', '参考时长（s）': 'duration',
}

# 关键词兜底（按顺序，先命中先得）。⚠️ 顺序即优先级：
#   「人物&场景」必须在「内容」之前判，否则会被 '内容' 之外的词抢走；
#   '景别/构图' 里的 '构图' 要归 shot_size_raw 而不是当成独立列。
_KEYWORD_RULES = [
    ('seq', ('镜号', '序号', 'shot_no')),
    ('ref_image', ('参考拍摄', '参考图', 'ref_image', 'refimage')),
    ('shot_size_raw', ('景别', '构图', 'shot_size', 'composition')),
    ('camera_move', ('运镜', '镜头运动', 'camera_move', 'camera')),
    ('characters_scene', ('人物', '场景', 'character', 'scene')),
    ('subtitle_text', ('台词', '字幕', '文案', 'subtitle', 'voiceover')),
    ('audio_note', ('音效', '音频', '音乐', 'bgm', 'audio', 'sound')),
    ('duration', ('时长', 'duration', 'dur')),
    ('content', ('画面内容', '内容', 'content', '画面', 'visual')),
]

# 「景别/构图」切分词表
_SHOT_SIZES = ('大特写', '中近景', '中全景', '特写', '近景', '中景', '全景',
               '远景', '微距', '空镜', '全身', '半身')
_ANGLES = ('第一人称', '俯拍', '仰拍', '平视', '顶拍', '顶视', '斜角',
           '低角度', '高角度', '鸟瞰', '正视')

DEFAULT_DURATION = 1.0
MAX_SHOTS = 400


def _now():
    return datetime.now().isoformat(timespec='seconds')


def _norm(s):
    """表头归一化：去空白 + 全角括号转半角 + 小写。"""
    t = str(s or '').strip().lower()
    t = t.replace('（', '(').replace('）', ')').replace('：', ':')
    return re.sub(r'\s+', '', t)


def _to_float(v, default=DEFAULT_DURATION):
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r'-?\d+(?:\.\d+)?', str(v or ''))
    if not m:
        return default
    try:
        return float(m.group(0))
    except ValueError:
        return default


def _cell(v):
    if v is None:
        return ''
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


# ---------------------------------------------------------------------------
# 「景别/构图」→ 三段
# ---------------------------------------------------------------------------
def split_shot_size(raw):
    """'中景/平视/三分法构图' → ('中景', '平视', '三分法构图')。

    分隔符要含 `+`：真实剧本里出现过「近景+海报拼接」「中景+特写」
    （漏了 `+` 就会把 "近景+海报拼接" 整段当成景别）。
    词表外的部分统一归到 composition（自由文本，构图/视角/机位都能放）。
    """
    parts = [p.strip() for p in re.split(r'[/、|，,;；+＋]+', _cell(raw)) if p.strip()]
    size = angle = ''
    comp = []
    for p in parts:
        if not size and any(k in p for k in _SHOT_SIZES):
            size = p
        elif not angle and any(k in p for k in _ANGLES):
            angle = p
        else:
            comp.append(p)
    return size, angle, '/'.join(comp)


# ---------------------------------------------------------------------------
# 表头定位
# ---------------------------------------------------------------------------
def _field_of(header_cell):
    h = _norm(header_cell)
    if not h:
        return None
    if h in _EXACT_HEADER:
        return _EXACT_HEADER[h]
    for field, kws in _KEYWORD_RULES:
        if any(k in h for k in kws):
            return field
    return None


def map_header(header_row):
    """表头行 → {字段: 列下标}。同名取第一个。"""
    idx = {}
    for i, h in enumerate(header_row or []):
        f = _field_of(h)
        if f and f not in idx:
            idx[f] = i
    return idx


def _find_header_row(rows, scan=6):
    """找表头行：命中已知列名最多的那一行（≥3 才算）。"""
    best, best_hits = -1, 0
    for i, r in enumerate(rows[:scan]):
        hits = sum(1 for c in r if _field_of(c))
        if hits > best_hits:
            best, best_hits = i, hits
    return best if best_hits >= 3 else -1


# ---------------------------------------------------------------------------
# 二维表 → 镜数组（xlsx / csv / 粘贴文本 共用）
# ---------------------------------------------------------------------------
def parse_rows(rows):
    rows = [[_cell(c) for c in (r or [])] for r in (rows or [])]
    rows = [r for r in rows if any(r)]
    if not rows:
        raise ValueError('表格是空的')

    hi = _find_header_row(rows)
    if hi < 0:
        raise ValueError('找不到表头行（至少要认得出「镜号 / 画面内容 / 台词」里的 3 个列名）')
    idx = map_header(rows[hi])
    if 'content' not in idx and 'subtitle_text' not in idx:
        raise ValueError('表头里既没有「画面内容」也没有「台词」，无法当剧本读')
    logger.info('aiclip 剧本: 表头在第 {} 行，识别到列 {}'.format(hi, sorted(idx)))

    def get(r, field):
        i = idx.get(field)
        return r[i] if (i is not None and i < len(r)) else ''

    shots = []
    for r in rows[hi + 1:]:
        content = get(r, 'content')
        sub = get(r, 'subtitle_text')
        if not content and not sub:
            continue            # 空行 / 合计行
        try:
            seq = int(_to_float(get(r, 'seq'), len(shots) + 1))
        except Exception:
            seq = len(shots) + 1
        if seq <= 0:
            seq = len(shots) + 1
        size, angle, comp = split_shot_size(get(r, 'shot_size_raw'))
        shots.append({
            'seq': seq,
            'ref_image': get(r, 'ref_image'),
            'shot_size': size,
            'angle': angle,
            'composition': comp,
            'camera_move': get(r, 'camera_move'),
            'content': content,
            'characters_scene': get(r, 'characters_scene'),
            'subtitle_text': sub,
            'audio_note': get(r, 'audio_note'),
            'duration': round(_to_float(get(r, 'duration'), DEFAULT_DURATION), 3),
        })
        if len(shots) > MAX_SHOTS:
            raise ValueError('剧本镜数超过 {}，疑似解析错位'.format(MAX_SHOTS))
    if not shots:
        raise ValueError('表头下面没有有效镜（每行的「画面内容」「台词」都为空）')
    return shots


def parse_xlsx(source):
    """source: 磁盘路径 或 bytes。返回 (shots, sheet_name)。"""
    import openpyxl
    if isinstance(source, (bytes, bytearray)):
        wb = openpyxl.load_workbook(io.BytesIO(source), data_only=True)
    else:
        wb = openpyxl.load_workbook(source, data_only=True)
    names = wb.sheetnames or []
    if not names:
        raise ValueError('xlsx 里没有工作表')

    # 优先选名字像分镜表的；否则挑第一个列数够的
    ws = None
    for n in names:
        low = n.lower()
        if '分镜' in n or '脚本' in n or 'script' in low or 'shot' in low:
            ws = wb[n]
            break
    if ws is None:
        for n in names:
            if (wb[n].max_column or 0) >= 4:
                ws = wb[n]
                break
    if ws is None:
        raise ValueError('xlsx 里没有列数 ≥4 的工作表')

    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    return parse_rows(rows), ws.title


def parse_text(text):
    """粘贴文本 → shots。支持制表符 / 竖线 / 逗号分隔，每行一镜。"""
    rows = []
    for line in (text or '').splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if '\t' in line:
            cells = line.split('\t')
        elif '|' in line:
            cells = [c for c in line.split('|')]
        elif ',' in line:
            cells = line.split(',')
        else:
            cells = [line]
        rows.append(cells)
    if not rows:
        raise ValueError('文本为空')
    return parse_rows(rows)


# ---------------------------------------------------------------------------
# 落库
# ---------------------------------------------------------------------------
def _next_version(pid, source):
    rows = store.query(
        'SELECT MAX(`version`) AS v FROM `frame_scripts` '
        'WHERE project_id=%s AND `source`=%s', [pid, source])
    v = (rows[0] or {}).get('v') if rows else None
    return int(v or 0) + 1


def get_script(pid, source='import'):
    """取该项目最新的某类脚本（import=剧本 / reference=参考脚本）。"""
    rows = store.fetch(
        'frame_scripts', 'project_id=%s AND `source`=%s', [pid, source],
        order='version DESC', limit=1)
    return rows[0] if rows else None


def list_shots(script_id):
    if not script_id:
        return []
    return store.fetch('frame_shots', 'script_id=%s', [script_id], order='seq ASC')


def import_script(pid, shots, source_name='', requirement='', owner_id=None):
    """剧本镜数组 → frame_scripts(source='import') + frame_shots(N)。返回 script 行。

    台词/画面都没有的镜在这里不过滤（parse_rows 已过滤），但会**重排 seq**
    并算好 start_time/end_time —— 后面 LLM#2 与时间轴表都要用。
    """
    if not shots:
        raise ValueError('没有可导入的镜')
    sid = str(uuid.uuid4())
    now = _now()
    prev = _next_version(pid, 'import')
    version = prev

    total = 0.0
    cursor = 0.0
    shot_rows = []
    ordered = []
    for i, s in enumerate(shots):
        seq = int(s.get('seq') or (i + 1))
        dur = round(float(s.get('duration') or DEFAULT_DURATION), 3)
        st, en = round(cursor, 3), round(cursor + dur, 3)
        cursor = en
        total += dur
        rec = dict(s)
        rec.update({'seq': seq, 'duration': dur, 'start': st, 'end': en})
        ordered.append(rec)
        shot_rows.append({
            'id': str(uuid.uuid4()),
            'script_id': sid,
            'seq': seq,
            'start_time': st,
            'end_time': en,
            'content': s.get('content') or '',
            'shot_size': s.get('shot_size') or None,
            'angle': s.get('angle') or None,
            'composition': s.get('composition') or None,
            'camera_move': s.get('camera_move') or None,
            'characters_scene': s.get('characters_scene') or None,
            'ref_image': s.get('ref_image') or None,
            'subtitle_text': s.get('subtitle_text') or None,
            'audio_note': s.get('audio_note') or None,
            'duration': dur,
            'role': 'script',
            'status': 'imported',
            'owner_id': owner_id,
            'created_at': now,
            'updated_at': now,
        })

    store.insert('frame_scripts', {
        'id': sid,
        'project_id': pid,
        'version': version,
        'status': 'imported',
        'source': 'import',
        'shot_count': len(ordered),
        'total_duration': round(total, 3),
        'avg_shot_duration': round(total / len(ordered), 3) if ordered else 0,
        'supersedes_version': (version - 1) if version > 1 else None,
        'requirement': requirement or None,
        'script_json': {'source_name': source_name, 'shots': ordered},
        'confirm_note': source_name or None,
        'owner_id': owner_id,
        'created_at': now,
        'updated_at': now,
    })
    for r in shot_rows:
        store.insert('frame_shots', r)
    logger.info('aiclip 剧本: 项目 {} 导入 {} 镜 / {:.1f}s (v{})'.format(
        pid, len(ordered), total, version))
    return get_script(pid, 'import')


def script_brief(script, shots=None, full=False):
    """出参整形。shots 不传就自己查。"""
    if not script:
        return None
    shots = list_shots(script['id']) if shots is None else shots
    data = {
        'id': script['id'],
        'project_id': script.get('project_id'),
        'source': script.get('source'),
        'version': script.get('version'),
        'status': script.get('status'),
        'shot_count': script.get('shot_count') or len(shots),
        'total_duration': script.get('total_duration') or 0,
        'avg_shot_duration': script.get('avg_shot_duration'),
        'updated_at': script.get('updated_at'),
        'created_at': script.get('created_at'),
    }
    if full:
        data['shots'] = [shot_brief(s) for s in shots]
        data['requirement'] = script.get('requirement')
        data['raw'] = script.get('script_json')
    return data


def shot_brief(s):
    return {
        'id': s.get('id'),
        'seq': s.get('seq'),
        'start': s.get('start_time'),
        'end': s.get('end_time'),
        'duration': s.get('duration'),
        'shot_size': s.get('shot_size'),
        'angle': s.get('angle'),
        'composition': s.get('composition'),
        'camera_move': s.get('camera_move'),
        'content': s.get('content'),
        'characters_scene': s.get('characters_scene'),
        'ref_image': s.get('ref_image'),
        'subtitle_text': s.get('subtitle_text'),
        'audio_note': s.get('audio_note'),
        'role': s.get('role'),
    }
