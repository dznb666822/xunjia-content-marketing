# -*- coding: utf-8 -*-
"""阶段 C 启动脚本：落库趋势结果样本 + XGBoost 训练 dry-run。

用法：
    python _run_stage_c.py                  # 用默认 _trend_batch_result.json 落库并训练
    python _run_stage_c.py <结果文件.json>   # 指定结果文件
    python _run_stage_c.py --clear          # 先清空 trend_samples 再落库
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from services.storage import load_all, delete_one
from pet_trend import timeseries

RESULT_FILE = os.path.join(BASE, '_trend_batch_result.json')


def clear_samples():
    for s in load_all(timeseries.ENTITY):
        delete_one(timeseries.ENTITY, s['id'])


def seed_from_result(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    results = data.get('results', []) if isinstance(data, dict) else data
    seeded = 0
    for r in results:
        name = r.get('trend_name')
        if not name:
            continue
        ds = r.get('data_summary') or {}
        features = {
            'keyword': name,
            'douyin_works': ds.get('douyin_works', 0),
            'taobao_products': ds.get('taobao_products', 0),
            'bilibili_works': ds.get('bilibili_works', 0),
            'suppliers': ds.get('suppliers', 0),
        }
        timeseries.save_sample(
            name, features, r.get('group_scores') or {},
            r.get('trend_score', 0), r.get('lifecycle', ''))
        seeded += 1
    return seeded


def main():
    args = sys.argv[1:]
    clear = '--clear' in args
    files = [a for a in args if not a.startswith('--')]
    path = files[0] if files else RESULT_FILE

    if clear:
        clear_samples()
        print('已清空 trend_samples')

    if not os.path.exists(path):
        print('结果文件不存在: {}'.format(path))
        print('提示：先跑 _run_trend_batch.py 生成结果，或等待后台重跑完成。')
        return

    seeded = seed_from_result(path)
    total = len(load_all(timeseries.ENTITY))
    labeled = timeseries.labeled_count()
    print('已落库 {} 条样本，累计 {} 条，真实标签 {} 条'.format(seeded, total, labeled))

    print('--- 阶段 C 训练 dry-run（weak_label=阶段一分数分桶） ---')
    res = timeseries.train_stage_c(weak_label=True)
    for k, v in res.items():
        print('  {}: {}'.format(k, v))


if __name__ == '__main__':
    main()
