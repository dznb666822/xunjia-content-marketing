# -*- coding: utf-8 -*-
"""AI 剪辑 · 参考脚本生成（SOP ②，LLM 第 1 次 —— 叙事层）。

三路输入汇成一份可照着剪的方案：

    剧本 script.json        剧本镜：画面 / 台词 / 景别 / 时长（script_io 产出）
    素材理解              可编排单元 units + 语义标签（P2 产出）
    用户需求 requirement   这条片子要什么效果

产出 `reference.json` + 人看版 md，形态对齐 `refs/reference_sample.md`
（那份是人写的爆款拆解报告，6 节：overall / 素材清单 / 逐镜时间轴 / 节奏 / 字幕规范 / 特效清单）。
**JSON 是权威副本，md 只是它的投影** —— 人审改要改 JSON，md 重新渲染即可。

三条不许违反的规则（写进 prompt，也在 validate 里兜底）：
1. **只能用素材清单里真实存在的 material_id** —— 编 ID 是最典型的 LLM 幻觉，
   而它一旦流到 LLM#2 就会变成"素材找不到"的成片级错误。validate 会剔除并记 issue。
2. **时间码必须落在该素材真实时长内** —— 素材时长是 ffprobe 实测的，不是猜的。
3. **剧本每一镜都要有交代** —— 要么匹配到素材，要么进 gaps（缺什么写真话），
   不允许静默丢镜（那会让成片少一段而没人知道）。

`VER` 约定同 P2：prompt / 结构有实质改动必须 +1，否则旧的 done 会被跳过不重跑。
"""
import json
import os
import re
import time
import uuid
from datetime import datetime
from functools import lru_cache

from loguru import logger

from services.aiclip import ark, store

VER = 'r1'

_SAMPLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'refs', 'reference_sample.md')

MAX_MATERIALS = 40          # 素材太多时按理解质量截断（有 units 的优先）
MAX_UNITS_PER_MATERIAL = 24  # 单素材单元太多时等距抽样，避免 prompt 被一条长素材吃满


def _now():
    return datetime.now().isoformat(timespec='seconds')


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default=None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _s(v, limit=None):
    t = '' if v is None else str(v).strip()
    return t[:limit] if limit else t


# ---------------------------------------------------------------------------
# few-shot：只学写法，不学内容
# ---------------------------------------------------------------------------
def _section(text, key, max_chars):
    i = text.find(key)
    if i < 0:
        return ''
    j = text.find('\n## ', i + len(key))
    seg = text[i:j] if j > 0 else text[i:]
    return seg[:max_chars].rstrip()


@lru_cache(maxsize=1)
def sample_digest():
    """摘出范例里最该学的三节。

    ⚠️ 范例的「素材清单」是**拆解别人视频**的口径（A/B/C/D/E 类 + 📷帧证据），
    与我们要产的「我方素材怎么排」不是一回事 —— 所以只取前三节里
    overall 的写法、时间轴表的列结构、节奏总结的语气，**不整段照搬**。
    """
    try:
        with open(_SAMPLE_PATH, encoding='utf-8') as f:
            txt = f.read()
    except OSError as e:
        logger.warning('aiclip reference: 读不到范例 {}'.format(e))
        return ''
    parts = [
        _section(txt, '## 一、视频 overall 分析', 900),
        _section(txt, '## 三、逐秒剪辑脚本', 2600),
        _section(txt, '## 四、节奏设计总结', 900),
    ]
    return '\n\n'.join(p for p in parts if p)


# ---------------------------------------------------------------------------
# 素材卡：把理解结果压成模型好读的文本
# ---------------------------------------------------------------------------
def _units_digest(units, limit=MAX_UNITS_PER_MATERIAL):
    """单元等距抽样（长素材动辄 31 段，全给会把 prompt 吃满）。"""
    us = [u for u in (units or []) if isinstance(u, dict)]
    if len(us) <= limit:
        return list(enumerate(us)), False
    step = len(us) / float(limit)
    picked = []
    for k in range(limit):
        idx = min(int(round(k * step)), len(us) - 1)
        if not picked or picked[-1][0] != idx:
            picked.append((idx, us[idx]))
    return picked, True


