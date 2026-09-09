# -*- coding: utf-8 -*-
"""阶段 B 端到端验证：B站采集 + 1688/小红书读取 + compute_features 接入"""
import os
import sys
import json

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from pet_trend import load_trend_config, load_fabric_kb
from pet_trend.sources import collect_bilibili, bilibili_heat, load_1688_suppliers, load_xiaohongshu
from pet_trend.features import compute_features, collect_douyin, enrich_author_followers, load_taobao
from pet_trend.output import format_output

cfg = load_trend_config()
fabric_kb = load_fabric_kb()
kw = '宠物衣服'

print('===== 1. B站采集 =====', flush=True)
bili = collect_bilibili(kw, cfg)
print('B站条数:', len(bili), flush=True)
if bili:
    print('B站样例:', json.dumps(bili[0], ensure_ascii=False)[:300], flush=True)
    print('B站热度 bilibili_heat:', round(bilibili_heat(bili), 4), flush=True)

print('\n===== 2. 1688 / 小红书读取（预期空）=====', flush=True)
print('1688供应商:', len(load_1688_suppliers(kw)), flush=True)
print('小红书笔记:', len(load_xiaohongshu(kw)), flush=True)

print('\n===== 3. compute_features 端到端（use_ai=False）=====', flush=True)
works = collect_douyin(kw, cfg)
works = enrich_author_followers(works, cfg)
taobao = load_taobao(kw)
feat = compute_features(kw, cfg=cfg, fabric_kb=fabric_kb, works=works,
                        taobao_products=taobao, bilibili_works=bili, use_ai=False)
print('counts:', {k: feat[k] for k in ('douyin_works', 'taobao_products', 'bilibili_works', 'suppliers')}, flush=True)
print('growth_momentum:', {k: round(v, 4) for k, v in feat['growth_momentum'].items() if k != '_raw'}, flush=True)
print('feasibility.fabric_procurement:', round(feat['feasibility']['fabric_procurement'], 4), flush=True)

result = format_output(kw, feat, cfg=cfg, fabric_kb=fabric_kb, works=works)
print('\ntrend_score:', result['trend_score'], flush=True)
print('data_summary:', result['data_summary'], flush=True)
print('\nSTAGE_B_OK', flush=True)
