# -*- coding: utf-8 -*-
"""AI 剪辑 · 项目业务逻辑。

状态机字段直接读 `projects` 表已有的四件套：
    status / progress / current_step / block_reason
UI 的步骤条 = 这四个字段的函数，不另造一套枚举。

`kind` 决定片型（决定中游用哪套编译规则）：
    oral        口播型 —— 主轨是口播成片零删减直通，有素材贴片层与柔化窗
    storyboard  分镜型 —— 无主轨，A-roll 素材段即主轨，无贴片
"""
import uuid
from datetime import datetime

from loguru import logger

from services.aiclip import store

# 路线图。`ready=True` = 该步骤的代码已实现（不等于本项目已完成，完成看 state）。
# 步骤条 = 这张表 + 本项目实际数据，前端不另造枚举。
STEPS = [
    {'key': 'created', 'name': '创建项目', 'hint': '命名 + 选片型', 'ready': True},
    {'key': 'assets', 'name': '导入素材', 'hint': '上传 / 从素材箱扫描', 'ready': True},
    {'key': 'probe', 'name': '素材体检', 'hint': 'sha1 / 几何 / 媒体 · 零 LLM', 'ready': True},
    {'key': 'understand', 'name': '素材理解', 'hint': '全模态 LLM → 可编排单元', 'ready': True},
    {'key': 'script', 'name': '剧本导入', 'hint': '剧本 xlsx → script.json', 'ready': True},
    {'key': 'reference', 'name': '参考脚本', 'hint': 'LLM#1：剧本 × 素材 × 需求', 'ready': True},
    {'key': 'shotlist', 'name': '方案编译', 'hint': 'LLM#2 + TTS + 校验闸门', 'ready': False},
    {'key': 'artifacts', 'name': '产物与成片', 'hint': 'workbench.ts / project.json → 导出', 'ready': False},
]

DEFAULT_CANVAS = {'w': 1080, 'h': 1920, 'fps': 30}
KINDS = ('oral', 'storyboard')


def _now():
    return datetime.now().isoformat(timespec='seconds')


def _new_id():
    return str(uuid.uuid4())


def list_projects(owner_id=None, include_archived=False):
    where, args = [], []
    if not include_archived:
        where.append('(deleted IS NULL OR deleted = 0)')
    if owner_id:
        where.append('owner_id = %s')
        args.append(owner_id)
    rows = store.fetch('projects', ' AND '.join(where) if where else '',
                       args, order='updated_at DESC')
    for r in rows:
        _attach_stats(r)
    return rows


def get_project(pid, owner_id=None):
    where = 'id = %s'
    args = [pid]
    if owner_id:
        where += ' AND owner_id = %s'
        args.append(owner_id)
    row = store.query_one('SELECT * FROM `projects` WHERE ' + where, args)
    if not row:
        return None
    row = store._decode('projects', row)
    _attach_stats(row)
    return row


def _attach_stats(row):
    """补素材统计 + 剧本/参考脚本状态 + 步骤状态（不算列，只在返回时附加）。"""
    pid = row['id']
    total = store.count('project_materials', 'project_id = %s', [pid])
    probed = understood = 0
    rows = store.query(
        'SELECT m.geom, m.media, m.classify_status FROM `project_materials` pm '
        'JOIN `materials` m ON m.id = pm.material_id WHERE pm.project_id = %s',
        [pid])
    for r in rows:
        if r.get('geom') or r.get('media'):
            probed += 1
        if r.get('classify_status') == 'done':
            understood += 1
    row['material_count'] = total
    row['probed_count'] = probed
    row['understood_count'] = understood

    # 剧本（import）与参考脚本（reference）各取最新一版
    sc = store.query_one(
        "SELECT id, shot_count, total_duration, requirement FROM `frame_scripts` "
        "WHERE project_id=%s AND `source`='import' ORDER BY version DESC LIMIT 1", [pid])
    rf = store.query_one(
        "SELECT id, shot_count, gen_status, gen_error FROM `frame_scripts` "
        "WHERE project_id=%s AND `source`='reference' ORDER BY version DESC LIMIT 1", [pid])
    row['script_id'] = (sc or {}).get('id')
    row['script_count'] = int((sc or {}).get('shot_count') or 0)
    row['script_duration'] = (sc or {}).get('total_duration') or 0
    row['requirement'] = (sc or {}).get('requirement')
    row['reference_id'] = (rf or {}).get('id')
    row['reference_status'] = (rf or {}).get('gen_status')
    row['reference_shots'] = int((rf or {}).get('shot_count') or 0)

    # P5c：TTS 旁白汇总（一镜一段，落在 audio_tracks kind='tts'）
    from services.aiclip import ttsline as _tl
    row.update(_tl.summary(pid))

    row['steps'] = build_steps(row, total, probed)
    row['step_index'] = _current_step_index(row['steps'])
    return row


