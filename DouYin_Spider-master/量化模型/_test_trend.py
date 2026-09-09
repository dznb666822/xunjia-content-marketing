# -*- coding: utf-8 -*-
"""阶段 A 功能测试：用真实抖音 + 淘宝数据跑通整条流水线（跳过 AI，减少请求）"""
import os
import sys
import json

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from pet_trend import load_trend_config, load_fabric_kb
from pet_trend.features import compute_features, collect_douyin, enrich_author_followers, load_taobao
from pet_trend.model import compute_trend_score
from pet_trend.output import format_output

cfg = load_trend_config()
# 测试：降低作者补全数量，加速
cfg['douyin']['max_author_enrich'] = 3
cfg['douyin']['max_pages'] = 2

fabric_kb = load_fabric_kb()

keyword = '宠物衣服'
print('=== 读取淘宝数据 ===', flush=True)
taobao = load_taobao(keyword)
print('taobao products:', len(taobao), flush=True)
if taobao:
    print('taobao sample:', json.dumps(taobao[0], ensure_ascii=False)[:200], flush=True)

print('=== 采集抖音数据 ===', flush=True)
works = collect_douyin(keyword, cfg)
print('douyin works:', len(works), flush=True)
works = enrich_author_followers(works, cfg)

print('=== 计算特征 ===', flush=True)
features = compute_features(keyword, cfg=cfg, fabric_kb=fabric_kb, works=works, taobao_products=taobao, use_ai=False)

print('=== 计算 TrendScore ===', flush=True)
score, group_scores = compute_trend_score(features, cfg)
print('TrendScore:', round(score, 4), flush=True)
print('group_scores:', json.dumps({k: round(v, 4) for k, v in group_scores.items()}, ensure_ascii=False), flush=True)

print('=== 七项输出 ===', flush=True)
result = format_output(keyword, features, cfg=cfg, fabric_kb=fabric_kb, works=works)
print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)

with open(os.path.join(BASE, '_test_trend_result.json'), 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('done -> _test_trend_result.json', flush=True)
