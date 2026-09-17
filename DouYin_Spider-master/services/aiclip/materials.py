# -*- coding: utf-8 -*-
"""AI 剪辑 · 素材业务逻辑。

`materials` 是**全库资产**（`project_id` 可空 = 公共资产，`used_count` = 被几个
项目引用过），项目与素材是多对多，所以引用关系落在 `project_materials`。
    —— 11 张表里缺这张引用表，本次补上（见 store.ensure_schema）。

去重靠 **sha1 唯一键**，不靠文件名：
    同一个文件改个名再导 → 命中已有素材行，只加一条项目引用、`used_count` +1，
    不会产生第二行，也不会重复占磁盘。
"""
import os
import re
import shutil
import uuid
from datetime import datetime

from loguru import logger

from services.aiclip import paths, probe, store

DISPLAY_TYPE = {'image': '图片', 'video': '视频'}


def _now():
    return datetime.now().isoformat(timespec='seconds')


def _new_id():
    return str(uuid.uuid4())


def _detect_kind(path):
    k = paths.file_kind(path)
    if k:
        return k
    # 扩展名不认识时，用 ffprobe 赌一把是视频
    media, _ = probe.probe_video(path)
    return 'video' if media else None


# ---------------------------------------------------------------------------
# 项目 ↔ 素材 引用
# ---------------------------------------------------------------------------
def link(project_id, material_id, owner_id=None):
    if not project_id or not material_id:
        return False
    try:
        n = store.execute(
            'INSERT IGNORE INTO `project_materials` '
            '(`id`,`project_id`,`material_id`,`seq`,`added_at`,`owner_id`) '
            'VALUES (%s,%s,%s,%s,%s,%s)',
            [_new_id(), project_id, material_id,
             store.count('project_materials', 'project_id = %s', [project_id]),
             _now(), owner_id])
        if n:
            refresh_used_count(material_id)
        return bool(n)
    except Exception as e:
        logger.error('aiclip: 挂载素材失败 {} -> {}: {}'.format(material_id, project_id, e))
        return False


def unlink(project_id, material_id):
    n = store.execute(
        'DELETE FROM `project_materials` WHERE project_id = %s AND material_id = %s',
        [project_id, material_id])
    if n:
        refresh_used_count(material_id)
    return bool(n)


def refresh_used_count(material_id):
    n = store.count('project_materials', 'material_id = %s', [material_id])
    store.update('materials', material_id, {'used_count': n, 'updated_at': _now()})
    return n


def list_for_project(project_id):
    rows = store.query(
        'SELECT m.*, pm.seq AS link_seq, pm.added_at AS linked_at '
        'FROM `project_materials` pm JOIN `materials` m ON m.id = pm.material_id '
        'WHERE pm.project_id = %s ORDER BY pm.seq ASC, pm.added_at ASC',
        [project_id])
    return [store._decode('materials', r) for r in rows]


def list_library(limit=None, offset=None):
    return store.fetch('materials', '', None, order='created_at DESC',
                       limit=limit, offset=offset)


def get(material_id):
    return store.fetch_by_id('materials', material_id)


# ---------------------------------------------------------------------------
# 导入
# ---------------------------------------------------------------------------
def _row_from_file(path, sha1, kind, probed, source, project_id,
                   owner_id, created_by, ext, original_name=None):
    geom = probed.get('geom')
    media = probed.get('media')
    w = h = None
    if geom:
        w, h = geom.get('w'), geom.get('h')
    elif media:
        w, h = media.get('width'), media.get('height')
    # ⚠️ 显示名必须用**用户上传时的原始文件名**，不能用 path ——
    # 落盘后的 path 是按 sha1 命名的（<sha1>.png），拿它当名字会显示成一串哈希。
    raw_name = original_name or os.path.basename(path)
    stem = os.path.splitext(raw_name)[0]
    return {
        'id': _new_id(),
        'project_id': project_id,          # 首次归属项目；NULL = 全库公共资产
        'name': stem[:255],
        'type': kind,
        'sub_type': DISPLAY_TYPE.get(kind),
        'source': source,
        'status': 'ready',
        'file_url': paths.file_url(sha1),
        'thumb_url': paths.thumb_url(sha1),
        'duration': float(probed.get('duration') or 0),
        'resolution': '{}x{}'.format(w, h) if (w and h) else None,
        'original_name': raw_name[:512],
        'format': (ext or '').lstrip('.')[:16],
        'file_size': os.path.getsize(path) if os.path.exists(path) else 0,
        'sha1': sha1,
        'geom': geom,
        'media': media,
        'tags': None,                       # P2：LLM 打标（素材能力层语义）
        'speech': probe.speech_probe(media),
        'seg_desc': None,                   # P2：片段级描述
        'ai_classify': None,
        'classify_status': 'pending',
        'used_count': 0,
        'created_by': created_by,
        'owner_id': owner_id,
        'created_at': _now(),
        'updated_at': _now(),
    }


