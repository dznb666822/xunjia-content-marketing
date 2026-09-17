# -*- coding: utf-8 -*-
"""AI 剪辑 · TTS 语音线（P5c）。

链路：参考脚本的「台词」→ 一镜一段旁白 → TTS 合成 → `audio_tracks` 落库 + 音频落盘。
合成引擎走 `services/tts.py` 门面（默认**火山引擎豆包语音合成大模型**，见 `tts_volc.py`；
本机 CosyVoice 是退路）。本模块不关心是谁在念，只关心「哪一镜、念什么、念好了没」。

爸爸的原话：
    「再给加一个子页面用来生成 tts 的语音」
    「在参考脚本生成下面得有一个导出 需要生成 tts 语音的文案或者台词」
    → 导出产物的判断：「导出的东西可用给 tts 生成页面处理，生成每一段的 tts，还可以预览」
    → 切段粒度：「按镜头一段」

三个设计决定：

1. **落在 `audio_tracks`，不另起表。**
   这张表本来就是「成片的声轨」（kind / segment / url / duration / shot_id /
   is_ai_generated / sort_order / status），TTS 旁白正好是其中一类（kind='tts'）。
   与 P1「对齐已有 schema，别再造一套」的立场一致；只补了 6 个溯源列
   （见 store._EXTRA_COLUMNS 的 P5c 段）。

2. **台词来源只有一个：`reference_json.timeline[].subtitle_text`。**
   不在本模块里让用户另写一份文案 —— 否则参考脚本一改，两边就对不上了。
   「导出」这个动作的真实语义 = **把参考脚本的台词对齐进 audio_tracks**（幂等），
   并对台词变过的段落把旧音频置为过期（删文件 + 回 pending）。

3. **「这镜要不要配音」不猜。**
   ② 的 `diagnose_capabilities()` 已经按实测数据（素材有没有音轨 / 有没有人声 / 时长）
   算好了 `gaps[].action == 'tts'`。所以清单一律给**全部有台词的镜**，
   但把 ② 判定的缺口镜标 `need_tts=True`，前端默认勾它们、其余留给用户自己决定。

幂等键：(project_id, kind='tts', shot_seq)。
"""
import os
import re
import threading
import uuid
from datetime import datetime, timedelta

from loguru import logger

from services import tts as tts_svc
from services.aiclip import paths, probe, store

KIND = 'tts'

STATUS_PENDING = 'pending'
STATUS_GENERATING = 'generating'
STATUS_DONE = 'done'
STATUS_FAILED = 'failed'

# 单段台词上限（提示线，不阻断）。超过这个字数时前端会标出来，
# 建议回参考脚本里把这一镜拆开 —— 一镜一两句话才是短视频该有的节奏，
# 而且长了 TTS 也容易在语气上「念成一整段」而不是「一句一句说」。
MAX_CHARS = 300

# ★ generating 的陈旧阈值。单段合成实测只要 1~3 秒（火山 v3 流式），
#   超过这个时长还挂在 generating，一定是**进程被中断了**
#   （容器 restart / 后台批量线程被杀 / 连接挂死），不是"还在跑"。
#
#   为什么必须要这个：generating 是这套状态机里唯一的**非终态**，
#   而进程被杀时没人会去把它改回来 → 这一行永远显示「合成中」，
#   并且下面 generate_one 的「正在合成中」检查会**连手动重试都拒掉**，
#   用户唯一的出路是手改数据库。容器重启是我们每天的常规动作，所以这条必然踩。
STALE_GENERATING_SECONDS = 180


def _now():
    return datetime.now().isoformat(timespec='seconds')


def _stale_cutoff():
    """generating 行的「太老了」分界线（ISO 字符串，与 updated_at 同格式可直接比大小）。"""
    return (datetime.now() - timedelta(seconds=STALE_GENERATING_SECONDS)) \
        .isoformat(timespec='seconds')


