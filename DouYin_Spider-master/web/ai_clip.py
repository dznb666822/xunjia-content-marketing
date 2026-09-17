# -*- coding: utf-8 -*-
"""AI 剪辑模块 API（P1 项目 + 素材；P2 素材理解；P3 剧本 + 参考脚本）。

设计口径：
    · 旧版是 Smart-Clip MCP 的 web 壳（/status · /clip · /upload 全是转发），
      **已全部删除**；MCP 仓库本身保留，那 4 个 tool 将来做长视频切片还用。
    · 本模块走 services/aiclip/ 的独立 DAL，直接对齐已有 11 张表。
    · P1 一次 LLM 都不调：建项目 → 导素材 → 体检（全部确定性）。
    · P2 只在**用户主动点**理解时才调 LLM，且理解是异步的（长素材要几分钟）。
    · P3 的剧本导入是确定性的（解析 xlsx，零 LLM）；参考脚本是 LLM 第 1 次，同样异步。

路由一览
    GET    /api/aiclip/health                          自检（存储根 / ffmpeg / schema）
    GET    /api/aiclip/projects                        项目列表
    POST   /api/aiclip/projects                        新建项目
    GET    /api/aiclip/projects/<pid>                  项目详情（含步骤状态）
    PATCH  /api/aiclip/projects/<pid>                  改名 / 换片型 / 封面等
    DELETE /api/aiclip/projects/<pid>                  软删除
    GET    /api/aiclip/projects/<pid>/materials        项目素材列表
    POST   /api/aiclip/projects/<pid>/materials/upload 上传（multipart，可多文件）
    POST   /api/aiclip/projects/<pid>/materials/scan   从素材箱（inbox）扫描导入
    POST   /api/aiclip/projects/<pid>/materials/link   把全库已有素材挂到项目
    DELETE /api/aiclip/projects/<pid>/materials/<mid>  从项目移除（保留全库资产）
    GET    /api/aiclip/materials                       全库素材（轻量，不含 units）
    GET    /api/aiclip/materials/<mid>                 单素材详情（含 units / 转写全文）
    DELETE /api/aiclip/materials/<mid>                 删全库资产（有引用时拒绝）
    POST   /api/aiclip/materials/<mid>/reprobe         重跑体检（确定性）
    POST   /api/aiclip/materials/<mid>/understand      理解本条素材（异步）
    POST   /api/aiclip/projects/<pid>/materials/understand  批量理解项目素材（异步）
    GET    /api/aiclip/projects/<pid>/script           读剧本（含镜表）
    POST   /api/aiclip/projects/<pid>/script           导入剧本（xlsx 上传 / 文本粘贴）
    POST   /api/aiclip/projects/<pid>/requirement      只改用户需求
    GET    /api/aiclip/projects/<pid>/reference        读参考脚本（?full=1 带 timeline）
    POST   /api/aiclip/projects/<pid>/reference        生成参考脚本（异步，LLM 第 1 次）
    GET    /api/aiclip/projects/<pid>/reference.md     人看版 md（?download=1 下载）
    GET    /api/aiclip/projects/<pid>/tts              TTS 清单：逐镜台词 + 生成状态 + 音色库
    POST   /api/aiclip/projects/<pid>/tts/sync         导出：参考脚本台词 → TTS 清单（幂等）
    POST   /api/aiclip/projects/<pid>/tts/generate     批量合成（异步，后台逐段串行）
    POST   /api/aiclip/projects/<pid>/tts/<tid>/generate  单段合成（同步，几秒）
    DELETE /api/aiclip/projects/<pid>/tts/<tid>        删一段（连带删 wav）
    GET    /api/aiclip/tts/<tid>                       TTS 音频（Range，供 <audio> 拖动试听）
    GET    /api/aiclip/inbox                           素材箱待导入文件
    GET    /api/aiclip/file/<sha1>                     原素材（?download=1 则下载）
    GET    /api/aiclip/thumb/<sha1>                    缩略图（缺失时即时生成）

异步口径：理解一条 246s 口播要 2–3 分钟、生成一次参考脚本实测约 2 分钟，HTTP 都等不起。
所以 POST 立即返回，进度由列表里的 `understand.status` / `reference_status`
（pending|generating|done|failed）反映，前端轮询即可 —— 不额外造一套任务轮询接口。
"""
import os
import re
import threading

from flask import Blueprint, jsonify, request, send_file, session
from loguru import logger

