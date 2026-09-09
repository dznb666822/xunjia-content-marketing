# -*- coding: utf-8 -*-
"""
AI 漫剧设计中心服务：小说/剧本 → 三阶段视觉生产工作流。

阶段一（美术指导）：扫描全剧本，输出角色/场景/道具的标准化视觉资产提示词
阶段二（分镜总导演）：将剧本转化为专业分镜表（镜号/景别/运镜/画面/台词/音效/时长）
阶段三（视频提示词）：为每个分镜生成 T2I 起始帧提示词 + Seedance 2.0 视频提示词

三个阶段的角色提示词模板位于 config/comic_design/ 下，由用户可自行修改。
"""
import os
import uuid
from datetime import datetime

from loguru import logger

from services.script_generator import _call_ai
from services import storage

_COMIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'config', 'comic_design')

# 单阶段 AI 生成的超时时间（秒）
_STAGE_TIMEOUT = 600


def _load_prompt(filename):
    """读取角色提示词模板。"""
    path = os.path.join(_COMIC_DIR, filename)
    with open(path, encoding='utf-8') as f:
        return f.read()


def _make_title(script_text):
    """从剧本第一行非空文本提取标题。"""
    for line in (script_text or '').splitlines():
        line = line.strip().lstrip('#').strip()
        if line:
            return line[:40]
    return '未命名漫剧'


def _build_prompt(role_prompt, script_text, extra_context=''):
    """角色模板 + 执行指令 + 前置阶段成果 + 剧本 → 单条 user prompt。"""
    parts = [
        role_prompt,
        '',
        '---',
        '',
        '【任务】请立即基于下方剧本内容，执行你在上方角色设定中的全部工作流程，直接输出最终成果。',
        '注意：不要输出"已就位"之类的初始化应答，不要等待用户再次输入，一次性输出完整结果。',
    ]
    if extra_context:
        parts.append('')
        parts.append('【前置阶段成果】（作为本次工作的参考上下文，保持角色与场景视觉一致性）')
        parts.append(extra_context)
    parts.append('')
    parts.append('【剧本内容】')
    parts.append(script_text.strip())
    return '\n'.join(parts)


def _get_or_create(design_id, script_text):
    """获取设计记录；不存在则新建。"""
    if design_id:
        record = storage.find_by_id('comic_designs', design_id)
        if record is not None:
            if script_text and script_text != record.get('script_text'):
                storage.update_one('comic_designs', design_id, {
                    'script_text': script_text, 'updated_at': datetime.now().isoformat()})
                record['script_text'] = script_text
            return record
    now = datetime.now().isoformat()
    record = {
        'id': str(uuid.uuid4()),
        'title': _make_title(script_text),
        'script_text': script_text,
        'art_result': '',
        'storyboard_result': '',
        'video_result': '',
        'created_at': now,
        'updated_at': now,
    }
    storage.save_one('comic_designs', record)
    return record


def _run_stage(record, field, prompt):
    """调用 AI 执行单阶段并落库。"""
    logger.info('漫剧设计阶段 {} 开始, design_id={}'.format(field, record['id']))
    result = _call_ai(prompt, timeout=_STAGE_TIMEOUT)
    if not result or not result.strip():
        raise ValueError('AI 返回结果为空')
    storage.update_one('comic_designs', record['id'], {
        field: result, 'updated_at': datetime.now().isoformat()})
    record[field] = result
    logger.info('漫剧设计阶段 {} 完成, 长度={}'.format(field, len(result)))
    return record


def design_art(design_id, script_text):
    """阶段一：美术视觉资产（角色/场景/道具提示词）。"""
    record = _get_or_create(design_id, script_text)
    prompt = _build_prompt(_load_prompt('art_director.txt'), script_text)
    return _run_stage(record, 'art_result', prompt)


def design_storyboard(design_id, script_text):
    """阶段二：专业分镜表。"""
    record = _get_or_create(design_id, script_text)
    if not record.get('art_result'):
        raise ValueError('请先完成阶段一（美术视觉资产）生成分镜的视觉参考')
    prompt = _build_prompt(
        _load_prompt('storyboard.txt'), script_text,
        extra_context=record['art_result'])
    return _run_stage(record, 'storyboard_result', prompt)


def design_video(design_id, script_text):
    """阶段三：T2I 分镜图提示词 + Seedance 2.0 视频提示词。"""
    record = _get_or_create(design_id, script_text)
    if not record.get('storyboard_result'):
        raise ValueError('请先完成阶段二（分镜表）生成视频提示词的依据')
    extra = record['storyboard_result']
    if record.get('art_result'):
        extra = record['art_result'] + '\n\n---\n\n' + extra
    prompt = _build_prompt(
        _load_prompt('video_prompt.txt'), script_text, extra_context=extra)
    return _run_stage(record, 'video_result', prompt)


def to_public(record):
    """记录的对外展示形式（列表用，不含长文本）。"""
    return {
        'id': record.get('id'),
        'title': record.get('title'),
        'created_at': record.get('created_at'),
        'updated_at': record.get('updated_at'),
        'has_art': bool(record.get('art_result')),
        'has_storyboard': bool(record.get('storyboard_result')),
        'has_video': bool(record.get('video_result')),
    }