def _fix_display_name(existing, display_name):
    """已有素材的展示名如果是 <sha1>.<ext> 或空，用新传来的真名补上。"""
    if not display_name:
        return
    cur = (existing.get('original_name') or '').strip()
    sha1 = existing.get('sha1') or ''
    stem = os.path.splitext(cur)[0]
    bad = (not cur) or (sha1 and stem == sha1) or stem.startswith(sha1[:16] if sha1 else '\x00')
    if not bad:
        return
    store.update('materials', existing['id'], {
        'name': os.path.splitext(display_name)[0][:255],
        'original_name': display_name[:512],
        'updated_at': _now(),
    })
    existing['name'] = os.path.splitext(display_name)[0][:255]
    existing['original_name'] = display_name[:512]


def ingest_path(path, project_id=None, owner_id=None, source='inbox',
                move=False, created_by=None, original_name=None):
    """把磁盘上的一个文件收进素材库。

    返回 (material_dict, created_bool, error_str)。
    已存在同 sha1 时：不新建行，只补项目引用并 used_count +1。
    original_name 用于展示（浏览器上传时传入真实文件名，缺省用路径的 basename）。
    """
    if not path or not os.path.isfile(path):
        return None, False, '文件不存在: {}'.format(path)
    kind = _detect_kind(path)
    if not kind:
        return None, False, '不支持的素材类型: {}'.format(os.path.basename(path))
    # 展示名必须在改名成 <sha1>.<ext> 之前抓下来
    display_name = original_name or os.path.basename(path)

    try:
        sha1 = probe.sha1_file(path)
    except OSError as e:
        return None, False, '读取失败: {}'.format(e)

    ext = os.path.splitext(path)[1].lower()
    existing = store.query_one('SELECT * FROM `materials` WHERE sha1 = %s', [sha1])
    if existing:
        existing = store._decode('materials', existing)
        # 展示名兜底修复：早期版本可能把 <sha1>.<ext> 当成了名字，发现就补回真名
        _fix_display_name(existing, display_name)
        # 磁盘文件可能被清掉了，补回来
        dst = paths.find_asset(sha1)
        if not dst:
            paths.ensure_dirs(sha1)
            dst = paths.asset_path(sha1, ext)
            try:
                shutil.copy2(path, dst)
            except OSError as e:
                logger.warning('aiclip: 补落盘失败 {}'.format(e))
        if project_id:
            link(project_id, existing['id'], owner_id)
        if move and os.path.abspath(path) != os.path.abspath(dst or ''):
            _try_remove(path)
        return existing, False, None

    paths.ensure_dirs(sha1)
    dst = paths.asset_path(sha1, ext)
    try:
        if move and os.path.abspath(path) == os.path.abspath(dst):
            pass
        elif move:
            os.replace(path, dst) if os.path.exists(path) else shutil.copy2(path, dst)
        else:
            shutil.copy2(path, dst)
    except OSError as e:
        # 跨设备 rename 会失败，退回拷贝
        try:
            shutil.copy2(path, dst)
            if move:
                _try_remove(path)
        except OSError as e2:
            return None, False, '落盘失败: {}'.format(e2)

    probe.make_thumb(dst, kind, paths.thumb_path(sha1))
    probed = probe.probe(dst, kind)
    row = _row_from_file(dst, sha1, kind, probed, source, project_id,
                         owner_id, created_by, ext, original_name=display_name)
    try:
        store.insert('materials', row)
    except Exception as e:
        logger.error('aiclip: 素材入库失败 {}: {}'.format(dst, e))
        return None, False, '入库失败: {}'.format(e)
    if project_id:
        link(project_id, row['id'], owner_id)
    logger.info('aiclip: 素材入库 {} ({})'.format(row['original_name'], row['id']))
    return get(row['id']), True, None


