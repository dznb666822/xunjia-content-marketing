# -*- coding: utf-8 -*-
"""AI 漫剧设计中心 API。"""
from flask import Blueprint, request, jsonify
from loguru import logger

from services import comic_designer
from services import storage

bp = Blueprint('comic', __name__)


def _get_script_text(data):
    return (data.get('script_text') or '').strip()


@bp.route('/api/comic/art', methods=['POST'])
def api_comic_art():
    """阶段一：美术视觉资产（角色/场景/道具提示词）。"""
    data = request.get_json(silent=True) or {}
    script_text = _get_script_text(data)
    if not script_text:
        return jsonify({'success': False, 'error': '剧本内容不能为空'})
    try:
        record = comic_designer.design_art(data.get('design_id'), script_text)
        return jsonify({'success': True, 'data': {
            'design_id': record['id'],
            'art_result': record.get('art_result', ''),
        }})
    except Exception as e:
        logger.error('漫剧美术设计失败: {}'.format(e))
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/api/comic/storyboard', methods=['POST'])
def api_comic_storyboard():
    """阶段二：专业分镜表。"""
    data = request.get_json(silent=True) or {}
    script_text = _get_script_text(data)
    if not script_text:
        return jsonify({'success': False, 'error': '剧本内容不能为空'})
    try:
        record = comic_designer.design_storyboard(data.get('design_id'), script_text)
        return jsonify({'success': True, 'data': {
            'design_id': record['id'],
            'storyboard_result': record.get('storyboard_result', ''),
        }})
    except Exception as e:
        logger.error('漫剧分镜生成失败: {}'.format(e))
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/api/comic/video', methods=['POST'])
def api_comic_video():
    """阶段三：T2I 分镜图提示词 + Seedance 视频提示词。"""
    data = request.get_json(silent=True) or {}
    script_text = _get_script_text(data)
    if not script_text:
        return jsonify({'success': False, 'error': '剧本内容不能为空'})
    try:
        record = comic_designer.design_video(data.get('design_id'), script_text)
        return jsonify({'success': True, 'data': {
            'design_id': record['id'],
            'video_result': record.get('video_result', ''),
        }})
    except Exception as e:
        logger.error('漫剧视频提示词生成失败: {}'.format(e))
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/api/comic/history', methods=['GET'])
def api_comic_history():
    """设计历史列表。"""
    records = storage.load_all('comic_designs')
    records.sort(key=lambda r: r.get('updated_at') or '', reverse=True)
    return jsonify({'success': True, 'data': [comic_designer.to_public(r) for r in records]})


@bp.route('/api/comic/<design_id>', methods=['GET'])
def api_comic_detail(design_id):
    """单条设计详情（含三个阶段的完整结果）。"""
    record = storage.find_by_id('comic_designs', design_id)
    if record is None:
        return jsonify({'success': False, 'error': '记录不存在'})
    detail = comic_designer.to_public(record)
    detail['script_text'] = record.get('script_text', '')
    detail['art_result'] = record.get('art_result', '')
    detail['storyboard_result'] = record.get('storyboard_result', '')
    detail['video_result'] = record.get('video_result', '')
    return jsonify({'success': True, 'data': detail})


@bp.route('/api/comic/<design_id>', methods=['DELETE'])
def api_comic_delete(design_id):
    """删除一条设计记录。"""
    if storage.delete_one('comic_designs', design_id) is None:
        return jsonify({'success': False, 'error': '记录不存在或无权删除'})
    return jsonify({'success': True})