def material_card(m, idx):
    """单条素材 → 文本卡。idx 是给模型看的序号（1 起）。"""
    tags = m.get('tags') or {}
    units = m.get('seg_desc') or []
    sp = m.get('speech') or {}
    media = m.get('media') or {}
    dur = _f(m.get('duration'), 0.0)

    head = '[素材 {}] id={}'.format(idx, m.get('id'))
    lines = [head]
    lines.append('  名称：{}｜类型：{}｜时长：{:.1f}s｜理解形态：{}'.format(
        _s(m.get('name') or m.get('original_name'), 40) or '(未命名)',
        _s(m.get('type')) or '?', dur, _s(m.get('ai_classify')) or '?'))
    # ⚠️ 两行都要给：ffprobe 实测的「有没有音轨」和模型判断的「有没有人声」是**两件事**
    # （P2 实测过：3D 动画配乐素材有音轨但 has_speech=false）。模型据此判断要不要走 TTS。
    has_audio = media.get('has_audio')
    lines.append('  音轨：{}｜语音：{}'.format(
        '有' if has_audio else '无',
        '有' if sp.get('has_speech') else '无'))
    if tags.get('summary'):
        lines.append('  摘要：{}'.format(_s(tags['summary'], 160)))
    if tags.get('list'):
        lines.append('  标签：{}'.format('、'.join(str(t) for t in tags['list'][:10])))
    if tags.get('text_on_screen'):
        lines.append('  屏幕文字：{}'.format(_s(tags['text_on_screen'], 100)))
    if sp.get('has_speech') and sp.get('full_text'):
        lines.append('  转写（节选）：{}'.format(_s(sp['full_text'], 120)))
    if not units:
        lines.append('  ⚠️ 无可编排单元（理解未完成或该素材没有明显切分）'
                     '，只能整段使用')
        return '\n'.join(lines)

    picked, sampled = _units_digest(units)
    lines.append('  可编排单元{}：'.format('（等距抽样）' if sampled else ''))
    for real_idx, u in picked:
        st, en = _f(u.get('start')), _f(u.get('end'))
        seg = '    #{} {:.1f}–{:.1f}s｜画面：{}'.format(
            real_idx, st, en, _s(u.get('visual'), 70) or '-')
        if u.get('speech'):
            seg += '｜台词：{}'.format(_s(u['speech'], 50))
        uf = u.get('usable_for') or []
        if uf:
            seg += '｜适合：{}'.format('、'.join(str(x) for x in uf[:6]))
        lines.append(seg)
    return '\n'.join(lines)


def pick_materials(materials):
    """挑出能进 prompt 的素材：理解完的优先，没单元的排后面。"""
    def score(m):
        units = m.get('seg_desc') or []
        return (1 if m.get('classify_status') == 'done' else 0, len(units))
    ms = sorted([m for m in (materials or []) if m.get('duration') or m.get('type')],
                key=score, reverse=True)
    return ms[:MAX_MATERIALS]


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------
PROMPT_ROLE = """你是一位短视频剪辑方案设计师。把「剧本」「手上真实拍到的素材」「客户需求」三者对齐，产出一份能照着剪的参考脚本。

**五条硬规则（违反即失败）**
1. timeline 里的 material_id **只能**取自素材清单，一个字母都不许编。清单里没有的，写进 gaps。
2. in_offset / out_offset 必须落在该素材的真实时长内（清单给了时长），精确到 0.1s。
3. 素材清单里的「可编排单元 #n」是已实测的片段切分：选片段时 unit_index 填那个 n，
   并让 in/out 落在这个单元的 start–end 内（可以只用单元的一部分）。
4. 剧本的**每一镜**都要有交代：匹配到了就写 timeline 一条；匹配不到就写 gaps 一条，说明缺什么画面。
5. 台词可以直接用剧本原文，但字幕要按规范切短：单行不超过 12 个汉字，按语义断句。

**第六件事：把「这条片子还缺什么能力」也写清楚**
素材清单里每条都标了 `音轨：有/无`、`语音：有/无`。剧本某镜要人声、而选中的素材没有音轨或没有语音时，
不要硬剪，要在 gaps 里写一条 `kind="tts"` 的建议：用 TTS 按台词生成配音。
- 视觉缺：库里没有能表达这个画面的素材 → `kind="material"`，`action="shoot"`（建议补拍）
  或 `action="stock"`（建议找现成素材/图库）。
- 声音缺：素材静音但剧本要说话 → `kind="tts"`，`action="tts"`，suggestion 里把要生成的台词写出来。
- 特效缺：剧本要一个库里没有的贴纸/动效 → `kind="effect"`，`action="effect"`。
- 一个镜可能既有素材也有声音问题，就写多条。

**判断口径**
- 素材形态与剧本镜意图对不上时，宁可进 gaps，也不要硬塞一条不合适的素材。
- 素材不够时优先「一材多用」：同一素材的不同单元可以服务不同镜（但要在 match_reason 里说明差异）。
- 落位档 band：分镜型片子通常整镜全屏（C）；口播型素材贴片在上下带（A/B），全屏满幅要节制（C 档间隔 ≥25s）。
"""

OUTPUT_SCHEMA = """严格输出**一个 JSON 对象**（不要 markdown 围栏、不要解释文字）：

{
  "overall": {
    "video_type": "这条片子的类型定位",
    "duration": 总时长秒数,
    "ratio": "9:16",
    "core_structure": "核心结构，一句话",
    "rhythm": "整体节奏，分段描述"
  },
  "material_map": [
    {"role": "A", "label": "主轴/插播/佐证/产品/特效 之类", "note": "这类素材怎么用",
     "material_ids": ["清单里的真实 id"]}
  ],
  "timeline": [
    {
      "seq": 1,                       // 参考镜序号，从 1 连续
      "source_seq": 1,                // ★对应剧本第几镜
      "start": 0.0, "end": 3.0,       // 本镜在成片里的时间（秒）
      "material_id": "真实存在的 id",
      "unit_index": 0,                // 用了该素材的第几个可编排单元；没有单元就填 null
      "in_offset": 1.2, "out_offset": 4.2,
      "band": "C",                    // A上带 | B下带 | C全屏 | END覆盖层
      "visual_note": "剪辑手法/特效/转场",
      "subtitle_text": "这一镜的字幕文案（可多行，用 \\n 分隔）",
      "subtitle_style": "白字|黄字|公式|清单",
      "subtitle_position": "下1/3居中 之类",
      "audio_note": "音频/音效/节奏",
      "match_reason": "为什么选这条素材这个片段（一句话，便于人审）"
    }
  ],
  "rhythm_notes": ["可复用的剪辑逻辑，3–6 条"],
  "subtitle_spec": {
    "font": "...", "colors": ["普通叙述=...", "重点=...", "公式=..."],
    "position": "...", "animation": "...", "size": "..."
  },
  "effect_list": [{"name": "特效名", "at": "出现在哪个时间/镜", "note": "怎么做"}],
  "workbench": {
    "layer_plan": "进工作台后怎么分层：素材层/字幕层/遮罩层/转场各放哪、用哪类卡"
  },
  "gaps": [
    {
      "source_seq": 5,                 // 对应剧本第几镜
      "kind": "material",              // material 画面缺 | tts 人声缺 | effect 特效缺
      "need": "缺什么（画面/声音/特效，写具体）",
      "reason": "为什么现有素材替代不了",
      "action": "tts",                 // tts 生成配音 | shoot 补拍 | stock 找素材 | effect 做特效 | reuse 复用已选
      "suggestion": "具体怎么做 —— action=tts 时把要生成的台词原文写在这里",
      "priority": "high"               // high | mid | low
    }
  ]
}
"""