def _try_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def ingest_bytes(filename, data, project_id=None, owner_id=None,
                 created_by=None, source='upload'):
    """浏览器上传：先落临时文件，再走统一入口（move=True）。"""
    if not data:
        return None, False, '空文件'
    safe = os.path.basename(filename or '') or 'unnamed'
    tmpdir = os.path.join(paths.store_root(), 'tmp')
    os.makedirs(tmpdir, exist_ok=True)
    tmp = os.path.join(tmpdir, '{}_{}'.format(uuid.uuid4().hex[:8], safe))
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
    except OSError as e:
        return None, False, '写入临时文件失败: {}'.format(e)
    try:
        return ingest_path(tmp, project_id=project_id, owner_id=owner_id,
                           source=source, move=True, created_by=created_by,
                           original_name=safe)
    finally:
        if os.path.exists(tmp):
            _try_remove(tmp)


# ---------------------------------------------------------------------------
# 素材箱（inbox）
# ---------------------------------------------------------------------------
def inbox_files():
    root = paths.inbox_root()
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if not os.path.isfile(p):
            continue
        kind = paths.file_kind(p)
        if not kind:
            continue
        try:
            st = os.stat(p)
        except OSError:
            continue
        out.append({
            'name': name,
            'path': p,
            'size': st.st_size,
            'mtime': datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds'),
            'kind': kind,
            'ext': os.path.splitext(name)[1].lower().lstrip('.'),
        })
    return out


# ---------------------------------------------------------------------------
# 删除 / 重检
# ---------------------------------------------------------------------------
def remove(material_id, force=False):
    """删除全库素材。仍被项目引用且未 force 时拒绝。"""
    row = get(material_id)
    if not row:
        return False, '素材不存在'
    refs = store.count('project_materials', 'material_id = %s', [material_id])
    if refs and not force:
        return False, '该素材仍被 {} 个项目引用，请先在各项目中移除'.format(refs)
    sha1 = row.get('sha1')
    store.execute('DELETE FROM `project_materials` WHERE material_id = %s', [material_id])
    store.execute('DELETE FROM `materials` WHERE id = %s', [material_id])
    if sha1:
        for fp in (paths.find_asset(sha1), paths.thumb_path(sha1)):
            if fp and os.path.exists(fp):
                _try_remove(fp)
    return True, None


def reprobe(material_id):
    """重跑体检（换过 ffmpeg 参数 / 图片被替换过时用）。"""
    row = get(material_id)
    if not row:
        return None, '素材不存在'
    sha1 = row.get('sha1')
    src = paths.find_asset(sha1) if sha1 else None
    if not src:
        return None, '磁盘上找不到该素材文件'
    kind = row.get('type') or 'image'
    probe.make_thumb(src, kind, paths.thumb_path(sha1))
    probed = probe.probe(src, kind)
    geom, media = probed.get('geom'), probed.get('media')
    w = (geom or {}).get('w') or (media or {}).get('width')
    h = (geom or {}).get('h') or (media or {}).get('height')
    # ⚠️ 人工校对过的转写不能被体检覆盖。
    #    模型会把同音词写错（"耳净"→"耳镜"），人工改对之后重检若无条件重写
    #    speech，校对就白做了 —— 而理解结果是 ② 参考脚本的输入。
    kept = (row.get('speech') or {}).get('full_text') if row.get('understand_edited_at') else None
    speech_probe = probe.speech_probe(media)
    if kept:
        speech_probe['full_text'] = kept
    store.update('materials', material_id, {
        'geom': geom,
        'media': media,
        'speech': speech_probe,
        'duration': float(probed.get('duration') or 0),
        'resolution': '{}x{}'.format(w, h) if (w and h) else None,
        'updated_at': _now(),
    })
    return get(material_id), None


