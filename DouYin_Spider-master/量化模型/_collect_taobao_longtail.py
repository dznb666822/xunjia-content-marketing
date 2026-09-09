# -*- coding: utf-8 -*-
"""淘宝垂类词补采脚本（补齐趋势模型里缺失的 21 个垂类词淘宝价格带/销量数据）

用法：python _collect_taobao_longtail.py
RPA 非无头浏览器，串行逐词采集（每个词 1 页），避免冲突与频控。
"""
import os
import sys
import json
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from services import price_research

# 21 个垂类词（排除已采集的宽泛词「宠物衣服」「狗狗衣服」）
KEYWORDS = [
    '宠物羽绒马甲',
    '宠物四脚羽绒服',
    '宠物加绒连帽卫衣',
    '宠物缎面公主裙',
    '宠物洛丽塔裙',
    '宠物西装礼服',
    '宠物护肚针织毛衣',
    '宠物三防机能服',
    '宠物新中式',
    '宠物JK制服',
    '宠物小香风',
    '宠物老钱风',
    '宠物法式',
    '马尔济斯衣服',
    '雪纳瑞衣服',
    '约克夏衣服',
    '德文猫衣服',
    '无毛猫衣服',
    '宠物婚纱',
    '宠物拜年服',
    '宠物四脚防水雨衣',
]

PAGES = 1
SUMMARY_FILE = os.path.join(BASE, '_collect_taobao_longtail_result.json')


def _flush(*args):
    print(*args, flush=True)


def run_one(keyword):
    task_id = price_research.start_research(keyword, 'taobao', 1, PAGES)
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
    summary = {'keywords': [], 'started_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    for i, keyword in enumerate(KEYWORDS):
        r = run_one(keyword)
        summary['keywords'].append(r)
        if i < len(KEYWORDS) - 1:
            _flush('[sleep] keyword gap 15s')
            time.sleep(15)

    summary['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    _flush('ALL DONE -> ' + SUMMARY_FILE)
    _flush(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