def build_steps(project, material_count, probed_count):
    done = {
        'created': True,
        'assets': material_count > 0,
        'probe': material_count > 0 and probed_count >= material_count,
        'understand': material_count > 0
        and (project.get('understood_count') or 0) >= material_count,
        'script': bool(project.get('script_id')),
        'reference': project.get('reference_status') == 'done',
    }
    cur = project.get('current_step')
    out = []
    reached = False
    for i, s in enumerate(STEPS):
        k = s['key']
        is_done = bool(done.get(k))
        if is_done:
            st = 'done'
        elif not reached:
            st = 'current'
            reached = True
        else:
            st = 'pending'
        # 已由后续阶段回填过的步骤直接算完成（P2 之后用）
        if cur and cur == k and not is_done:
            st = 'current'
        out.append({
            'key': k, 'name': s['name'], 'hint': s['hint'],
            'ready': s['ready'], 'state': st, 'index': i,
        })
    return out


def _current_step_index(steps):
    for s in steps:
        if s['state'] == 'current':
            return s['index']
    return len(steps) - 1


def recompute(pid):
    """按实际数据回填 status / progress / current_step。"""
    row = store.query_one('SELECT * FROM `projects` WHERE id = %s', [pid])
    if not row:
        return None
    row = store._decode('projects', row)
    _attach_stats(row)
    idx = row['step_index']
    progress = int(round(float(idx) / float(max(len(STEPS) - 1, 1)) * 100))
    total = row['material_count']
    # 越靠后越优先：已经是「参考脚本就绪」就别退回 assets_ready
    if row.get('reference_status') == 'done':
        status = 'reference_ready'
    elif row.get('reference_status') == 'generating':
        status = 'reference_generating'
    elif row.get('reference_status') == 'failed':
        status = 'reference_failed'
    elif row.get('script_id'):
        status = 'script_ready'
    elif total and row['probed_count'] >= total:
        status = 'assets_ready'
    elif total:
        status = 'assets_importing'
    else:
        status = 'draft'
    store.update('projects', pid, {
        'progress': progress,
        'current_step': STEPS[idx]['key'],
        'status': status,
        'updated_at': _now(),
    })
    return get_project(pid)


def create(name, kind='storyboard', canvas=None, owner_id=None, created_by=None):
    name = (name or '').strip()
    if not name:
        raise ValueError('项目名不能为空')
    if kind not in KINDS:
        kind = 'storyboard'
    pid = _new_id()
    now = _now()
    row = {
        'id': pid,
        'name': name[:255],
        'status': 'draft',
        'progress': 0,
        'current_step': 'created',
        'kind': kind,
        'canvas': canvas or dict(DEFAULT_CANVAS),
        'deleted': 0,
        'owner_id': owner_id,
        'created_by': created_by,
        'created_at': now,
        'updated_at': now,
    }
    store.insert('projects', row)
    logger.info('aiclip: 新建项目 {} ({})'.format(name, pid))
    return get_project(pid)


ALLOWED_UPDATE = ('name', 'kind', 'canvas', 'voiceover_video_url',
                  'voiceover_duration', 'reference_video_url',
                  'voiceover_has_audio', 'reference_has_subtitle', 'block_reason')


def update(pid, fields):
    data = {k: v for k, v in (fields or {}).items() if k in ALLOWED_UPDATE}
    if 'kind' in data and data['kind'] not in KINDS:
        data.pop('kind')
    if 'name' in data:
        data['name'] = (data['name'] or '').strip()[:255]
        if not data['name']:
            data.pop('name')
    if not data:
        return get_project(pid)
    data['updated_at'] = _now()
    store.update('projects', pid, data)
    return get_project(pid)


def archive(pid):
    """软删除（projects.deleted / archived_at）。"""
    if not store.fetch_by_id('projects', pid):
        return False
    store.update('projects', pid, {
        'deleted': 1, 'archived_at': _now(), 'updated_at': _now(),
    })
    return True