def build_prompt(project, shots, materials, requirement):
    """三路输入 → (blocks, 提示词文本)。blocks 直接喂 ark.call。"""
    named = [(m, i + 1) for i, m in enumerate(pick_materials(materials))]
    cards = '\n\n'.join(material_card(m, n) for m, n in named)

    script_lines = []
    for s in shots:
        bits = ['[镜{}] {:.1f}s'.format(s.get('seq'), _f(s.get('duration')))]
        meta = '／'.join(x for x in [_s(s.get('shot_size')), _s(s.get('angle')),
                                     _s(s.get('composition'))] if x)
        if meta:
            bits.append(meta)
        if s.get('camera_move'):
            bits.append('运镜：' + _s(s['camera_move']))
        script_lines.append(' '.join(bits))
        if s.get('content'):
            script_lines.append('   画面：{}'.format(_s(s['content'], 300)))
        if s.get('characters_scene'):
            script_lines.append('   人物&场景：{}'.format(_s(s['characters_scene'], 160)))
        if s.get('subtitle_text'):
            script_lines.append('   台词：{}'.format(_s(s['subtitle_text'], 300)))
        if s.get('audio_note'):
            script_lines.append('   音效：{}'.format(_s(s['audio_note'], 120)))
    total = sum(_f(s.get('duration')) for s in shots)

    kind_name = '口播型' if project.get('kind') == 'oral' else '分镜型'
    canvas = project.get('canvas') or {}
    body = """【项目】
名称：{}
片型：{}（{}）
画布：{}×{} @ {}fps

【客户需求】
{}

【剧本】共 {} 镜，总时长 {:.1f}s
{}

【可用素材】共 {} 条（已按理解质量排序；id 必须原样引用）
{}

【输出格式】
{}
""".format(
        _s(project.get('name'), 60) or '未命名', kind_name,
        '主轨口播直通 + 素材贴片层' if project.get('kind') == 'oral'
        else '无主轨，素材段即主轨，快切',
        canvas.get('w') or 1080, canvas.get('h') or 1920, canvas.get('fps') or 30,
        requirement or '（未填，按剧本本身的叙事逻辑来）',
        len(shots), total, '\n'.join(script_lines),
        len(named), cards, OUTPUT_SCHEMA)

    sample = sample_digest()
    if sample:
        body += """
【写法范例】下面是**另一条片子**的人工拆解报告节选。只学它的信息密度、术语与时间轴表的写法，
**不要**把里面的内容、素材、时间码搬过来：
---
{}
---
""".format(sample)

    return [{'type': 'input_text', 'text': PROMPT_ROLE + '\n\n' + body}]