def is_stale_generating(row):
    """一行是不是「被中断后卡死」的 generating。"""
    if not row or row.get('status') != STATUS_GENERATING:
        return False
    ts = row.get('updated_at')
    if not ts:
        return True                    # 时间都没有，宁可放行也不要永久卡死
    try:
        age = (datetime.now() - datetime.fromisoformat(str(ts))).total_seconds()
    except (TypeError, ValueError):
        return True
    return age > STALE_GENERATING_SECONDS


def reap_stale(pid):
    """把卡死的 generating 行放回 pending —— 打开页面即自愈。

    容器重启后必然产生这种行；不回收的话，它既不能重试、也永远不会自己好。
    """
    rows = store.fetch('audio_tracks',
                       "project_id=%s AND kind=%s AND status=%s",
                       [pid, KIND, STATUS_GENERATING])
    n = 0
    for r in rows:
        if is_stale_generating(r):
            store.update('audio_tracks', r['id'], {
                'status': STATUS_PENDING,
                'gen_error': '上次合成被中断（进程重启或任务中断），可重新生成',
                'updated_at': _now(),
            })
            n += 1
    if n:
        logger.warning('aiclip TTS 回收 {} 个卡死的 generating 行 ({})'.format(n, pid))
    return n


# ---------------------------------------------------------------------------
# 台词清洗
# ---------------------------------------------------------------------------
def clean_text(t):
    """字幕文案 → 可念的台词。

    字幕里的换行是**排版折行**，在语音里应该只是一个换气停顿；
    原样送进 TTS 会被当成句末，把一句话念成两句 —— 所以折叠成逗号。
    空白同理（字幕为对齐排的间距在语音里是噪音）。
    """
    s = (t or '').replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'\s*\n\s*', '，', s)
    s = re.sub(r'[ \t\u3000]+', '', s)
    s = re.sub(r'，{2,}', '，', s)
    return s.strip('，').strip()


def line_name(seq, text):
    """audio_tracks.name：给后端/日志一个能认出来的短标识。"""
    head = re.sub(r'[，。！？、,.!?]', ' ', text or '').strip()
    return '#{} {}'.format(seq, head[:14])


# ---------------------------------------------------------------------------
# 读：参考脚本 → TTS 清单（纯读，不写库）
# ---------------------------------------------------------------------------
def latest_reference(pid):
    rows = store.fetch(
        'frame_scripts', "project_id=%s AND `source`='reference'", [pid],
        order='version DESC', limit=1)
    return rows[0] if rows else None


def collect_lines(pid):
    """这条片子该配哪些旁白。

    Returns:
        {'lines': [...], 'meta': {...}}；没有参考脚本时 lines=[]。
    """
    row = latest_reference(pid)
    meta = {
        'reference_id': None, 'reference_version': None,
        'reference_status': None, 'reference_at': None,
        'shots_total': 0, 'shot_with_text': 0, 'need_tts': 0, 'skipped_no_text': 0,
    }
    if not row:
        return {'lines': [], 'meta': meta}

    ref = row.get('reference_json') or {}
    tl = ref.get('timeline') or []
    gaps = ref.get('gaps') or []
    meta.update({
        'reference_id': row.get('id'),
        'reference_version': row.get('version'),
        'reference_status': row.get('gen_status'),
        'reference_at': ref.get('_generated_at'),
        'shots_total': len(tl),
    })

    tts_seqs = {g.get('source_seq') for g in gaps
                if (g.get('action') or '') == 'tts' and g.get('source_seq') is not None}
    gap_by_seq = {g.get('source_seq'): g for g in gaps
                  if g.get('source_seq') is not None}

    # 参考镜 → frame_shots.id（TTS 段落要能挂回镜头，成片混音时按 shot 对齐）
    shot_ids = {}
    for s in store.query('SELECT `id`, `seq` FROM `frame_shots` WHERE script_id=%s',
                         [row.get('id')]):
        if s.get('seq') is not None:
            shot_ids[s['seq']] = s.get('id')

    lines = []
    skipped = 0
    for t in tl:
        text = clean_text(t.get('subtitle_text'))
        if not text:
            skipped += 1          # 没人声的镜（纯画面/音效）不需要旁白
            continue
        seq = t.get('seq')
        sseq = t.get('source_seq')
        need = sseq in tts_seqs
        g = gap_by_seq.get(sseq) if need else None
        try:
            dur_hint = max(0.0, float(t.get('end') or 0) - float(t.get('start') or 0))
        except (TypeError, ValueError):
            dur_hint = 0.0
        lines.append({
            'seq': seq,
            'source_seq': sseq,
            'shot_id': shot_ids.get(seq),
            'text': text,
            'chars': len(text),
            'start': t.get('start'),
            'end': t.get('end'),
            'duration_hint': round(dur_hint, 3),
            'band': t.get('band'),
            'material_id': t.get('material_id'),
            'need_tts': bool(need),
            'too_long': len(text) > MAX_CHARS,
            'gap': ({'need': g.get('need'), 'reason': g.get('reason'),
                     'suggestion': g.get('suggestion'), 'auto': bool(g.get('auto'))}
                    if g else None),
        })

    meta['shot_with_text'] = len(lines)
    meta['skipped_no_text'] = skipped
    meta['need_tts'] = sum(1 for x in lines if x['need_tts'])
    return {'lines': lines, 'meta': meta}


