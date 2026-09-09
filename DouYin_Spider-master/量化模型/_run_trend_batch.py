# -*- coding: utf-8 -*-
"""批量趋势分析运行脚本：对全部关键词计算 TrendScore 并输出对比表。

用法：
    python _run_trend_batch.py [max_author_enrich]
"""
import os
import sys
import json

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from pet_trend.batch import run_batch, to_table

max_enrich = int(sys.argv[1]) if len(sys.argv) > 1 else 5

print('=== 批量趋势分析开始（作者补全上限={}）==='.format(max_enrich), flush=True)
results = run_batch(max_author_enrich=max_enrich)

table = to_table(results)
print('\n=== 趋势评分对比表 ===', flush=True)
print('{:<10} {:<8} {:<10} {:<8} {:<6} {:<6} {:<6} {:<6}'.format(
    '关键词', '得分', '生命周期', '动作', '抖音', '淘宝', 'B站', '1688'), flush=True)
for row in table:
    print('{:<10} {:<8} {:<10} {:<8} {:<6} {:<6} {:<6} {:<6}'.format(
        row['keyword'], row['trend_score'], row['lifecycle'], row['action'],
        row['douyin_works'], row['taobao_products'], row['bilibili_works'],
        row['suppliers']), flush=True)

out = {
    'results': results,
    'table': table,
}
path = os.path.join(BASE, '_trend_batch_result.json')
with open(path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('\ndone -> ' + path, flush=True)