# ---------------------------------------------------------------------------
# 能力诊断（确定性，不靠 LLM）
# ---------------------------------------------------------------------------
def diagnose_capabilities(clean_tl, shots, mat_index, gaps):
    """补齐 LLM 漏报的能力缺口 —— 依据是实测字段，不是推测。

    判据全部来自已有的确定性数据：
        media.has_audio     ffprobe 实测有没有音轨
        speech.has_speech   全模态模型判断有没有人声
        material.duration   ffprobe 实测时长

    为什么要代码算而不是全靠 LLM：**「有音轨」≠「有语音」** 这条 P2 踩过的坑，
    模型在长 prompt 里很容易糊过去；而"这镜要说话、选的素材是静音的"是成片级硬伤，
    必须有一道确定性的兜底。标 `auto=True` 让人审时知道这条是代码推出来的。
    """
    shot_by_seq = {s.get('seq'): s for s in (shots or [])}
    have = set()
    for g in (gaps or []):
        have.add((g.get('source_seq'), g.get('kind')))
    added = []
    for t in clean_tl:
        seq = t.get('source_seq')
        m = mat_index.get(t.get('material_id')) or {}
        media = m.get('media') or {}
        sp = m.get('speech') or {}
        line = _s((shot_by_seq.get(seq) or {}).get('subtitle_text'))

        # ① 声音：剧本要说话，素材却没有可用人声
        if line and (seq, 'tts') not in have:
            has_audio = bool(media.get('has_audio'))
            has_speech = bool(sp.get('has_speech'))
            if not has_speech:
                why = '素材没有音轨' if not has_audio else '素材有音轨但没有人声'
                added.append({
                    'source_seq': seq,
                    'kind': 'tts',
                    'need': '这镜台词「{}…」在选中素材里没有对应人声'.format(line[:18]),
                    'reason': '{}（音轨：{}｜语音：{}）'.format(
                        why, '有' if has_audio else '无', '有' if has_speech else '无'),
                    'action': 'tts',
                    'suggestion': '用 TTS 生成配音后贴到 {:.1f}–{:.1f}s；台词：{}'.format(
                        _f(t.get('start')), _f(t.get('end')), line[:200]),
                    'priority': 'high',
                    'auto': True,
                })
                have.add((seq, 'tts'))

        # ② 时长：素材比这一镜需要的还短
        if (seq, 'material') not in have:
            need = _f(t.get('end')) - _f(t.get('start'))
            avail = _f(m.get('duration'))
            if avail and need > avail + 0.3:
                added.append({
                    'source_seq': seq,
                    'kind': 'material',
                    'need': '这一镜需要 {:.1f}s，选中素材只有 {:.1f}s'.format(need, avail),
                    'reason': '素材时长不足（ffprobe 实测 {:.1f}s）→ 已按素材时长截断，'.format(avail)
                              + '缺口 {:.1f}s 需要补'.format(need - avail),
                    'action': 'reuse',
                    'suggestion': '优先把这一镜拆成两镜复用同素材的不同单元；仍不够则补拍',
                    'priority': 'mid',
                    'auto': True,
                })
                have.add((seq, 'material'))
    return added


# ---------------------------------------------------------------------------
# 校验闸门
# ---------------------------------------------------------------------------
def validate(ref, mat_index, shots):
    """把幻觉与越界拦在落库之前。返回 (issues, 修正后的 timeline, 修正后的 gaps)。

    mat_index: {material_id: material}
    """
    issues = []
    if not isinstance(ref, dict):
        return ['模型输出不是 JSON 对象'], [], []

    tl = ref.get('timeline')
    if not isinstance(tl, list) or not tl:
        return ['timeline 为空或不是数组'], [], []

    clean, seen, cursor = [], set(), 0.0
    for n, seg in enumerate(tl):
        if not isinstance(seg, dict):
            issues.append('#{} 不是对象，已丢弃'.format(n + 1))
            continue
        label = '镜{}'.format(seg.get('seq') or n + 1)
        mid = _s(seg.get('material_id'))
        m = mat_index.get(mid)
        if not m:
            issues.append('{} 引用了不存在的素材 id「{}」→ 已剔除该条'.format(label, mid or '(空)'))
            continue

        dur = _f(m.get('duration'), 0.0)
        ino = _f(seg.get('in_offset'), 0.0)
        outo = _f(seg.get('out_offset'), 0.0)
        if ino < 0:
            issues.append('{} 入点为负 → 归零'.format(label))
            ino = 0.0
        if outo <= ino:
            outo = round(min(dur or ino + 2.0, ino + 2.0), 2)
            issues.append('{} 出点 ≤ 入点 → 调整为 {:.1f}–{:.1f}s'.format(label, ino, outo))
        if dur and outo > dur + 0.06:
            issues.append('{} 出点 {:.2f}s 超出素材时长 {:.2f}s → 截断'.format(label, outo, dur))
            outo = round(dur, 2)
            if outo <= ino:
                ino = max(0.0, round(outo - 1.0, 2))
        if dur and ino > dur:
            issues.append('{} 入点 {:.2f}s 超出素材时长 {:.2f}s → 丢弃该条'.format(label, ino, dur))
            continue

        units = m.get('seg_desc') or []
        ui = _i(seg.get('unit_index'))
        if ui is not None and (ui < 0 or ui >= len(units)):
            issues.append('{} unit_index={} 越界（该素材 {} 个单元）→ 置空'.format(
                label, ui, len(units)))
            ui = None

        sseq = _i(seg.get('source_seq'))
        if sseq is not None:
            seen.add(sseq)

        st = _f(seg.get('start'), cursor)
        en = _f(seg.get('end'), st + (outo - ino))
        if en <= st:
            en = round(st + max(outo - ino, 0.5), 2)
        clean.append({
            'seq': _i(seg.get('seq'), len(clean) + 1),
            'source_seq': sseq,
            'start': round(st, 2),
            'end': round(en, 2),
            'material_id': mid,
            'unit_index': ui,
            'in_offset': round(ino, 2),
            'out_offset': round(outo, 2),
            'band': _s(seg.get('band'), 8) or 'C',
            'visual_note': _s(seg.get('visual_note'), 400),
            'subtitle_text': _s(seg.get('subtitle_text'), 600),
            'subtitle_style': _s(seg.get('subtitle_style'), 32),
            'subtitle_position': _s(seg.get('subtitle_position'), 64),
            'audio_note': _s(seg.get('audio_note'), 300),
            'match_reason': _s(seg.get('match_reason'), 300),
        })
        cursor = en

    if not clean:
        return issues + ['timeline 里没有任何一条可用素材引用'], [], []

    # gaps（LLM 报的）
    gaps = []
    raw_gaps = ref.get('gaps')
    if isinstance(raw_gaps, list):
        for g in raw_gaps:
            if not isinstance(g, dict):
                continue
            if not (_s(g.get('need')) or _s(g.get('reason'))):
                continue
            kind = _s(g.get('kind'), 16).lower() or 'material'
            if kind not in ('material', 'tts', 'effect'):
                kind = 'material'
            act = _s(g.get('action'), 16).lower()
            if act not in ('tts', 'shoot', 'stock', 'effect', 'reuse'):
                act = 'tts' if kind == 'tts' else 'shoot'
            pri = _s(g.get('priority'), 8).lower()
            gaps.append({
                'source_seq': _i(g.get('source_seq')),
                'kind': kind,
                'need': _s(g.get('need'), 300),
                'reason': _s(g.get('reason'), 300),
                'action': act,
                'suggestion': _s(g.get('suggestion'), 400),
                'priority': pri if pri in ('high', 'mid', 'low') else 'mid',
                'auto': False,
            })

    # 剧本镜既没进 timeline 也没进 gaps → 人工必须知道（否则成片悄悄少一段）
    covered = set(seen) | {g['source_seq'] for g in gaps if g['source_seq'] is not None}
    missing = [s.get('seq') for s in shots if s.get('seq') not in covered]
    if missing:
        issues.append('剧本镜 {} 既没匹配素材也没进 gaps'.format(
            '、'.join('#{}'.format(x) for x in missing[:12])))
        for seq in missing:
            gaps.append({'source_seq': seq, 'kind': 'material',
                         'need': '（模型未交代）', 'reason': 'timeline 与 gaps 都没覆盖这一镜',
                         'action': 'shoot', 'suggestion': '人工确认这一镜怎么处理',
                         'priority': 'high', 'auto': True})

    # ★ 确定性兜底：声音/时长这类硬伤不能只靠 LLM 自觉
    gaps.extend(diagnose_capabilities(clean, shots, mat_index, gaps))

    # ★ material_map 必须收敛到 timeline 真实用到的素材。
    # 实测过坑：模型会把「给我的可用素材清单」照抄成「本片用到的素材」——
    # 交付一份 12 镜却列出 15 条素材的分组表，人审时根本对不上。
    used = {t['material_id'] for t in clean}
    mm = ref.get('material_map')
    if isinstance(mm, list):
        fixed_mm = []
        for grp in mm:
            if not isinstance(grp, dict):
                continue
            raw_ids = grp.get('material_ids') or []
            keep = [x for x in raw_ids if _s(x) in used]
            dropped = len([x for x in raw_ids if _s(x)]) - len(keep)
            if not keep:
                issues.append('素材分组「{}」里的素材一条都没被 timeline 用到 → 已移除'.format(
                    _s(grp.get('label'), 30) or _s(grp.get('role'))))
                continue
            g = dict(grp)
            g['material_ids'] = keep
            if dropped > 0:
                issues.append('素材分组「{}」剔除了 {} 条未被使用的素材'.format(
                    _s(grp.get('label'), 30) or _s(grp.get('role')), dropped))
            fixed_mm.append(g)
        ref['material_map'] = fixed_mm

    return issues, clean, gaps