from services.aiclip import materials as mat
from services.aiclip import paths, probe, projects, store
from services.aiclip import reference as ref
from services.aiclip import script_io as sio
from services.aiclip import ttsline as tl
from services.aiclip import understand as und

bp = Blueprint('ai_clip', __name__)

SHA1_RE = re.compile(r'^[0-9a-f]{40}$')
MIME_FALLBACK = {
    '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm',
    '.mkv': 'video/x-matroska', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif',
    '.bmp': 'image/bmp',
}


@bp.before_request
def _bootstrap():
    """首次进入本蓝图时自愈 schema 与目录（幂等，之后零开销）。"""
    store.ensure_schema()
    paths.ensure_dirs()


def _owner():
    """P1 单租户：owner_id 先记录、不过滤（多租户在 P3 打开过滤）。"""
    try:
        return session.get('user_id')
    except Exception:
        return None


def _ok(data=None, **extra):
    body = {'success': True}
    if data is not None:
        body['data'] = data
    body.update(extra)
    return jsonify(body)


def _err(msg, code=200):
    return jsonify({'success': False, 'error': msg}), code


def _body():
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
@bp.route('/api/aiclip/health', methods=['GET'])
def api_health():
    import shutil as _sh
    return _ok({
        'store_root': paths.store_root(),
        'store_writable': os.access(paths.store_root(), os.W_OK)
        if os.path.isdir(paths.store_root()) else False,
        'inbox_root': paths.inbox_root(),
        'inbox_exists': os.path.isdir(paths.inbox_root()),
        'ffmpeg': bool(_sh.which(probe.FFMPEG)),
        'ffprobe': bool(_sh.which(probe.FFPROBE)),
        'pillow': probe.Image is not None,
        **store.health(),
    })


# ---------------------------------------------------------------------------
# 项目
# ---------------------------------------------------------------------------
@bp.route('/api/aiclip/projects', methods=['GET'])
def api_project_list():
    rows = projects.list_projects()
    return _ok([_project_brief(r) for r in rows],
               steps_schema=[{k: s[k] for k in ('key', 'name', 'hint', 'ready')}
                             for s in projects.STEPS],
               kinds=[{'value': 'storyboard', 'label': '分镜型',
                       'desc': '无主轨，A-roll 素材段即主轨'},
                      {'value': 'oral', 'label': '口播型',
                       'desc': '主轨口播成片零删减直通，有贴片层与柔化窗'}])


@bp.route('/api/aiclip/projects', methods=['POST'])
def api_project_create():
    b = _body()
    try:
        row = projects.create(
            name=b.get('name'),
            kind=b.get('kind') or 'storyboard',
            canvas=b.get('canvas'),
            owner_id=_owner(),
            created_by=(b.get('created_by') or 'web'),
        )
    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.error('aiclip: 建项目失败 {}'.format(e))
        return _err('建项目失败: {}'.format(e))
    return _ok(_project_brief(row))


@bp.route('/api/aiclip/projects/<pid>', methods=['GET'])
def api_project_detail(pid):
    row = projects.get_project(pid)
    if not row:
        return _err('项目不存在')
    data = _project_brief(row)
    data['materials'] = [_material_brief(m) for m in mat.list_for_project(pid)]
    return _ok(data)


@bp.route('/api/aiclip/projects/<pid>', methods=['PATCH', 'POST'])
def api_project_update(pid):
    if not projects.get_project(pid):
        return _err('项目不存在')
    row = projects.update(pid, _body())
    row = projects.recompute(pid) or row
    return _ok(_project_brief(row))


@bp.route('/api/aiclip/projects/<pid>', methods=['DELETE'])
def api_project_delete(pid):
    if not projects.archive(pid):
        return _err('项目不存在')
    return _ok({'id': pid})


# ---------------------------------------------------------------------------
# 项目素材
# ---------------------------------------------------------------------------
@bp.route('/api/aiclip/projects/<pid>/materials', methods=['GET'])
def api_project_materials(pid):
    if not projects.get_project(pid):
        return _err('项目不存在')
    return _ok([_material_brief(m) for m in mat.list_for_project(pid)])


