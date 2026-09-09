# -*- coding: utf-8 -*-
"""1688 供应商补采脚本（趋势模型阶段 B 供应链硬数据）

用法：
  python _collect_1688.py            # 采集 pet_trend.yaml 全部 keywords
  python _collect_1688.py 宠物羽绒马甲 宠物缎面公主裙   # 只采集指定关键词

每词采集 1 页（供应商数量足够计算 fabric_procurement，不必多页）。
"""
import os
import sys
import json
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from services import price_research

SUMMARY_FILE = os.path.join(BASE, '_collect_1688_result.json')
PAGES = 1

# 1688 是 B2B 平台，供应商标题偏宽泛，细分垂类词搜不到结果，故用宽泛品类词采集
DEFAULT_KEYWORDS = ['宠物衣服', '狗狗衣服', '宠物羽绒服', '宠物毛衣', '宠物汉服', '宠物高定']


def _flush(*args):
    print(*args, flush=True)


def run_one(keyword):
    task_id = price_research.start_research(keyword, '1688', 1, PAGES)
    _flush('[{}] start task={}'.format(keyword, task_id))
    status = 'running'
    last_progress = -1
    max_wait = PAGES * 90 + 60
    waited = 0
    while waited < max_wait:
        st = price_research.get_task_status(task_id)
        if not st:
            _flush('[{}] task not found, abort'.format(keyword))
            return {'keyword': keyword, 'status': 'missing', 'count': 0}
        status = st.get('status')
        progress = st.get('progress')
        if progress != last_progress:
            _flush('[{}] status={} progress={} msg={}'.format(
                keyword, status, progress, st.get('message')))
            last_progress = progress
        if status in ('completed', 'failed'):
            break
        time.sleep(5)
        waited += 5

    results = price_research.get_task_results(task_id) or []
    _flush('[{}] done status={} count={}'.format(keyword, status, len(results)))
    return {'keyword': keyword, 'status': status, 'count': len(results), 'task_id': task_id}


def main():
    keywords = list(DEFAULT_KEYWORDS)
    if len(sys.argv) > 1:
        keywords = sys.argv[1:]
    _flush('1688 补采关键词数:', len(keywords))

    summary = {'keywords': [], 'started_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    for i, kw in enumerate(keywords):
        r = run_one(kw)
        summary['keywords'].append(r)
        if i < len(keywords) - 1:
            _flush('[sleep] keyword gap 15s')
            time.sleep(15)

    summary['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    _flush('ALL DONE -> ' + SUMMARY_FILE)
    _flush(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