# ---------------------------------------------------------------------------
# md 投影
# ---------------------------------------------------------------------------
def render_md(ref, project, script, shots=None, issues=None):
    """reference.json → 人看版 md（对齐 refs/reference_sample.md 的六节）。"""
    ov = ref.get('overall') or {}
    tl = ref.get('timeline') or []
    mm = ref.get('material_map') or []
    gaps = ref.get('gaps') or []
    rs = ref.get('rhythm_notes') or []
    ss = ref.get('subtitle_spec') or {}
    el = ref.get('effect_list') or []
    wb = ref.get('workbench') or {}

    name = _s(project.get('name'), 60) or '未命名'
    kind = '口播型' if project.get('kind') == 'oral' else '分镜型'
    total = sum(_f(x.get('duration')) for x in (shots or [])) or _f(
        script.get('total_duration'))
    L = []
    L.append('# 参考脚本 · {}'.format(name))
    L.append('')
    L.append('> 片型 {}｜剧本 {} 镜 / {:.1f}s｜参考镜 {} 条｜素材分组 {} 类｜生成 {}'.format(
        kind, len(shots or []), total, len(tl), len(mm), _s(ref.get('_generated_at')) or '-'))
    L.append('> 由 LLM#1 生成（{}）。**这是参考脚本，确认后才进入方案编译（LLM#2）**。'.format(
        _s(ref.get('_model')) or 'ark'))
    L.append('')
    L.append('---')
    L.append('')

    L.append('## 一、视频 overall 分析')
    L.append('')
    for k, label in (('video_type', '视频类型'), ('duration', '视频时长'),
                     ('ratio', '画幅比例'), ('core_structure', '核心结构'),
                     ('rhythm', '整体节奏')):
        v = ov.get(k)
        if v in (None, ''):
            continue
        if k == 'duration':
            v = '{:.1f}s'.format(_f(v))
        L.append('- **{}**：{}'.format(label, v))
    L.append('')

    # 能不能进工作台预览 —— 判据是"有没有素材引用"，不是感觉
    tl_seqs = {t.get('source_seq') for t in tl}
    gap_seqs = sorted({g.get('source_seq') for g in gaps
                       if g.get('source_seq') is not None})
    blocked = [s for s in gap_seqs if s not in tl_seqs]
    L.append('### 可预览性（能不能进工作台）')
    L.append('')
    L.append('- ✅ **{} 条镜可以直接进工作台渲染**：都带 `material_id` + 入出点 + 落位档'.format(len(tl)))
    if blocked:
        L.append('- 🚧 **{} 条镜暂时渲染不了**：剧本镜 {} 还没素材，补完缺口再进预览'.format(
            len(blocked), '、'.join('#{}'.format(x) for x in blocked)))
    else:
        L.append('- ✅ 剧本每一镜都有素材落点，**可以整片进工作台预览**')
    if wb.get('layer_plan'):
        L.append('- **工作台分层建议**：{}'.format(wb['layer_plan']))
    L.append('')

    L.append('## 二、素材清单（按用途分组）')
    L.append('')
    for grp in mm:
        if not isinstance(grp, dict):
            continue
        L.append('### {} 类：{}'.format(_s(grp.get('role')) or '-', _s(grp.get('label')) or ''))
        L.append('')
        if grp.get('note'):
            L.append('- **用法**：{}'.format(grp['note']))
        ids = grp.get('material_ids') or []
        if ids:
            L.append('- **素材**：{}'.format('、'.join('`{}`'.format(_s(x, 40)) for x in ids)))
        L.append('')

    L.append('## 三、逐镜剪辑脚本')
    L.append('')
    L.append('| 镜 | 时间 | 剧本镜 | 素材 | 单元 | 入出点 | 落位 | 剪辑手法/特效 | 字幕 | 音频 |')
    L.append('|---|---|---|---|---|---|---|---|---|---|')
    for t in tl:
        sub = _s(t.get('subtitle_text')).replace('\n', ' / ')
        style = _s(t.get('subtitle_style'))
        pos = _s(t.get('subtitle_position'))
        subcell = '{}'.format(sub or '-')
        if style or pos:
            subcell += '（{}）'.format('·'.join(x for x in (style, pos) if x))
        L.append('| {} | {:.1f}-{:.1f}s | #{} | `{}` | {} | {:.1f}-{:.1f}s | {} | {} | {} | {} |'.format(
            t.get('seq'), _f(t.get('start')), _f(t.get('end')),
            t.get('source_seq') if t.get('source_seq') is not None else '-',
            _s(t.get('material_id'), 12),
            t.get('unit_index') if t.get('unit_index') is not None else '-',
            _f(t.get('in_offset')), _f(t.get('out_offset')),
            _s(t.get('band')),
            _s(t.get('visual_note'), 120) or '-',
            subcell, _s(t.get('audio_note'), 80) or '-'))
    L.append('')

    L.append('### 选材理由（人审用）')
    L.append('')
    for t in tl:
        if t.get('match_reason'):
            L.append('- **#{}(剧本#{})** {}'.format(
                t.get('seq'), t.get('source_seq'), t['match_reason']))
    L.append('')

    L.append('## 四、节奏设计总结')
    L.append('')
    for i, n in enumerate(rs, 1):
        L.append('{}. {}'.format(i, n))
    L.append('')

    L.append('## 五、字幕系统规范')
    L.append('')
    if ss.get('font'):
        L.append('- **字体**：{}'.format(ss['font']))
    colors = ss.get('colors')
    if colors:
        if not isinstance(colors, list):
            colors = [colors]
        for c in colors:
            L.append('- **配色**：{}'.format(c))
    for k, label in (('position', '位置'), ('animation', '动画'), ('size', '字号')):
        if ss.get(k):
            L.append('- **{}**：{}'.format(label, ss[k]))
    L.append('')

    L.append('## 六、特效清单')
    L.append('')
    for i, e in enumerate(el, 1):
        if isinstance(e, dict):
            L.append('{}. **{}**（{}）：{}'.format(
                i, _s(e.get('name')) or '-', _s(e.get('at')) or '-', _s(e.get('note')) or ''))
        else:
            L.append('{}. {}'.format(i, e))
    L.append('')

    if gaps:
        L.append('## 七、需要补的能力（可直接执行）')
        L.append('')
        L.append('> 标「自动诊断」的是代码按实测数据推出来的（素材有没有音轨/人声、时长够不够），')
        L.append('> 不是模型猜的 —— 这类硬伤漏一个，成片就哑一段或短一截。')
        L.append('')
        buckets = [
            ('tts', '🎙 配音：用 TTS 生成'),
            ('shoot', '🎬 需要补拍'),
            ('stock', '🔍 找现成素材 / 图库'),
            ('effect', '✨ 需要特效 / 贴纸'),
            ('reuse', '♻️ 复用已选素材即可'),
        ]
        known = {a for a, _ in buckets}
        for act, title in buckets:
            items = [g for g in gaps if g.get('action') == act]
            if not items:
                continue
            L.append('### {}（{} 条）'.format(title, len(items)))
            L.append('')
            for g in items:
                tag = '　`自动诊断`' if g.get('auto') else ''
                L.append('- **剧本镜 #{}**{}：{}'.format(
                    g.get('source_seq') if g.get('source_seq') is not None else '-',
                    tag, g.get('need') or '-'))
                if g.get('reason'):
                    L.append('  - 原因：{}'.format(g['reason']))
                if g.get('suggestion'):
                    L.append('  - **建议**：{}'.format(g['suggestion']))
            L.append('')
        rest = [g for g in gaps if g.get('action') not in known]
        if rest:
            L.append('### 其他（{} 条）'.format(len(rest)))
            L.append('')
            for g in rest:
                L.append('- **剧本镜 #{}**：{}'.format(
                    g.get('source_seq') if g.get('source_seq') is not None else '-',
                    g.get('need') or '-'))
            L.append('')

    if issues:
        L.append('## 八、自动校验发现的问题')
        L.append('')
        for x in issues:
            L.append('- ⚠️ {}'.format(x))
        L.append('')

    return '\n'.join(L)