@bp.route('/api/aiclip/projects/<pid>/materials/upload', methods=['POST'])
def api_project_upload(pid):
    if not projects.get_project(pid):
        return _err('项目不存在')
    files = request.files.getlist('files') or request.files.getlist('file')
    if not files:
        return _err('没有收到文件')
    owner = _owner()
    added, deduped, failed = [], [], []
    for f in files:
        name = f.filename or ''
        if not name:
            continue
        try:
            data = f.read()
        except Exception as e:
            failed.append({'name': name, 'error': '读取失败: {}'.format(e)})
            continue
        row, created, err = mat.ingest_bytes(name, data, project_id=pid,
                                             owner_id=owner, source='upload')
        if err:
            failed.append({'name': name, 'error': err})
        elif created:
            added.append(_material_brief(row))
        else:
            deduped.append(_material_brief(row))
    projects.recompute(pid)
    return _ok({'added': added, 'deduped': deduped, 'failed': failed,
                'added_count': len(added), 'deduped_count': len(deduped),
                'failed_count': len(failed)})


@bp.route('/api/aiclip/projects/<pid>/materials/scan', methods=['POST'])
def api_project_scan(pid):
    """从素材箱导入。body: {"names": ["a.mp4", ...]} 或 {"all": true}。"""
    if not projects.get_project(pid):
        return _err('项目不存在')
    b = _body()
    files = mat.inbox_files()
    if not b.get('all'):
        want = set(b.get('names') or [])
        if not want:
            return _err('未选择文件')
        files = [f for f in files if f['name'] in want]
    if not files:
        return _err('素材箱里没有可导入的文件')
    owner = _owner()
    added, deduped, failed = [], [], []
    for f in files:
        row, created, err = mat.ingest_path(
            f['path'], project_id=pid, owner_id=owner,
            source='inbox', move=bool(b.get('move')))
        if err:
            failed.append({'name': f['name'], 'error': err})
        elif created:
            added.append(_material_brief(row))
        else:
            deduped.append(_material_brief(row))
    projects.recompute(pid)
    return _ok({'added': added, 'deduped': deduped, 'failed': failed,
                'added_count': len(added), 'deduped_count': len(deduped),
                'failed_count': len(failed)})


@bp.route('/api/aiclip/projects/<pid>/materials/link', methods=['POST'])
def api_project_link(pid):
    if not projects.get_project(pid):
        return _err('项目不存在')
    mid = (_body().get('material_id') or '').strip()
    if not mid:
        return _err('缺少 material_id')
    if not mat.get(mid):
        return _err('素材不存在')
    mat.link(pid, mid, _owner())
    projects.recompute(pid)
    return _ok({'project_id': pid, 'material_id': mid})


@bp.route('/api/aiclip/projects/<pid>/materials/<mid>', methods=['DELETE'])
def api_project_unlink(pid, mid):
    mat.unlink(pid, mid)
    projects.recompute(pid)
    return _ok({'project_id': pid, 'material_id': mid})


# ---------------------------------------------------------------------------
# 全库素材
# ---------------------------------------------------------------------------
@bp.route('/api/aiclip/materials', methods=['GET'])
def api_material_library():
    rows = mat.list_library()
    return _ok([_material_brief(m) for m in rows])


@bp.route('/api/aiclip/materials/<mid>', methods=['DELETE'])
def api_material_delete(mid):
    force = request.args.get('force') in ('1', 'true', 'yes')
    ok, err = mat.remove(mid, force=force)
    return _ok({'id': mid}) if ok else _err(err)


@bp.route('/api/aiclip/materials/<mid>/reprobe', methods=['POST'])
def api_material_reprobe(mid):
    row, err = mat.reprobe(mid)
    if err:
        return _err(err)
    return _ok(_material_brief(row))


# ---------------------------------------------------------------------------
# 素材理解（P2）：异步。长素材 2–3 分钟，HTTP 等不起，进度靠轮询素材列表
# ---------------------------------------------------------------------------
_und_lock = threading.Lock()
_und_running = set()


def _spawn_understand(mid, force=False):
    """起一条后台理解线程。返回 (是否已起, 拒绝原因)。"""
    row = store.fetch_by_id('materials', mid)
    if not row:
        return False, '素材不存在'
    if row.get('classify_status') == 'running' and not force:
        return False, '正在理解中'
    with _und_lock:
        if mid in _und_running:
            return False, '正在理解中'
        _und_running.add(mid)

    def work():
        try:
            und.understand_material(mid, force=force)
        except Exception as e:
            logger.error('aiclip: 后台理解异常 {}: {}'.format(mid, e))
        finally:
            with _und_lock:
                _und_running.discard(mid)

    threading.Thread(target=work, daemon=True,
                     name='und-{}'.format(mid[:8])).start()
    return True, None