def list_tracks(pid):
    """已落库的 TTS 段，按 shot_seq 索引。"""
    rows = store.fetch('audio_tracks', 'project_id=%s AND kind=%s', [pid, KIND],
                       order='sort_order ASC')
    out = {}
    for r in rows:
        if r.get('shot_seq') is None:
            continue
        out[int(r['shot_seq'])] = r
    return out


def preview(pid):
    """清单 + 状态合并视图（GET /tts 的出参）。"""
    reap_stale(pid)          # 打开页面即自愈：把上次被中断的「合成中」放回 pending
    plan = collect_lines(pid)
    tracks = list_tracks(pid)
    segs = []
    stats = {'total': 0, 'done': 0, 'pending': 0, 'failed': 0, 'generating': 0,
             'chars': 0, 'audio_seconds': 0.0, 'too_long': 0, 'need_tts': 0}
    seen = set()
    for ln in plan['lines']:
        seq = int(ln['seq'])
        seen.add(seq)
        tr = tracks.get(seq) or {}
        item = dict(ln)
        item.update({
            'track_id': tr.get('id'),
            'status': tr.get('status'),
            'audio_url': tr.get('url') if tr.get('status') == STATUS_DONE else None,
            'audio_duration': float(tr.get('duration') or 0),
            'voice': tr.get('voice_id'),
            'rate': tr.get('speech_rate'),
            'gen_error': tr.get('gen_error'),
            'gen_at': tr.get('gen_at'),
            'synced': bool(tr),
        })
        segs.append(item)

        stats['total'] += 1
        stats['chars'] += ln['chars']
        if ln['too_long']:
            stats['too_long'] += 1
        if ln['need_tts']:
            stats['need_tts'] += 1
        st = item['status']
        if st == STATUS_DONE:
            stats['done'] += 1
            stats['audio_seconds'] += item['audio_duration']
        elif st == STATUS_FAILED:
            stats['failed'] += 1
        elif st == STATUS_GENERATING:
            stats['generating'] += 1
        else:
            stats['pending'] += 1
    stats['audio_seconds'] = round(stats['audio_seconds'], 2)

    return {
        'segments': segs,
        'stats': stats,
        'meta': plan['meta'],
        # 已落库、但参考脚本里已经没有的镜（参考脚本重生成过、还没重新导出）
        'orphan_seqs': sorted(k for k in tracks if k not in seen),
        'voices': tts_svc.get_voice_library(),
        'default_voice': tts_svc.default_voice(),
        'default_rate': tts_svc.default_rate(),
        'max_chars': MAX_CHARS,
        # 当前 TTS 供应商 + 配置状态（前端拿它显示「凭据没配」的告警横幅）
        'provider': tts_svc.status(),
        'batch': batch_state(pid),
    }


