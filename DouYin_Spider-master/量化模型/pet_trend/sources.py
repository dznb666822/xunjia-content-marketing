# -*- coding: utf-8 -*-
"""
宠物趋势预测 · 阶段 B 数据源

- B站：公开搜索接口（匿名 + buvid cookie + 频控重试），用于跨平台热度验证
- 1688：复用 services.price_research 的 RPA 采集（platform=1688），供应商数据落库后读取
- 小红书：人工导入（反爬强，不做自研爬虫），导入后从 xiaohongshu_import 表读取

所有函数返回 dict 列表，失败返回空列表（由上层回退静态值）。
"""
import math
import random
import time

from loguru import logger


def _clamp01(x):
    return max(0.0, min(1.0, float(x)))


# ---- B站 ----
def _bili_session():
    import requests
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/',
    })
    # 先访问首页获取 buvid cookie，否则搜索接口可能被拦截
    try:
        s.get('https://www.bilibili.com/', timeout=10)
    except Exception:
        pass
    return s


def _clean_html(text):
    import re
    return re.sub(r'<[^>]+>', '', text or '').strip()


def collect_bilibili(keyword, cfg):
    """B站视频搜索，返回 [{bvid,title,author,play,danmaku,favorites,like,comment,pubdate,duration,tag}]。"""
    bcfg = cfg.get('bilibili', {}) or {}
    if not bcfg.get('enabled', True):
        return []
    max_pages = int(bcfg.get('max_pages', 2))
    page_size = int(bcfg.get('page_size', 20))
    gap = bcfg.get('request_gap_seconds', [3, 6])
    session = _bili_session()
    results = []
    for page in range(1, max_pages + 1):
        url = 'https://api.bilibili.com/x/web-interface/search/type'
        params = {'search_type': 'video', 'keyword': keyword, 'page': page, 'page_size': page_size}
        try:
            r = session.get(url, params=params, timeout=15)
            data = r.json()
            if data.get('code') != 0:
                logger.warning('B站搜索第{}页失败({}): code={}'.format(page, keyword, data.get('code')))
                break
            for item in (data.get('data') or {}).get('result') or []:
                results.append({
                    'bvid': item.get('bvid', ''),
                    'title': _clean_html(item.get('title', '')),
                    'author': item.get('author', ''),
                    'play': item.get('play', 0) or 0,
                    'danmaku': item.get('danmaku', 0) or 0,
                    'favorites': item.get('favorites', 0) or 0,
                    'like': item.get('like', 0) or 0,
                    'comment': item.get('video_review', 0) or item.get('review', 0) or 0,
                    'pubdate': item.get('pubdate', 0) or 0,
                    'duration': item.get('duration', ''),
                    'tag': item.get('tag', ''),
                })
        except Exception as e:
            logger.warning('B站搜索第{}页异常({}): {}'.format(page, keyword, e))
            break
        if page < max_pages:
            time.sleep(random.uniform(gap[0], gap[1]))
    logger.info('B站采集 {}: {} 条视频'.format(keyword, len(results)))
    return results


def bilibili_heat(bili_works):
    """B站跨平台热度（0~1）：视频数量 + 平均播放量对数归一化。"""
    if not bili_works:
        return 0.5
    total_play = sum(w.get('play', 0) for w in bili_works)
    avg_play = total_play / max(len(bili_works), 1)
    count_score = _clamp01(len(bili_works) / 20.0)
    play_score = _clamp01(math.log10(avg_play + 1) / 5.0)
    return _clamp01(0.5 * count_score + 0.5 * play_score)


# ---- 1688 供应商 ----
def load_1688_suppliers(keyword=None):
    """从 price_research 表读取 platform=1688 的供应商商品。

    keyword 为 None 时返回全部（供应链能力全局共享，垂类词均可复用）。
    """
    from services.storage import load_all
    products = []
    try:
        items = load_all('price_research')
    except Exception as e:
        logger.warning('读取 1688 供应商失败: {}'.format(e))
        return products
    for item in items:
        if (item.get('platform') or '') != '1688':
            continue
        if keyword and (item.get('keyword') or '').strip() != keyword.strip():
            continue
        for p in item.get('products', []) or []:
            if isinstance(p, dict):
                products.append(p)
    return products


def supplier_procurement(suppliers):
    """把 1688 供应商数量映射为面料可采购性（0~1）。无数据返回 None（回退静态）。"""
    if not suppliers:
        return None
    shops = set()
    for p in suppliers:
        shop = (p.get('item_shop') or p.get('item_name') or '').strip()
        if shop:
            shops.add(shop)
    n = len(shops)
    return _clamp01(0.4 + 0.6 * min(n, 30) / 30.0)


# ---- 小红书（人工导入） ----
def load_xiaohongshu(keyword):
    """从 xiaohongshu_import 表读取人工导入的小红书笔记。"""
    from services.storage import load_all
    notes = []
    try:
        items = load_all('xiaohongshu_import')
    except Exception as e:
        logger.warning('读取小红书导入数据失败: {}'.format(e))
        return notes
    for item in items:
        if (item.get('keyword') or '').strip() != keyword.strip():
            continue
        for n in item.get('notes', []) or []:
            if isinstance(n, dict):
                notes.append(n)
    return notes


def import_xiaohongshu(keyword, notes):
    """人工导入小红书笔记并落库。

    notes: [{title, likes, collects, comments}]，字段缺失按 0 处理。
    """
    import uuid
    from datetime import datetime
    from services.storage import save_one
    if not notes:
        return None
    record_id = 'xhs_{}_{}'.format(datetime.now().strftime('%Y%m%d%H%M%S'), uuid.uuid4().hex[:6])
    save_one('xiaohongshu_import', {
        'id': record_id,
        'keyword': keyword.strip(),
        'notes': notes,
        'imported_at': datetime.now().isoformat(),
        'created_at': datetime.now().isoformat(),
    })
    logger.info('小红书笔记已导入 {}: {} 条'.format(keyword, len(notes)))
    return record_id
