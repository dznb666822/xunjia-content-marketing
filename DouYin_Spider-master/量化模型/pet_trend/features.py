# -*- coding: utf-8 -*-
"""
宠物趋势预测 · 特征因子计算（阶段 A）

数据来源（严格对应方案文档 §3 的可得因子）：
- 抖音：dy_apis.douyin_api（搜索作品 + 作者信息二次查询）
- 淘宝：MySQL price_research 表（services.price_research 采集）
- AI：豆包 Seed 2.0（风格迁移 / 噪声等兜底，失败时回退静态值）
- 知识库：config/pet_fabric_kb.yaml（可行性因子）

所有因子输出均归一化到 0~1。
"""
import json
import math
import os
import random
import time
from datetime import datetime

from loguru import logger

from pet_trend import sources

# ---- 抖音鉴权（懒加载 + 缓存） ----
_auth = None


def _get_auth():
    global _auth
    if _auth is not None:
        return _auth
    from dotenv import load_dotenv
    load_dotenv()
    from builder.auth import DouyinAuth
    auth = DouyinAuth()
    auth.perepare_auth(os.getenv('DY_COOKIES', ''))
    auth.ticket = os.getenv('DY_TICKET', '')
    auth.ts_sign = os.getenv('DY_TS_SIGN', '')
    auth.client_cert = os.getenv('DY_CLIENT_CERT', '')
    auth.private_key = os.getenv('DY_PRIVATE_KEY', '')
    _auth = auth
    return _auth