# ---------------------------------------------------------------------------
# 写：导出（参考脚本台词 → audio_tracks，幂等）
# ---------------------------------------------------------------------------
def drop_file(pid, tid):
    """删掉这一段的音频文件。

    扩展名随 TTS provider 变（火山 mp3 / CosyVoice wav），**不能拼** ——
    换过 provider 的项目里新旧两种扩展名会同时存在，拼错了就是「文件在却删不掉」。
    """
    fp = paths.find_tts_file(pid, tid)
    if fp and os.path.isfile(fp):
        try:
            os.remove(fp)
        except OSError as e:
            logger.warning('TTS 音频删除失败 {}: {}'.format(fp, e))


def sync(pid, owner_id=None):
    """「导出」：把参考脚本的台词对齐进 TTS 清单。

    幂等，且**台词改动是有后果的**：
      · 新增的镜 → 建行（pending）
      · 台词变了的镜 → 更新文本，旧音频删文件 + 回 pending（不许拿旧音频配新词）
      · 参考脚本里已消失的镜 → 删行 + 删文件
    """
    plan = collect_lines(pid)
    lines = plan['lines']
    tracks = list_tracks(pid)
    now = _now()
    added = updated = removed = 0
    seen = set()

    for ln in lines:
        seq = int(ln['seq'])
        seen.add(seq)
        cur = tracks.get(seq)

        if not cur:
            store.insert('audio_tracks', {
                'id': str(uuid.uuid4()),
                'project_id': pid,
                'kind': KIND,
                'segment': str(seq),
                'shot_seq': seq,
                'shot_id': ln.get('shot_id'),
                'name': line_name(seq, ln['text']),
                'text_content': ln['text'],
                'url': None,
                'volume': 1,
                'duration': 0,
                'start_offset': 0,
                'is_ai_generated': 1,
                'voice_id': tts_svc.default_voice(),
                'speech_rate': tts_svc.default_rate(),
                'status': STATUS_PENDING,
                'sort_order': seq,
                'source_material_id': ln.get('material_id'),
                'owner_id': owner_id,
                'created_at': now,
                'updated_at': now,
            })
            added += 1
            continue

        patch = {}
        if (cur.get('text_content') or '') != ln['text']:
            patch['text_content'] = ln['text']
            patch['name'] = line_name(seq, ln['text'])
            if cur.get('status') == STATUS_DONE:
                drop_file(pid, cur['id'])
                patch.update({'url': None, 'duration': 0, 'gen_at': None,
                              'status': STATUS_PENDING, 'gen_error': None})
        if (cur.get('shot_id') or None) != (ln.get('shot_id') or None):
            patch['shot_id'] = ln.get('shot_id')
        if (cur.get('source_material_id') or None) != (ln.get('material_id') or None):
            patch['source_material_id'] = ln.get('material_id')
        # ★ 换过 TTS provider 之后，老行的 voice_id（例如 CosyVoice 的「中文女」）
        #   在新 provider 的音色库里根本不存在 → 整行参数都作废，重置为当前默认。
        #   连 speech_rate 一起重置：0.88 在 CosyVoice 是「254 字/分」，
        #   在火山是另一个含义，留着就是两边不讨好的中间值。
        #   这和「台词改了就作废旧音频」是同一条规矩：**参数变了，结果就不能留**。
        if cur.get('voice_id') and not tts_svc.has_voice(cur['voice_id']):
            patch['voice_id'] = tts_svc.default_voice()
            patch['speech_rate'] = tts_svc.default_rate()
            if cur.get('status') in (STATUS_DONE, STATUS_FAILED):
                # failed 也要清：那条错误是上一家引擎报的，换引擎后它已经不准了，
                # 留着只会让人以为「新引擎也失败」。
                drop_file(pid, cur['id'])
                patch.update({'url': None, 'duration': 0, 'gen_at': None,
                              'status': STATUS_PENDING, 'gen_error': None})
        if patch:
            patch['updated_at'] = now
            store.update('audio_tracks', cur['id'], patch)
            updated += 1

    for seq, cur in tracks.items():
        if seq not in seen:
            drop_file(pid, cur['id'])
            store.execute('DELETE FROM `audio_tracks` WHERE `id`=%s', [cur['id']])
            removed += 1

    logger.info('aiclip TTS 导出 {}: +{} ~{} -{} (共 {} 段)'.format(
        pid, added, updated, removed, len(lines)))
    return {'added': added, 'updated': updated, 'removed': removed,
            'total': len(lines)}