@bp.route('/api/aiclip/materials/<mid>', methods=['GET'])
def api_material_detail(mid):
    row = mat.get(mid)
    if not row:
        return _err('素材不存在')
    return _ok(_material_brief(row, full=True))


@bp.route('/api/aiclip/materials/<mid>/understand', methods=['PATCH'])
def api_material_understand_edit(mid):
    """人工校对理解结果（PATCH，只改传进来的字段）。

    body: {kind?, summary?, tags?, text_on_screen?, notes?,
           speech_full_text?, units?: [{index, visual, speech, usable_for}]}

    为什么需要：全模态模型转写会因同音词出错别字（"耳净"→"耳镜"），
    而理解结果是 ② 参考脚本的唯一素材依据 —— 错字会一路带进成片字幕。
    """
    row, err = mat.update_understand(mid, _body(), editor=_owner())
    if err:
        return _err(err)
    return _ok(_material_brief(row, full=True))


@bp.route('/api/aiclip/materials/<mid>/understand', methods=['POST'])
def api_material_understand(mid):
    b = _body()
    started, why = _spawn_understand(mid, force=bool(b.get('force')))
    if not started:
        return _err(why)
    return _ok({'id': mid, 'status': 'running',
                'ver': und.VER, 'model': und.ark.MODEL})


@bp.route('/api/aiclip/projects/<pid>/materials/understand', methods=['POST'])
def api_project_understand(pid):
    """批量理解项目素材。

    body: {ids?: [...], force?: bool}
      · 不给 ids 就对全项目素材
      · 默认跳过「已 done 且版本一致」的，所以按钮可以反复点而不重复烧钱
    """
    if not projects.get_project(pid):
        return _err('项目不存在')
    b = _body()
    want = set(b.get('ids') or [])
    force = bool(b.get('force'))
    targets, skipped = [], 0
    for m in mat.list_for_project(pid):
        if want and m['id'] not in want:
            continue
        if (not force) and m.get('classify_status') == 'done' \
                and m.get('understand_ver') == und.VER:
            skipped += 1
            continue
        targets.append(m['id'])
    # 长素材优先起（否则排在最后要等很久）
    by_id = {m['id']: m for m in mat.list_for_project(pid)}
    targets.sort(key=lambda i: -(by_id.get(i, {}).get('duration') or 0))
    started, busy = [], []
    for mid in targets:
        ok, why = _spawn_understand(mid, force)
        if ok:
            started.append(mid)
        else:
            busy.append({'id': mid, 'why': why})
    return _ok({
        'started': len(started), 'busy': len(busy), 'skipped': skipped,
        'total': len(targets), 'ver': und.VER, 'model': und.ark.MODEL,
    }, started_ids=started, busy=busy)


@bp.route('/api/aiclip/understand/status', methods=['GET'])
def api_understand_status():
    """全局理解队列自检（排查「按钮点了没反应」用）。"""
    with _und_lock:
        running = sorted(_und_running)
    return _ok({'running': running, 'count': len(running),
                'ver': und.VER, 'model': und.ark.MODEL,
                'ark_available': und.ark.available()})


# ---------------------------------------------------------------------------
# 剧本导入（P3 · SOP ①）
#   产物：frame_scripts(source='import') + frame_shots(N)。零 LLM。
#   入口两种：上传 xlsx（主）/ 粘贴文本（备用）。
# ---------------------------------------------------------------------------
@bp.route('/api/aiclip/projects/<pid>/script', methods=['GET'])
def api_script_get(pid):
    if not projects.get_project(pid):
        return _err('项目不存在')
    row = sio.get_script(pid, 'import')
    if not row:
        return _ok(None)
    # 剧本镜数有限（实测 10–12 镜），不像 246s 口播的 units 那样会爆体积，直接给全
    return _ok(sio.script_brief(row, full=True))