# ---- AI 兜底调用 ----
def _call_ai(prompt, timeout=90):
    """调用豆包 Seed 2.0，返回文本；失败返回空串（由上层回退静态值）。"""
    import requests
    api_url = os.getenv('AI_API_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    api_key = os.getenv('AI_API_KEY', os.getenv('ARK_API_KEY', ''))
    model = os.getenv('AI_MODEL', 'doubao-seed-2-0-pro-260215')
    headers = {'Authorization': 'Bearer {}'.format(api_key), 'Content-Type': 'application/json'}
    payload = {'model': model, 'input': [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]}
    try:
        resp = requests.post('{}/responses'.format(api_url), json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get('output', []):
            for c in item.get('content', []):
                text = c.get('text', '')
                if text:
                    return text.strip()
        for item in data.get('output', []):
            for s in item.get('summary', []):
                text = s.get('text', '')
                if text:
                    return text.strip()
    except Exception as e:
        logger.warning('趋势 AI 调用失败，回退静态值: {}'.format(e))
    return ''


# ---- 归一化工具 ----
def _clamp01(x):
    return max(0.0, min(1.0, float(x)))


def _growth_norm(g):
    """把增速（-inf..inf）映射到 0~1：0 增速 -> 0.5，正增长 -> >0.5。"""
    return _clamp01((g + 1.0) / 2.0)


def _parse_price(price_str):
    """把 '¥41' / '128' / '¥1,299' 解析为 float，失败返回 None。"""
    if price_str is None:
        return None
    s = str(price_str).strip()
    if not s:
        return None
    s = s.replace('¥', '').replace('￥', '').replace(',', '').replace('元', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


# ---- 抖音采集 ----
def _extract_work(aweme):
    author = aweme.get('author') or {}
    stats = aweme.get('statistics') or {}
    hashtags = []
    for te in aweme.get('text_extra') or []:
        name = te.get('hashtag_name') if isinstance(te, dict) else None
        if name:
            hashtags.append(name)
    return {
        'aweme_id': aweme.get('aweme_id'),
        'desc': aweme.get('desc', '') or '',
        'create_time': aweme.get('create_time', 0) or 0,
        'digg_count': stats.get('digg_count', 0) or 0,
        'comment_count': stats.get('comment_count', 0) or 0,
        'share_count': stats.get('share_count', 0) or 0,
        'collect_count': stats.get('collect_count', 0) or 0,
        'author_nickname': author.get('nickname', '') or '',
        'author_sec_uid': author.get('sec_uid', '') or '',
        'author_follower_count': author.get('follower_count', 0) or 0,
        'hashtags': hashtags,
    }


def _search_douyin_page(auth, keyword, sort_type, publish_time, offset, retries=3, backoff=8):
    """搜索单页，空结果退避重试。

    抖音对连续搜索会做风控，间歇性返回空 data（status_code 仍为 0、不抛异常），
    不重试会把被风控的词误记为 0 条。
    """
    from dy_apis.douyin_api import DouyinAPI
    for attempt in range(retries):
        try:
            resp = DouyinAPI.search_general_work(
                auth, keyword, sort_type=sort_type, publish_time=publish_time, offset=offset)
        except Exception as e:
            logger.warning('抖音搜索失败({}, offset={}, 第{}次): {}'.format(keyword, offset, attempt + 1, e))
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
                continue
            return []
        data = resp.get('data') or []
        if data:
            return data
        if attempt < retries - 1:
            logger.warning('抖音搜索空结果({}, offset={})，疑似频控，第{}次退避重试'.format(
                keyword, offset, attempt + 1))
            time.sleep(backoff * (attempt + 1))
    return []


def collect_douyin(keyword, cfg):
    """搜索抖音作品并抽取字段，返回 work 列表（空结果自动退避重试，规避频控误记 0）。"""
    auth = _get_auth()
    dcfg = cfg.get('douyin', {})
    max_pages = int(dcfg.get('max_pages', 2))
    sort_type = str(dcfg.get('sort_type', '0'))
    publish_time = str(dcfg.get('publish_time', '0'))
    gap = dcfg.get('request_gap_seconds', [5, 10])

    def _collect_once():
        works = []
        seen = set()
        for page in range(max_pages):
            offset = str(page * 20)
            data = _search_douyin_page(auth, keyword, sort_type, publish_time, offset)
            for item in data:
                aweme = item.get('aweme_info')
                if not aweme:
                    continue
                wid = aweme.get('aweme_id')
                if not wid or wid in seen:
                    continue
                seen.add(wid)
                works.append(_extract_work(aweme))
            if page < max_pages - 1:
                time.sleep(random.uniform(gap[0], gap[1]))
        return works

    works = _collect_once()
    if not works:
        logger.warning('抖音采集 {}: 首轮 0 条，退避 30s 后整体重试'.format(keyword))
        time.sleep(30)
        works = _collect_once()
    logger.info('抖音采集 {}: {} 条作品'.format(keyword, len(works)))
    return works


def enrich_author_followers(works, cfg):
    """对作品作者做 get_user_info 二次查询，补齐真实粉丝数（控制数量避免频控）。"""
    from dy_apis.douyin_api import DouyinAPI
    auth = _get_auth()
    dcfg = cfg.get('douyin', {})
    max_enrich = int(dcfg.get('max_author_enrich', 20))
    gap = dcfg.get('request_gap_seconds', [5, 10])
    # 按互动量排序，优先补足头部作者
    ordered = sorted(works, key=lambda w: w['digg_count'] + w['comment_count'], reverse=True)
    enriched = 0
    for w in ordered:
        if enriched >= max_enrich:
            break
        sec_uid = w.get('author_sec_uid')
        if not sec_uid or w.get('author_follower_count', 0) > 0:
            continue
        try:
            info = DouyinAPI.get_user_info(auth, 'https://www.douyin.com/user/' + sec_uid)
            user = info.get('user') or {}
            w['author_follower_count'] = user.get('follower_count', 0) or 0
            w['author_total_favorited'] = user.get('total_favorited', 0) or 0
            enriched += 1
            time.sleep(random.uniform(gap[0], gap[1]))
        except Exception as e:
            logger.warning('作者信息查询失败({}): {}'.format(sec_uid, e))
    return works


# ---- 淘宝读取 ----
def load_taobao(keyword):
    """从 MySQL price_research 表读取某关键词的淘宝商品（仅 platform=taobao，合并所有历史任务）。"""
    from services.storage import load_all
    products = []
    try:
        items = load_all('price_research')
    except Exception as e:
        logger.warning('读取淘宝 price_research 失败: {}'.format(e))
        return products
    for item in items:
        if (item.get('platform') or '').strip() != 'taobao':
            continue
        if (item.get('keyword') or '').strip() != keyword.strip():
            continue
        for p in item.get('products', []) or []:
            if isinstance(p, dict):
                products.append(p)
    return products


# ---- 3.1 增长动能（抖音 + B站跨平台热度） ----
def growth_momentum(works, cfg, bilibili_works=None):
    now = time.time()
    w = cfg.get('windows', {})
    recent = w.get('recent', 7)
    mid = w.get('mid', 14)
    long_ = w.get('long', 30)

    buckets = {'recent': 0, 'mid': 0, 'old': 0}
    buckets_inter = {'recent': 0, 'mid': 0, 'old': 0}
    total_authors = set()
    recent_authors = set()

    for work in works:
        age_days = (now - float(work['create_time'] or now)) / 86400.0
        inter = work['digg_count'] + work['comment_count'] + work['share_count'] + work['collect_count']
        sec_uid = work.get('author_sec_uid')
        if sec_uid:
            total_authors.add(sec_uid)
        if age_days <= recent:
            buckets['recent'] += 1
            buckets_inter['recent'] += inter
            if sec_uid:
                recent_authors.add(sec_uid)
        elif age_days <= mid:
            buckets['mid'] += 1
            buckets_inter['mid'] += inter
        elif age_days <= long_:
            buckets['old'] += 1
            buckets_inter['old'] += inter

    # 发布量环比增速（近7天 vs 前7天）
    publish_growth = (buckets['recent'] - buckets['mid']) / max(buckets['mid'], 1)
    # 二阶差分（加速度）
    accel = (buckets['recent'] - buckets['mid']) - (buckets['mid'] - buckets['old'])
    accel = accel / max(buckets['mid'] + buckets['old'], 1)
    # 互动-发布背离度
    inter_growth = (buckets_inter['recent'] - buckets_inter['mid']) / max(buckets_inter['mid'], 1)
    divergence = inter_growth - publish_growth
    # 新达人入局增长率（近7天新作者占比）
    new_author_rate = len(recent_authors) / max(len(total_authors), 1)

    return {
        'publish_volume_growth': _growth_norm(publish_growth),
        'acceleration': _growth_norm(accel),
        'interaction_divergence': _growth_norm(divergence),
        'new_author_rate': _clamp01(new_author_rate),
        'cross_platform_heat': sources.bilibili_heat(bilibili_works) if bilibili_works else 0.5,
        '_raw': {
            'buckets': buckets, 'publish_growth': publish_growth,
            'accel': accel, 'divergence': divergence, 'new_author_rate': new_author_rate,
        },
    }


# ---- 3.2 受众质量（抖音 + 淘宝） ----
def audience_quality(works, taobao_products, cfg):
    # 作者粉丝层级：高粉作者（>=1w）占比 + 平均粉丝对数
    followers = [w.get('author_follower_count', 0) for w in works if w.get('author_follower_count', 0) > 0]
    if followers:
        high_follower_ratio = sum(1 for f in followers if f >= 10000) / len(followers)
        avg_log = sum(math.log10(f + 1) for f in followers) / len(followers)
        author_tier = _clamp01(0.5 * high_follower_ratio + 0.5 * (avg_log / 6.0))
    else:
        high_follower_ratio = 0.0
        author_tier = 0.5

    # 高客单笔记占比：标题命中高端词
    high_end_words = ['高定', '定制', '轻奢', '高端', '奢华', '重工', '手工', '原创设计']
    high_end_notes = 0
    for work in works:
        if any(k in work['desc'] for k in high_end_words):
            high_end_notes += 1
    high_end_note_ratio = high_end_notes / max(len(works), 1)

    # 低价流量占比（反向）：淘宝低价商品占比
    prices = []
    for p in taobao_products:
        price = _parse_price(p.get('item_price'))
        if price is not None and price > 0:
            prices.append(price)
    low_threshold = float(cfg.get('low_price_threshold', 100))
    low_price_ratio = (sum(1 for p in prices if p < low_threshold) / max(len(prices), 1)) if prices else 0.5

    # 评论区正向需求 / 求购留言：用抖音标题/文案关键词代理
    demand_words = ['求', '想要', '哪里买', '怎么买', '链接', '多少钱', '好想要', '蹲', '推荐', '种草']
    demand_ratio = sum(1 for w in works if any(k in w['desc'] for k in demand_words)) / max(len(works), 1)
    positive = _clamp01(demand_ratio)
    purchase = _clamp01(demand_ratio * 0.8)

    return {
        'author_tier': author_tier,
        'high_end_note_ratio': _clamp01(high_end_note_ratio),
        'positive_demand_density': positive,
        'purchase_intent_density': purchase,
        'low_price_ratio': low_price_ratio,
        '_raw': {
            'followers_sample': len(followers), 'high_follower_ratio': high_follower_ratio,
            'high_end_notes': high_end_notes, 'prices_sample': len(prices), 'low_price_ratio': low_price_ratio,
        },
    }


# ---- 3.3 风格迁移（AI + 静态映射） ----
def style_migration(keyword, works, fabric_kb, cfg):
    # 静态兜底：关键词是否命中知识库里的"人→宠"高适配元素
    mapping = fabric_kb.get('element_mapping', [])
    hit = 0
    for m in mapping:
        el = m.get('human_element', '')
        # 仅用关键词做轻量匹配（阶段 A）
        if el and any(ch in keyword for ch in el[:2]):
            if m.get('pet_adaptability') == 'high':
                hit += 1
    static_score = _clamp01(0.3 + 0.35 * min(hit, 2))

    # AI 兜底：让豆包给"人→宠"迁移打分（0~1）
    desc_sample = '；'.join(w['desc'][:30] for w in works[:5])
    prompt = (
        '你是宠物时尚趋势分析师。针对宠物服装趋势关键词"{kw}"，'
        '请评估"人类时尚元素迁移到高端宠物服饰"的适配度（0~1，仅输出一个数字）。\n'
        '参考作品标题：{desc}\n只输出一个 0 到 1 之间的小数，不要解释。'
    ).format(kw=keyword, desc=desc_sample[:500])
    ai_text = _call_ai(prompt)
    try:
        ai_score = _clamp01(float(ai_text))
    except Exception:
        ai_score = static_score

    # 有 AI 用 AI，否则回退静态
    score = ai_score if ai_text else static_score
    return {
        'human_to_pet_score': score,
        '_raw': {'static_score': static_score, 'ai_score': ai_score, 'ai_used': bool(ai_text)},
    }


# ---- 3.4 可行性（知识库 + 1688 供应商） ----
def feasibility(keyword, fabric_kb, cfg, suppliers=None):
    fabrics = fabric_kb.get('fabrics', [])
    # 关键词命中面料，取最匹配的面料；否则取均值
    matched = [f for f in fabrics if f.get('name') in keyword]
    if not matched:
        matched = fabrics
    def _avg(key):
        vals = [f.get(key, 0) for f in matched]
        return sum(vals) / max(len(vals), 1)
    procurement_map = {'easy': 1.0, 'normal': 0.7, 'hard': 0.4}
    craft_map = {'low': 1.0, 'medium': 0.7, 'high': 0.4}
    fabric_score = _clamp01(sum(procurement_map.get(f.get('procurement'), 0.7) for f in matched) / max(len(matched), 1))
    craft_score = _clamp01(sum(craft_map.get(f.get('craft_difficulty'), 0.7) for f in matched) / max(len(matched), 1))
    # 阶段 B：有 1688 供应商硬数据时，覆盖面料采购分
    supplier_score = sources.supplier_procurement(suppliers)
    if supplier_score is not None:
        fabric_score = supplier_score
    # 成本适配：高端面料占比（high_end_fit）
    high_end_fit = sum(1 for f in matched if f.get('high_end_fit')) / max(len(matched), 1)
    cost_fit = _clamp01(0.4 + 0.6 * high_end_fit)
    # 版型改造：静态给中等偏上
    silhouette_adapt = 0.7
    return {
        'fabric_procurement': fabric_score,
        'craft_difficulty': craft_score,
        'cost_fit': cost_fit,
        'silhouette_adapt': silhouette_adapt,
        '_raw': {'matched_fabrics': [f.get('name') for f in matched]},
    }


# ---- 3.5 噪声衰减（淘宝 + AI，负向） ----
def noise_decay(keyword, taobao_products, cfg):
    # 卖家数量（内卷度）：店铺去重越多越内卷
    shops = set()
    for p in taobao_products:
        shop = (p.get('item_shop') or '').strip()
        if shop and shop != '?':
            shops.add(shop)
    seller_ratio = len(shops) / max(len(taobao_products), 1)

    # 低价铺货占比
    prices = []
    for p in taobao_products:
        price = _parse_price(p.get('item_price'))
        if price is not None and price > 0:
            prices.append(price)
    low_threshold = float(cfg.get('low_price_threshold', 100))
    low_price_ratio = (sum(1 for p in prices if p < low_threshold) / max(len(prices), 1)) if prices else 0.5

    # 72h 网红梗 / 退货风险：AI 估计，失败给中性 0.3
    ai_text = _call_ai(
        '针对宠物服装关键词"{kw}"，评估其作为短期网红梗（易快速衰退/高退货风险）的程度，'
        '输出 0~1 之间的小数（越大风险越高），只输出数字。'.format(kw=keyword))
    try:
        hot_meme_risk = _clamp01(float(ai_text))
    except Exception:
        hot_meme_risk = 0.3

    return {
        'seller_density': _clamp01(seller_ratio),
        'low_price_saturation': low_price_ratio,
        'hot_meme_risk': hot_meme_risk,
        '_raw': {'shop_count': len(shops), 'low_price_ratio': low_price_ratio},
    }


# ---- 汇总入口 ----
def compute_features(keyword, cfg=None, fabric_kb=None, use_ai=True, works=None, taobao_products=None,
                     bilibili_works=None, suppliers=None):
    """计算某关键词的全部因子，返回 feature dict（各因子组含 0~1 子特征）。"""
    if cfg is None:
        from pet_trend import load_trend_config
        cfg = load_trend_config()
    if fabric_kb is None:
        from pet_trend import load_fabric_kb
        fabric_kb = load_fabric_kb()

    if works is None:
        works = collect_douyin(keyword, cfg)
        works = enrich_author_followers(works, cfg)
    if taobao_products is None:
        taobao_products = load_taobao(keyword)

    # 阶段 B 数据源（B站 / 1688 供应商）
    if bilibili_works is None:
        bilibili_works = sources.collect_bilibili(keyword, cfg)
    if suppliers is None:
        suppliers = sources.load_1688_suppliers()  # 全局供应链（垂类词共享）

    feat = {
        'keyword': keyword,
        'douyin_works': len(works),
        'taobao_products': len(taobao_products),
        'bilibili_works': len(bilibili_works),
        'suppliers': len(suppliers),
        'growth_momentum': growth_momentum(works, cfg, bilibili_works),
        'audience_quality': audience_quality(works, taobao_products, cfg),
        'noise_decay': noise_decay(keyword, taobao_products, cfg) if use_ai else {
            'seller_density': 0.5, 'low_price_saturation': 0.5, 'hot_meme_risk': 0.3},
    }
    if use_ai:
        feat['style_migration'] = style_migration(keyword, works, fabric_kb, cfg)
    else:
        feat['style_migration'] = {'human_to_pet_score': 0.5}
    feat['feasibility'] = feasibility(keyword, fabric_kb, cfg, suppliers)
    return feat
