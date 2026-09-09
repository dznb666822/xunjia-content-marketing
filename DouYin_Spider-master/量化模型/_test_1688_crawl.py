# -*- coding: utf-8 -*-
"""单关键词 1688 采集并打印结果，用于验证新版提取逻辑。"""
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from services import price_research

kw = '宠物衣服'
task_id = price_research.start_research(kw, '1688', 1, 1)
print('[{}] task={}'.format(kw, task_id), flush=True)

status = 'running'
waited = 0
while waited < 240:
    st = price_research.get_task_status(task_id)
    if st:
        status = st.get('status')
        if status in ('completed', 'failed'):
            break
    time.sleep(5)
    waited += 5

results = price_research.get_task_results(task_id) or []
print('status={} count={}'.format(status, len(results)), flush=True)

shops = {}
for p in results:
    name = (p.get('item_name') or '')[:40]
    price = (p.get('item_price') or '').strip()
    shop = (p.get('item_shop') or '').strip()
    shops[shop] = shops.get(shop, 0) + 1
    print(' - [{:<8}] {:<20} | {}'.format(price, shop[:18], name), flush=True)

print('distinct shops =', len(shops), flush=True)
for s, c in shops.items():
    print('  shop[{}]: {}'.format(c, s), flush=True)