@bp.route('/api/aiclip/projects/<pid>/script', methods=['POST'])
def api_script_import(pid):
    """导入剧本。

    multipart  file=<xlsx>                     主入口
    json       {"text": "…"} / {"rows": [[…]]}  粘贴
    json       {"requirement": "…"}             可同时带用户需求
    """
    if not projects.get_project(pid):
        return _err('项目不存在')
    shots, sheet, source_name = [], '', ''
    b = _body()
    requirement = (b.get('requirement') or '').strip()

    f = request.files.get('file') or request.files.get('files')
    if f is not None and (f.filename or '').strip():
        source_name = f.filename.strip()
        try:
            data = f.read()
        except Exception as e:
            return _err('读取文件失败: {}'.format(e))
        low = source_name.lower()
        try:
            if low.endswith(('.xlsx', '.xlsm')):
                shots, sheet = sio.parse_xlsx(data)
            elif low.endswith(('.csv', '.txt', '.md')):
                shots = sio.parse_text(data.decode('utf-8-sig', 'ignore'))
            else:
                try:                       # 后缀不认识：先当 xlsx 试
                    shots, sheet = sio.parse_xlsx(data)
                except Exception:
                    shots = sio.parse_text(data.decode('utf-8-sig', 'ignore'))
        except Exception as e:
            return _err('解析失败: {}'.format(e))
    elif b.get('rows'):
        try:
            shots = sio.parse_rows(b['rows'])
        except Exception as e:
            return _err('解析失败: {}'.format(e))
        source_name = (b.get('source_name') or 'pasted').strip()
    elif (b.get('text') or '').strip():
        try:
            shots = sio.parse_text(b['text'])
        except Exception as e:
            return _err('解析失败: {}'.format(e))
        source_name = (b.get('source_name') or 'pasted').strip()
    else:
        return _err('请上传剧本 xlsx，或粘贴剧本文本')

    if not shots:
        return _err('没有解析出任何镜')

    try:
        row = sio.import_script(pid, shots, source_name=source_name,
                                requirement=requirement, owner_id=_owner())
    except Exception as e:
        logger.error('aiclip: 剧本导入失败 {}'.format(e))
        return _err('导入失败: {}'.format(e))
    projects.recompute(pid)
    return _ok(sio.script_brief(row, full=True),
               sheet=sheet, parsed=len(shots),
               total_duration=row.get('total_duration'))


@bp.route('/api/aiclip/projects/<pid>/requirement', methods=['POST'])
def api_requirement_set(pid):
    """只改用户需求（不动剧本）。需求挂在最新一版 import 脚本上。"""
    if not projects.get_project(pid):
        return _err('项目不存在')
    row = sio.get_script(pid, 'import')
    if not row:
        return _err('还没有导入剧本')
    req = (_body().get('requirement') or '').strip()
    store.update('frame_scripts', row['id'], {'requirement': req or None})
    return _ok({'id': row['id'], 'requirement': req})


# ---------------------------------------------------------------------------
# 参考脚本（P3 · SOP ② ，LLM 第 1 次 —— 叙事层）
#   输入：剧本 × 素材理解 × 用户需求 —— 产出 reference.json + 人看版 md
#   同样异步：一次调用实测 90–140s（11795 in / 6105 out tokens），HTTP 等不起。
# ---------------------------------------------------------------------------
_ref_lock = threading.Lock()
_ref_running = set()


def _spawn_reference(pid, requirement=None, owner_id=None):
    """起一条后台生成线程。返回 (是否已起, 拒绝原因)。"""
    with _ref_lock:
        if pid in _ref_running:
            return False, '正在生成中，请稍候'
        _ref_running.add(pid)

    def work():
        try:
            ref.generate(pid, requirement=requirement, owner_id=owner_id)
        except Exception as e:
            logger.error('aiclip: 后台生成参考脚本异常 {}: {}'.format(pid, e))
        finally:
            with _ref_lock:
                _ref_running.discard(pid)

    threading.Thread(target=work, daemon=True,
                     name='ref-{}'.format(pid[:8])).start()
    return True, None


@bp.route('/api/aiclip/projects/<pid>/reference', methods=['GET'])
def api_reference_get(pid):
    if not projects.get_project(pid):
        return _err('项目不存在')
    full = request.args.get('full') in ('1', 'true', 'yes')
    row = store.fetch(
        'frame_scripts', "project_id=%s AND `source`='reference'", [pid],
        order='version DESC', limit=1)
    if not row:
        return _ok(None, running=(pid in _ref_running), ver=ref.VER)
    return _ok(ref.reference_brief(row[0], full=full),
               running=(pid in _ref_running), ver=ref.VER, model=ref.ark.MODEL)


