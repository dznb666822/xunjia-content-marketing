# -*- coding: utf-8 -*-
"""淘宝多关键词多页补采脚本（用于趋势模型阶段 A 的数据打底）

用法：python _collect_taobao.py
按顺序抓取多个关键词、多页商品，逐关键词等待完成后再下一个（RPA 非无头浏览器，串行避免冲突）。
"""
import os
import sys
import json
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from services import price_research

# 关键词与页数（Z.paw 高端宠物服装趋势相关词）
KEYWORDS = [
    ('宠物衣服', 3),
    ('狗狗衣服', 2),
    ('宠物羽绒服', 2),
    ('宠物毛衣', 2),
    ('宠物汉服', 2),
    ('宠物高定', 2),
]

SUMMARY_FILE = os.path.join(BASE, '_collect_taobao_result.json')


def _flush(*args):
    print(*args, flush=True)


def run_one(keyword, pages):
    task_id = price_research.start_research(keyword, 'taobao', 1, pages)
    _flush('[{}] start task={} pages={}'.format(keyword, task_id, pages))
    status = 'running'
    last_progress = -1
    # 单页约 40~60s，多页再加页面间延时，预留充足轮询次数
    max_wait = pages * 90 + 60
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
    summary = {'keywords': [], 'started_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    for keyword, pages in KEYWORDS:
        r = run_one(keyword, pages)
        summary['keywords'].append(r)
        # 关键词之间额外休息，进一步降低频控概率
        if keyword != KEYWORDS[-1][0]:
            _flush('[sleep] keyword gap 15s')
            time.sleep(15)

    summary['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    _flush('ALL DONE -> ' + SUMMARY_FILE)
    _flush(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