# ---------------------------------------------------------------------------
# 合成
# ---------------------------------------------------------------------------
def audio_duration(fp):
    """ffprobe 实测时长（不猜 —— 与素材体检同一口径）。"""
    info = probe._ffprobe(fp)
    if not info:
        return 0.0
    try:
        return round(float((info.get('format') or {}).get('duration') or 0), 3)
    except (TypeError, ValueError):
        return 0.0


def friendly_error(e):
    """把底层异常翻译成「看得懂 + 知道去哪儿修」的话。

    各 provider 的文案在 `services/tts.py::friendly_error` 里 —— 因为「没配凭据」
    和「CosyVoice 没起」这两种最常见故障，修法完全不同，只有那一层知道是谁在合成。
    """
    return tts_svc.friendly_error(e)


def generate_one(pid, track, voice=None, rate=None, force=False):
    """合成一段（同步，通常几秒）。返回更新后的 track dict。"""
    tid = track.get('id')
    if not tid:
        raise ValueError('缺少音频段 id')
    text = clean_text(track.get('text_content'))
    if not text:
        raise ValueError('这一段没有台词，无法合成')
    if track.get('status') == STATUS_DONE and track.get('url') and not force:
        return track                     # 已经好了，别重复烧算力
    # 入参可能是别处读来的快照，重新拿一次最新的再判
    fresh = store.fetch_by_id('audio_tracks', tid) or track
    if fresh.get('status') == STATUS_GENERATING and not is_stale_generating(fresh):
        raise RuntimeError('这一段正在合成中')

    voice = (voice or '').strip() or track.get('voice_id') or tts_svc.default_voice()
    if not tts_svc.has_voice(voice):
        # 换过 provider 的老行（或前端传了不存在的音色）→ 落回当前默认，别拿无效音色去烧接口
        voice = tts_svc.default_voice()
    try:
        rate = float(rate if rate not in (None, '') else
                     (track.get('speech_rate') or tts_svc.default_rate()))
    except (TypeError, ValueError):
        rate = tts_svc.default_rate()

    # ★ 抢占用「比较并交换」，不是先读后写：单段按钮与批量任务可能同时打同一段，
    #   先读后写会两边都以为自己抢到了 → 同一句话被烧两遍、两个线程互相覆盖状态。
    #   CAS 让只有一方推进，另一方立刻拿到「已有人在处理」。
    #   条件里额外放行「陈旧的 generating」= 允许夺回被中断的行（见 STALE_GENERATING_SECONDS）。
    got = store.execute(
        'UPDATE `audio_tracks` SET `status`=%s, `gen_error`=NULL, `updated_at`=%s '
        'WHERE `id`=%s AND (`status` IS NULL OR `status`<>%s '
        'OR `updated_at` IS NULL OR `updated_at`<%s)',
        [STATUS_GENERATING, _now(), tid, STATUS_GENERATING, _stale_cutoff()])
    if not got:
        raise RuntimeError('这一段正在合成中（已有任务在处理）')
    paths.ensure_tts_dir(pid)
    # 换 provider 会换扩展名 —— 先把旧扩展名的残留删掉，避免目录里堆两个「同一段」
    drop_file(pid, tid)
    out = paths.tts_path(pid, tid, tts_svc.audio_ext())
    try:
        tts_svc.synthesize(text, out, voice=voice, rate=rate)
    except Exception as e:
        msg = friendly_error(e)
        store.update('audio_tracks', tid, {
            'status': STATUS_FAILED, 'gen_error': msg[:512],
            'url': None, 'duration': 0, 'updated_at': _now()})
        logger.error('aiclip TTS 合成失败 {} seq={}: {}'.format(
            pid, track.get('shot_seq'), e))
        raise RuntimeError(msg)

    dur = audio_duration(out)
    store.update('audio_tracks', tid, {
        'url': paths.tts_url(tid),
        'duration': dur,
        'voice_id': voice,
        'speech_rate': rate,
        'status': STATUS_DONE,
        'gen_error': None,
        'gen_at': _now(),
        'updated_at': _now(),
    })
    logger.info('aiclip TTS 完成 {} seq={} {}字 {:.2f}s {}'.format(
        pid, track.get('shot_seq'), len(text), dur, voice))
    return store.fetch_by_id('audio_tracks', tid)