@bp.route('/api/aiclip/projects/<pid>/reference', methods=['POST'])
def api_reference_generate(pid):
    """生成参考脚本（异步）。

    body: {"requirement": "…", "force": true}
      · 不传 requirement 就沿用剧本上已存的需求
      · 生成中重复点会被拒（同一项目同时只跑一条）
    """
    project = projects.get_project(pid)
    if not project:
        return _err('项目不存在')
    if not project.get('script_id'):
        return _err('还没有导入剧本 —— 先做「剧本导入」这一步')
    if not project.get('understood_count'):
        return _err('还没有已理解的素材 —— 先去「素材理解」跑一遍')
    b = _body()
    req = b.get('requirement')
    req = req.strip() if isinstance(req, str) else None
    started, why = _spawn_reference(pid, requirement=req, owner_id=_owner())
    if not started:
        return _err(why)
    return _ok({'project_id': pid, 'status': 'generating',
                'ver': ref.VER, 'model': ref.ark.MODEL})


@bp.route('/api/aiclip/projects/<pid>/reference.md', methods=['GET'])
def api_reference_md(pid):
    """人看版 md（?download=1 直接下载）。"""
    row = store.fetch(
        'frame_scripts', "project_id=%s AND `source`='reference'", [pid],
        order='version DESC', limit=1)
    if not row or not row[0].get('reference_md'):
        return _err('还没有生成参考脚本', 404)
    md = row[0]['reference_md']
    if request.args.get('download') in ('1', 'true', 'yes'):
        import io as _io
        from flask import send_file as _sf
        name = '{}-参考脚本.md'.format((projects.get_project(pid) or {}).get('name') or 'project')
        return _sf(_io.BytesIO(md.encode('utf-8')), mimetype='text/markdown',
                   as_attachment=True, download_name=name)
    return bp.response_class(md, mimetype='text/markdown; charset=utf-8')


# ---------------------------------------------------------------------------
# TTS 语音（P5c）—— 参考脚本的台词 → 一镜一段旁白 → TTS 合成
#   合成引擎由 services/tts.py 选（默认火山引擎豆包语音合成大模型）
# ---------------------------------------------------------------------------
_TTS_MIME = {
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav',
    'ogg': 'audio/ogg',
    'opus': 'audio/ogg',
    'pcm': 'audio/L16',
    'aac': 'audio/aac',
    'm4a': 'audio/mp4',
}


@bp.route('/api/aiclip/projects/<pid>/tts', methods=['GET'])
def api_tts_list(pid):
    """TTS 清单：逐镜台词（来自参考脚本）+ 生成状态 + 音色库。

    台词是**读出来的**，不是让用户另写一份 —— 单一数据源留在参考脚本里，
    否则参考脚本一改两边就对不上（「导出」这个动作因此是「对齐」，不是「复制」）。
    """
    if not projects.get_project(pid):
        return _err('项目不存在')
    return _ok(tl.preview(pid))


@bp.route('/api/aiclip/projects/<pid>/tts/sync', methods=['POST'])
def api_tts_sync(pid):
    """「导出」：把参考脚本的每镜台词交接给 TTS 清单（幂等）。"""
    if not projects.get_project(pid):
        return _err('项目不存在')
    row = tl.latest_reference(pid)
    if not row:
        return _err('还没有参考脚本 —— 先在「参考脚本生成」里跑一次')
    if row.get('gen_status') != 'done':
        return _err('参考脚本还在生成中，等它出结果再导出')
    res = tl.sync(pid, owner_id=_owner())
    if not res['total']:
        return _err('参考脚本里没有可配音的台词（所有镜的 subtitle_text 都是空的）')
    return _ok(tl.preview(pid), changed=res)


@bp.route('/api/aiclip/projects/<pid>/tts/generate', methods=['POST'])
def api_tts_generate_batch(pid):
    """批量合成（异步，后台逐段串行）。body: {"all":true} 或 {"ids":[3,4,5]}"""
    if not projects.get_project(pid):
        return _err('项目不存在')
    b = _body()
    ids = b.get('ids') or []
    if not isinstance(ids, list):
        return _err('ids 必须是数组')
    ok, why = tl.generate_batch(
        pid, ids=ids, all_=bool(b.get('all')), voice=b.get('voice'),
        rate=b.get('rate'), force=bool(b.get('force')))
    if not ok:
        return _err(why)
    return _ok(tl.batch_state(pid))