# ---------------------------------------------------------------------------
# 人工校对理解结果（模型会错，必须能改）
# ---------------------------------------------------------------------------
# 落库位置一览（前端弹窗里可编辑的字段 → DB 列）：
#     kind                  → materials.ai_classify
#     summary               → materials.tags.summary
#     tags                  → materials.tags.list
#     text_on_screen        → materials.tags.text_on_screen
#     notes                 → materials.tags.notes
#     speech_full_text      → materials.speech.full_text
#     units[i].visual/.speech/.usable_for
#                           → materials.seg_desc[i].*
def _split_list(v):
    """标签类字段：允许前端传数组，也允许传逗号/顿号/斜杠分隔的字符串。"""
    if isinstance(v, str):
        v = re.split(r'[,，、|/\n]+', v)
    return [str(s).strip() for s in (v or []) if str(s).strip()]


def update_understand(material_id, patch, editor=None):
    """人工校对理解结果，PATCH 语义（只动传进来的字段）。

    为什么必须开这个口子：全模态模型转写会因同音词出错别字，
    而理解结果是 ② 参考脚本的**唯一素材依据** —— 错字会一路带进成片字幕。
    改完打 `understand_edited_at`，前端据此标「已人工校对」（也用于
    reprobe 时保护人工改过的转写，见上）。
    """
    row = get(material_id)
    if not row:
        return None, '素材不存在'
    if not isinstance(patch, dict):
        return None, '参数格式不对'

    fields = {}
    tags = dict(row.get('tags') or {})
    speech = dict(row.get('speech') or {})
    units = list(row.get('seg_desc') or [])
    touched = []

    if 'kind' in patch:
        fields['ai_classify'] = (patch.get('kind') or '').strip() or None
        touched.append('kind')
    for k in ('summary', 'notes', 'text_on_screen'):
        if k in patch:
            tags[k] = (patch.get(k) or '').strip() or None
            touched.append(k)
    if 'tags' in patch:
        tags['list'] = _split_list(patch.get('tags'))
        touched.append('tags')
    if 'speech_full_text' in patch:
        speech['full_text'] = (patch.get('speech_full_text') or '').strip()
        touched.append('speech_full_text')

    if 'units' in patch:
        # 按 index 局部更新：只改传进来的那几段，其余原样保留。
        # 用 index 而不是整段替换，是为了前端能「改一段存一段」，不会因为
        # 某段没渲染全就把别的段清掉。
        for item in (patch.get('units') or []):
            if not isinstance(item, dict):
                continue
            try:
                i = int(item.get('index'))
            except (TypeError, ValueError):
                continue
            if not (0 <= i < len(units)):
                continue
            u = dict(units[i])
            for k in ('visual', 'speech'):
                if k in item:
                    u[k] = (item.get(k) or '').strip()
            if 'usable_for' in item:
                u['usable_for'] = _split_list(item.get('usable_for'))
            if 'start' in item or 'end' in item:
                for k in ('start', 'end'):
                    if k in item:
                        try:
                            u[k] = float(item[k])
                        except (TypeError, ValueError):
                            pass
            units[i] = u
        touched.append('units')

    if not touched:
        return row, None

    if tags:
        fields['tags'] = tags
    if speech:
        fields['speech'] = speech
    if 'units' in touched:
        fields['seg_desc'] = units
    fields['understand_edited_at'] = _now()
    fields['understand_edited_by'] = editor or 'admin'
    fields['updated_at'] = _now()
    store.update('materials', material_id, fields)
    logger.info('aiclip: 素材 {} 理解结果人工校对 ({} 项)'.format(material_id[:8], len(touched)))
    return get(material_id), None