# ---------------------------------------------------------------------------
# 落库
# ---------------------------------------------------------------------------
def _next_version(pid):
    rows = store.query(
        "SELECT MAX(`version`) AS v FROM `frame_scripts` "
        "WHERE project_id=%s AND `source`='reference'", [pid])
    v = (rows[0] or {}).get('v') if rows else None
    return int(v or 0) + 1


def _persist(pid, ref, md, script_id, script, issues, owner_id, requirement):
    """reference.json → frame_scripts(source='reference') + frame_shots(N)。"""
    sid = str(uuid.uuid4())
    now = _now()
    version = _next_version(pid)
    tl = ref.get('timeline') or []
    gaps = ref.get('gaps') or []
    gap_by_seq = {g.get('source_seq'): g for g in gaps if g.get('source_seq') is not None}

    store.insert('frame_scripts', {
        'id': sid,
        'project_id': pid,
        'version': version,
        'status': 'draft',              # ← 人审改后置 confirmed
        'source': 'reference',
        'generate_params': {'ver': VER, 'model': ark.MODEL,
                            'source_script_id': script_id},
        'shot_count': len(tl),
        'total_duration': round(sum(
            max(0.0, _f(t.get('end')) - _f(t.get('start'))) for t in tl), 3),
        'avg_shot_duration': round(
            sum(max(0.0, _f(t.get('end')) - _f(t.get('start'))) for t in tl)
            / len(tl), 3) if tl else 0,
        'supersedes_version': (version - 1) if version > 1 else None,
        'requirement': requirement or None,
        'reference_json': dict(ref, _issues=issues or [],
                               _script_id=script_id, _ver=VER),
        'reference_md': md,
        'gen_status': 'done',
        'gen_error': None,
        'self_check_passed': 1 if not [x for x in (issues or []) if '不存在' in x] else 0,
        'owner_id': owner_id,
        'created_at': now,
        'updated_at': now,
    })

    rows = []
    for t in tl:
        sseq = t.get('source_seq')
        g = gap_by_seq.get(sseq)
        rows.append({
            'id': str(uuid.uuid4()),
            'script_id': sid,
            'seq': t.get('seq'),
            'start_time': t.get('start'),
            'end_time': t.get('end'),
            'duration': round(max(0.0, _f(t.get('end')) - _f(t.get('start'))), 3),
            'content': t.get('visual_note') or '',
            'subtitle_text': t.get('subtitle_text') or None,
            'subtitle_style': t.get('subtitle_style') or None,
            'audio_note': t.get('audio_note') or None,
            'source_seq': sseq,
            'band': t.get('band') or None,
            'material_id': t.get('material_id') or None,
            'in_offset': t.get('in_offset'),
            'out_offset': t.get('out_offset'),
            'unit_index': t.get('unit_index'),
            'match_reason': t.get('match_reason') or None,
            'material_gap': 1 if (g and not t.get('material_id')) else 0,
            'gap_desc': (g or {}).get('need') if g else None,
            'role': 'reference',
            'status': 'draft',
            'owner_id': owner_id,
            'created_at': now,
            'updated_at': now,
        })
    shot_ids = {}
    for r in rows:
        store.insert('frame_shots', r)
        if r.get('source_seq') is not None:
            shot_ids.setdefault(r['source_seq'], r['id'])

    # 能力缺口 → material_list_items
    # 这 11 张表里的那张就是为这条闭环准备的（need_type/method/priority/resolve_*），
    # 所以缺口不能只活在 JSON 里 —— 落表之后才有「补齐 / 已解决」的流转。
    order = {'high': 0, 'mid': 1, 'low': 2}
    for n, g in enumerate(sorted(gaps, key=lambda x: order.get(x.get('priority'), 1)), 1):
        seq = g.get('source_seq')
        store.insert('material_list_items', {
            'id': str(uuid.uuid4()),
            'project_id': pid,
            'script_id': sid,
            'shot_id': shot_ids.get(seq),
            'material_id': None,
            'seq': n,
            'need_type': (g.get('kind') or 'material')[:64],
            'method': (g.get('action') or 'shoot')[:32],
            'priority': (g.get('priority') or 'mid')[:8],
            'status': 'pending',
            'resolve_by': (g.get('action') or 'shoot')[:32],
            'resolve_result': json.dumps({
                'need': g.get('need'),
                'reason': g.get('reason'),
                'suggestion': g.get('suggestion'),
                'auto': bool(g.get('auto')),
            }, ensure_ascii=False),
            'owner_id': owner_id,
            'created_at': now,
            'updated_at': now,
        })
    return sid