@bp.route('/api/aiclip/projects/<pid>/tts/<tid>/generate', methods=['POST'])
def api_tts_generate_one(pid, tid):
    """单段合成（同步，通常几秒 —— 前端直接转圈等结果）。"""
    if not projects.get_project(pid):
        return _err('项目不存在')
    track = store.fetch_by_id('audio_tracks', tid)
    if not track or track.get('project_id') != pid or track.get('kind') != tl.KIND:
        return _err('音频段不存在')
    b = _body()
    try:
        tl.generate_one(pid, track, voice=b.get('voice'), rate=b.get('rate'),
                        force=bool(b.get('force')))
    except Exception as e:
        return _err(str(e))
    return _ok(_tts_segment(store.fetch_by_id('audio_tracks', tid)))


@bp.route('/api/aiclip/projects/<pid>/tts/<tid>', methods=['DELETE'])
def api_tts_delete(pid, tid):
    if not projects.get_project(pid):
        return _err('项目不存在')
    if not tl.remove(pid, tid):
        return _err('音频段不存在')
    return _ok(tl.preview(pid))


@bp.route('/api/aiclip/tts/<tid>', methods=['GET'])
def api_tts_file(tid):
    """TTS 音频文件。`conditional=True` 支持 Range —— `<audio>` 拖进度条要用。

    ⚠️ 扩展名随 TTS provider 变（火山 mp3 / CosyVoice wav），**按 tid 扫目录**而不是
    拼路径 —— 换过 provider 的项目里新旧两种扩展名会同时存在。
    """
    row = store.fetch_by_id('audio_tracks', tid)
    if not row or row.get('kind') != tl.KIND:
        return _err('音频不存在', 404)
    fp = paths.find_tts_file(row.get('project_id'), tid)
    if not fp or not os.path.isfile(fp):
        return _err('音频文件不存在（点「生成」重新合成）', 404)
    ext = os.path.splitext(fp)[1].lstrip('.').lower()
    resp = send_file(fp, mimetype=_TTS_MIME.get(ext, 'application/octet-stream'),
                     conditional=True)
    # 重新生成 = 覆盖同一路径，所以必须禁缓存，否则浏览器一直播旧音频
    resp.headers['Cache-Control'] = 'no-store, must-revalidate'
    if request.args.get('download') in ('1', 'true', 'yes'):
        seq = row.get('shot_seq')
        resp.headers['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'{}'.format(
            _quote('tts-{}.{}'.format(seq if seq is not None else str(tid)[:8],
                                      ext or 'bin')))
    return resp


def _tts_segment(track):
    """单段出参（与 ttsline.preview 的 segments 元素同形，前端只维护一套渲染）。"""
    return {
        'seq': track.get('shot_seq'),
        'shot_id': track.get('shot_id'),
        'text': track.get('text_content'),
        'chars': len(track.get('text_content') or ''),
        'track_id': track.get('id'),
        'status': track.get('status'),
        'audio_url': track.get('url') if track.get('status') == tl.STATUS_DONE else None,
        'audio_duration': float(track.get('duration') or 0),
        'voice': track.get('voice_id'),
        'rate': track.get('speech_rate'),
        'gen_error': track.get('gen_error'),
        'gen_at': track.get('gen_at'),
        'synced': True,
    }


# ---------------------------------------------------------------------------
# 素材箱
# ---------------------------------------------------------------------------
@bp.route('/api/aiclip/inbox', methods=['GET'])
def api_inbox():
    files = mat.inbox_files()
    return _ok(files, root=paths.inbox_root(), exists=os.path.isdir(paths.inbox_root()))


# ---------------------------------------------------------------------------
# 文件服务（按 sha1 取，不暴露磁盘路径）
# ---------------------------------------------------------------------------
@bp.route('/api/aiclip/file/<sha1>', methods=['GET'])
def api_file(sha1):
    if not SHA1_RE.match(sha1 or ''):
        return _err('非法 sha1')
    fp = paths.find_asset(sha1)
    if not fp or not os.path.isfile(fp):
        return _err('文件不存在', 404)
    ext = os.path.splitext(fp)[1].lower()
    resp = send_file(fp, mimetype=MIME_FALLBACK.get(ext), conditional=True)
    if request.args.get('download') in ('1', 'true', 'yes'):
        row = store.query_one('SELECT original_name FROM `materials` WHERE sha1=%s', [sha1])
        name = (row or {}).get('original_name') or os.path.basename(fp)
        resp.headers['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'{}'.format(
            _quote(name))
    return resp


