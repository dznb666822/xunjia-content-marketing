# -*- coding: utf-8 -*-
"""
宠物趋势预测 · 异步任务编排（供 web 端点调用）
"""
import threading
from datetime import datetime


_tasks = {}
_results = {}
_lock = threading.Lock()


def start_analysis(keyword):
    """启动某关键词的趋势分析（异步），返回 task_id。"""
    keyword = (keyword or '').strip()
    task_id = 'trend_{}_{}'.format(datetime.now().strftime('%Y%m%d%H%M%S'), keyword[:8] or 'x')
    with _lock:
        _tasks[task_id] = {
            'status': 'pending',
            'keyword': keyword,
            'message': '等待分析...',
            'created_at': datetime.now().isoformat(),
        }
    t = threading.Thread(target=_run, args=(task_id, keyword), daemon=True)
    t.start()
    return task_id


def _run(task_id, keyword):
    try:
        with _lock:
            _tasks[task_id]['status'] = 'running'
            _tasks[task_id]['message'] = '正在采集抖音数据...'

        from pet_trend import load_trend_config, load_fabric_kb
        from pet_trend.features import compute_features, collect_douyin, enrich_author_followers
        from pet_trend.output import format_output

        cfg = load_trend_config()
        fabric_kb = load_fabric_kb()
        works = collect_douyin(keyword, cfg)
        works = enrich_author_followers(works, cfg)

        with _lock:
            _tasks[task_id]['message'] = '正在计算特征因子...'

        features = compute_features(keyword, cfg=cfg, fabric_kb=fabric_kb, works=works)
        result = format_output(keyword, features, cfg=cfg, fabric_kb=fabric_kb, works=works)

        try:
            from pet_trend import timeseries
            timeseries.save_sample(
                keyword, features, result.get('group_scores') or {},
                result.get('trend_score', 0), result.get('lifecycle', ''))
        except Exception as _e:
            logger.warning('阶段 C 样本落库失败({}): {}'.format(keyword, _e))

        with _lock:
            _results[task_id] = result
            _tasks[task_id]['status'] = 'completed'
            _tasks[task_id]['message'] = '分析完成'
    except Exception as e:
        import traceback
        traceback.print_exc()
        with _lock:
            _tasks[task_id]['status'] = 'failed'
            _tasks[task_id]['message'] = '分析失败: {}'.format(str(e))


def get_status(task_id):
    with _lock:
        t = _tasks.get(task_id)
        return dict(t) if t else None


def get_result(task_id):
    with _lock:
        r = _results.get(task_id)
        return dict(r) if r else None