def generate(pid, requirement=None, force=False, owner_id=None):
    """主入口。返回 (reference_row, issues, error)。

    同步执行（一次 LLM 调用约 30–90s）。API 层用后台线程包它，前端轮询
    `gen_status`（generating → done/failed），与 P2 的理解状态机同一套口径。
    """
    from services.aiclip import materials as mat
    from services.aiclip import projects as pj

    project = pj.get_project(pid)
    if not project:
        return None, [], '项目不存在'
    script = store.fetch(
        'frame_scripts', "project_id=%s AND `source`='import'", [pid],
        order='version DESC', limit=1)
    if not script:
        return None, [], '还没有导入剧本'
    script = script[0]
    shots = store.fetch('frame_shots', 'script_id=%s', [script['id']], order='seq ASC')
    if not shots:
        return None, [], '剧本里没有镜'

    mats = mat.list_for_project(pid)
    understood = [m for m in mats if m.get('classify_status') == 'done']
    if not understood:
        return None, [], '项目里还没有已理解的素材（先去「素材理解」跑一遍）'

    req = (requirement if requirement is not None else script.get('requirement')) or ''
    if requirement is not None:
        store.update('frame_scripts', script['id'],
                     {'requirement': (requirement or '').strip() or None})

    blocks = build_prompt(project, shots, understood, req)
    t0 = time.time()
    data, usage, raw, err = ark.call(blocks, want_json=True, tag='reference')
    if err or not isinstance(data, dict):
        # 失败也要留痕，否则前端只看到「没反应」
        store.insert('frame_scripts', {
            'id': str(uuid.uuid4()), 'project_id': pid, 'version': _next_version(pid),
            'status': 'failed', 'source': 'reference',
            'generate_params': {'ver': VER, 'model': ark.MODEL,
                                'source_script_id': script['id']},
            'requirement': req or None,
            'gen_status': 'failed',
            'gen_error': (err or '模型返回不是 JSON')[:500],
            'gen_cost': dict(usage or {}, raw_preview=(raw or '')[:300]),
            'owner_id': owner_id, 'created_at': _now(), 'updated_at': _now(),
        })
        return None, [], '生成失败: {}'.format(err or '模型返回不是 JSON')

    mat_index = {m['id']: m for m in understood}
    issues, clean_tl, clean_gaps = validate(data, mat_index, shots)
    data['timeline'] = clean_tl
    data['gaps'] = clean_gaps
    data['_model'] = ark.MODEL
    data['_generated_at'] = _now()
    data['_ver'] = VER
    data['_seconds'] = round(time.time() - t0, 1)
    data['_usage'] = usage

    md = render_md(data, project, script, shots, issues)
    sid = _persist(pid, data, md, script['id'], script, issues, owner_id, req)

    # 补成本（_persist 里没带 usage，单独补一次）
    try:
        store.update('frame_scripts', sid, {'gen_cost': dict(usage or {})})
    except Exception as e:
        logger.warning('aiclip reference: 补 gen_cost 失败 {}'.format(e))

    row = store.fetch_by_id('frame_scripts', sid)
    logger.info('aiclip reference: 项目 {} 生成 {} 条参考镜 / {} 个问题 / {:.0f}s'.format(
        pid, len(clean_tl), len(issues), time.time() - t0))
    return row, issues, None