@bp.route('/api/aiclip/thumb/<sha1>', methods=['GET'])
def api_thumb(sha1):
    if not SHA1_RE.match(sha1 or ''):
        return _err('非法 sha1')
    tp = paths.thumb_path(sha1)
    if not os.path.isfile(tp):
        src = paths.find_asset(sha1)
        if not src:
            return _err('文件不存在', 404)
        row = store.query_one('SELECT type FROM `materials` WHERE sha1=%s', [sha1])
        kind = (row or {}).get('type') or paths.file_kind(src) or 'image'
        if not probe.make_thumb(src, kind, tp):
            return _err('缩略图生成失败', 404)
    return send_file(tp, mimetype='image/jpeg', conditional=True)


def _quote(name):
    from urllib.parse import quote
    return quote(name or 'material')


# ---------------------------------------------------------------------------
# 出参整形
# ---------------------------------------------------------------------------
def _project_brief(r):
    return {
        'id': r['id'],
        'name': r.get('name') or '未命名',
        'kind': r.get('kind') or 'storyboard',
        'status': r.get('status') or 'draft',
        'progress': r.get('progress') or 0,
        'current_step': r.get('current_step'),
        'block_reason': r.get('block_reason'),
        'canvas': r.get('canvas'),
        'material_count': r.get('material_count', 0),
        'probed_count': r.get('probed_count', 0),
        'understood_count': r.get('understood_count', 0),
        'script_id': r.get('script_id'),
        'script_count': r.get('script_count', 0),
        'script_duration': r.get('script_duration') or 0,
        'requirement': r.get('requirement'),
        'reference_id': r.get('reference_id'),
        'reference_status': r.get('reference_status'),
        'reference_shots': r.get('reference_shots', 0),
        # P5c：TTS 旁白（一镜一段，落在 audio_tracks kind='tts'）
        'tts_count': r.get('tts_count', 0),
        'tts_done': r.get('tts_done', 0),
        'tts_failed': r.get('tts_failed', 0),
        'steps': r.get('steps') or [],
        'step_index': r.get('step_index', 0),
        'created_at': r.get('created_at'),
        'updated_at': r.get('updated_at'),
    }


def _material_brief(m, full=False):
    """素材出参。

    `full=False`（列表用）只给理解的**摘要**：246s 口播的 units 有 31 段、
    转写全文几千字，列表里全带上会让一个项目详情接口变成几百 KB。
    详情走 `GET /api/aiclip/materials/<mid>` 取 full。
    """
    geom = m.get('geom') or {}
    media = m.get('media') or {}
    tags = m.get('tags') or {}
    sp = m.get('speech') or {}
    units = m.get('seg_desc') or []
    und_info = {
        'status': m.get('classify_status') or 'pending',
        'ver': m.get('understand_ver'),
        'at': m.get('understand_at'),
        'error': m.get('understand_error'),
        'cost': m.get('understand_cost'),
        'kind': m.get('ai_classify'),
        'summary': tags.get('summary'),
        'tags': tags.get('list') or [],
        'text_on_screen': tags.get('text_on_screen'),
        'notes': tags.get('notes'),
        'modality': tags.get('modality'),
        'unit_count': len(units),
        'has_speech': bool(sp.get('has_speech')),
        'speech_chars': len(sp.get('full_text') or ''),
        # 人工校对标记：模型原文 vs 人改过的，前端要能一眼分清
        'edited': bool(m.get('understand_edited_at')),
        'edited_at': m.get('understand_edited_at'),
    }
    if full:
        und_info['units'] = units
        und_info['speech'] = sp
    return {
        'id': m['id'],
        'sha1': m.get('sha1'),
        'name': m.get('name') or m.get('original_name') or '',
        'original_name': m.get('original_name'),
        'type': m.get('type'),
        'format': m.get('format'),
        'file_size': m.get('file_size') or 0,
        'duration': m.get('duration') or 0,
        'resolution': m.get('resolution'),
        'file_url': m.get('file_url'),
        'thumb_url': m.get('thumb_url'),
        'used_count': m.get('used_count') or 0,
        'classify_status': m.get('classify_status') or 'pending',
        'understand': und_info,
        'geom': geom,
        'media': media,
        'content_ratio': geom.get('content_ratio'),
        'bbox': geom.get('bbox'),
        'bbox_px': geom.get('bbox_px'),
        'has_alpha': geom.get('has_alpha'),
        'fps': media.get('fps'),
        'has_audio': media.get('has_audio'),
        'probed': bool(geom or media),
        'created_at': m.get('created_at'),
    }