# ---------------------------------------------------------------------------
# 批量（后台线程逐段串行 —— 别把 CosyVoice 打爆）
# ---------------------------------------------------------------------------
_batch = {}          # pid -> {total,done,failed,current,running,started_at,errors}
_batch_lock = threading.Lock()


def batch_state(pid):
    with _batch_lock:
        b = _batch.get(pid)
        if not b:
            return {'running': False}
        return dict(b)


def _batch_set(pid, **kw):
    with _batch_lock:
        b = _batch.get(pid)
        if b is None:
            b = {'total': 0, 'done': 0, 'failed': 0, 'current': None,
                 'running': True, 'started_at': _now(), 'errors': []}
            _batch[pid] = b
        b.update(kw)


def generate_batch(pid, ids=None, all_=False, voice=None, rate=None,
                   force=False):
    """批量合成。立即返回 (ok, why)，进度看 batch_state(pid)。"""
    with _batch_lock:
        if (_batch.get(pid) or {}).get('running'):
            return False, '这个项目正在批量合成中，等它跑完'

    tracks = list_tracks(pid)
    if all_:
        targets = [tracks[k] for k in sorted(tracks)]
    else:
        want = []
        for i in (ids or []):
            try:
                want.append(int(i))
            except (TypeError, ValueError):
                continue
        targets = [tracks[k] for k in sorted(set(want)) if k in tracks]
    if not force:
        targets = [t for t in targets if t.get('status') != STATUS_DONE]
    if not targets:
        return False, '没有需要合成的段落（都已经是「已生成」了）'

    _batch[pid] = {'total': len(targets), 'done': 0, 'failed': 0,
                   'current': None, 'running': True,
                   'started_at': _now(), 'errors': []}

    def work():
        for t in targets:
            _batch_set(pid, current=t.get('shot_seq'))
            try:
                generate_one(pid, t, voice=voice, rate=rate, force=force)
                with _batch_lock:
                    _batch[pid]['done'] = _batch[pid].get('done', 0) + 1
            except Exception as e:
                with _batch_lock:
                    b = _batch[pid]
                    b['failed'] = b.get('failed', 0) + 1
                    errs = b.setdefault('errors', [])
                    if len(errs) < 5:
                        errs.append('#{} {}'.format(t.get('shot_seq'), str(e)[:120]))
        _batch_set(pid, current=None, running=False, finished_at=_now())
        logger.info('aiclip TTS 批量结束 {}: {}'.format(pid, batch_state(pid)))

    threading.Thread(target=work, daemon=True,
                     name='tts-{}'.format(str(pid)[:8])).start()
    return True, None


def remove(pid, tid):
    """删一段（连带删 wav）。"""
    row = store.fetch_by_id('audio_tracks', tid)
    if not row or row.get('project_id') != pid or row.get('kind') != KIND:
        return False
    drop_file(pid, tid)
    store.execute('DELETE FROM `audio_tracks` WHERE `id`=%s', [tid])
    return True


def summary(pid):
    """轻量汇总（项目列表 / 项目头徽标用）。"""
    rows = store.fetch('audio_tracks', 'project_id=%s AND kind=%s', [pid, KIND])
    total = len(rows)
    done = sum(1 for r in rows if r.get('status') == STATUS_DONE)
    failed = sum(1 for r in rows if r.get('status') == STATUS_FAILED)
    gen = sum(1 for r in rows if r.get('status') == STATUS_GENERATING)
    return {
        'tts_count': total,
        'tts_done': done,
        'tts_failed': failed,
        'tts_generating': gen,
        'tts_pending': max(0, total - done - failed - gen),
    }