def reference_brief(row, full=False):
    if not row:
        return None
    ref = row.get('reference_json') or {}
    data = {
        'id': row['id'],
        'project_id': row.get('project_id'),
        'version': row.get('version'),
        'status': row.get('status'),
        'gen_status': row.get('gen_status'),
        'gen_error': row.get('gen_error'),
        'gen_cost': row.get('gen_cost'),
        'shot_count': row.get('shot_count'),
        'total_duration': row.get('total_duration'),
        'requirement': row.get('requirement'),
        'created_at': row.get('created_at'),
        'issues': ref.get('_issues') or [],
        'ver': ref.get('_ver'),
        'model': ref.get('_model'),
        'generated_at': ref.get('_generated_at'),
        'seconds': ref.get('_seconds'),
        'gap_count': len(ref.get('gaps') or []),
        'timeline_count': len(ref.get('timeline') or []),
    }
    # 能力缺口分类 + 可预览性（前端据此显示徽标和按钮态）
    gaps = ref.get('gaps') or []
    kinds = {}
    actions = {}
    for g in gaps:
        kinds[g.get('kind') or 'material'] = kinds.get(g.get('kind') or 'material', 0) + 1
        actions[g.get('action') or 'shoot'] = actions.get(g.get('action') or 'shoot', 0) + 1
    tl_seqs = {t.get('source_seq') for t in (ref.get('timeline') or [])}
    blocked = sorted({g.get('source_seq') for g in gaps
                      if g.get('source_seq') is not None and g['source_seq'] not in tl_seqs})
    data.update({
        'gap_kinds': kinds,
        'gap_actions': actions,
        'auto_gap_count': sum(1 for g in gaps if g.get('auto')),
        'blocked_seqs': blocked,
        'renderable': bool(ref.get('timeline')) and not blocked,
        'workbench': ref.get('workbench') or {},
    })
    if full:
        data['overall'] = ref.get('overall') or {}
        data['material_map'] = ref.get('material_map') or []
        data['timeline'] = ref.get('timeline') or []
        data['gaps'] = ref.get('gaps') or []
        data['rhythm_notes'] = ref.get('rhythm_notes') or []
        data['subtitle_spec'] = ref.get('subtitle_spec') or {}
        data['effect_list'] = ref.get('effect_list') or []
        data['md'] = row.get('reference_md') or ''
        data['raw'] = ref
    return data
