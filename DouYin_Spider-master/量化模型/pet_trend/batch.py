# -*- coding: utf-8 -*-
"""
宠物趋势预测 · 批量分析（阶段 A 核心产出）

对配置里的全部关键词依次计算特征 + TrendScore + 七项输出，
按 TrendScore 降序返回，用于横向对比与选品决策。
"""
import random
import time

from loguru import logger

from pet_trend import load_trend_config, load_fabric_kb
from pet_trend.features import compute_features, collect_douyin, enrich_author_followers, load_taobao
from pet_trend.output import format_output


def run_batch(keywords=None, cfg=None, fabric_kb=None, max_author_enrich=None):
    """批量分析，返回按 TrendScore 降序的结果列表。"""
    if cfg is None:
        cfg = load_trend_config()
    if fabric_kb is None:
        fabric_kb = load_fabric_kb()
    if max_author_enrich is not None:
        cfg['douyin']['max_author_enrich'] = int(max_author_enrich)

    if keywords is None:
        keywords = cfg.get('keywords', [])

    results = []
    for i, kw in enumerate(keywords):
        if i > 0:
            # 关键词之间额外休息，降低抖音频控概率
            gap = random.uniform(10, 20)
            logger.info('关键词间隔 {}s（防频控）'.format(int(gap)))
            time.sleep(gap)
        logger.info('批量分析开始: {}'.format(kw))
        try:
            works = collect_douyin(kw, cfg)
            works = enrich_author_followers(works, cfg)
            taobao = load_taobao(kw)
            features = compute_features(
                kw, cfg=cfg, fabric_kb=fabric_kb, works=works, taobao_products=taobao, use_ai=True)
            result = format_output(kw, features, cfg=cfg, fabric_kb=fabric_kb, works=works)
            results.append(result)
            try:
                from pet_trend import timeseries
                timeseries.save_sample(
                    kw, features, result.get('group_scores') or {},
                    result.get('trend_score', 0), result.get('lifecycle', ''))
            except Exception as _e:
                logger.warning('阶段 C 样本落库失败({}): {}'.format(kw, _e))
            logger.info('批量分析完成: {} score={}'.format(kw, result.get('trend_score')))
        except Exception as e:
            logger.error('批量分析失败({}): {}'.format(kw, e))
            results.append({
                'trend_name': kw,
                'trend_score': 0.0,
                'lifecycle': '分析失败',
                'action': '重试',
                'error': str(e),
            })

    results.sort(key=lambda r: -(r.get('trend_score') or 0))
    return results


def to_table(results):
    """把结果列表转成可读的对比表（list[dict]）。"""
    rows = []
    for r in results:
        rows.append({
            'keyword': r.get('trend_name'),
            'trend_score': r.get('trend_score'),
            'lifecycle': r.get('lifecycle'),
            'action': r.get('action'),
            'burst_window': r.get('burst_window'),
            'douyin_works': (r.get('data_summary') or {}).get('douyin_works', 0),
            'taobao_products': (r.get('data_summary') or {}).get('taobao_products', 0),
            'bilibili_works': (r.get('data_summary') or {}).get('bilibili_works', 0),
            'suppliers': (r.get('data_summary') or {}).get('suppliers', 0),
            'top_hashtags': (r.get('elements') or {}).get('hashtags', [])[:3],
            'risks': r.get('risks', []),
        })
    return rows
