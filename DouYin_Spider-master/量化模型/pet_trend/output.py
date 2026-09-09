# -*- coding: utf-8 -*-
"""
宠物趋势预测 · 七项输出格式化
"""
from pet_trend.model import compute_trend_score


def _judge_lifecycle(score, cfg):
    thresholds = cfg.get('thresholds', {})
    high = thresholds.get('high_potential', 0.75)
    watch = thresholds.get('watch', 0.55)
    mature = thresholds.get('mature', 0.35)
    if score > high:
        return '萌芽/高潜力早期', '优先立项'
    if score > watch:
        return '观察期', '小成本素材测试'
    if score > mature:
        return '成熟期', '谨慎入场'
    return '衰退/伪趋势', '放弃'


def _extract_elements(features):
    """从抖音话题 + 标题高端词 + 知识库元素提取趋势元素清单。"""
    # 简化：需要 works 才能提取，这里用 features 里已存的关键信息兜底
    # works 列表不会全量进入 features（体积大），这里从 growth/quality 的 raw 中取不到，
    # 改为在 format_output 入参里传入 works / fabric_kb 提取。
    return []


def format_output(keyword, features, cfg=None, fabric_kb=None, works=None):
    """生成七项输出。"""
    if cfg is None:
        from pet_trend import load_trend_config
        cfg = load_trend_config()
    if fabric_kb is None:
        from pet_trend import load_fabric_kb
        fabric_kb = load_fabric_kb()

    score, group_scores = compute_trend_score(features, cfg)
    lifecycle, action = _judge_lifecycle(score, cfg)

    # 元素清单：抖音话题标签（去重取高频）
    hashtag_count = {}
    for w in (works or []):
        for h in w.get('hashtags', []) or []:
            hashtag_count[h] = hashtag_count.get(h, 0) + 1
    top_hashtags = [h for h, _ in sorted(hashtag_count.items(), key=lambda x: -x[1])[:8]]

    # 面料元素：可行性 raw 里命中的面料
    matched_fabrics = features.get('feasibility', {}).get('_raw', {}).get('matched_fabrics', [])

    # 爆发窗口：基于加速度与互动背离度做粗略判断
    g = features.get('growth_momentum', {})
    accel = g.get('acceleration', 0.5)
    divergence = g.get('interaction_divergence', 0.5)
    if accel > 0.6 and divergence > 0.6:
        burst_window = '未来 30 天内（加速 + 互动背离双高，接近爆发）'
    elif accel > 0.55:
        burst_window = '未来 30~60 天（发布加速中）'
    else:
        burst_window = '60~90 天（尚在积累期）'

    # 高客单改造建议
    high_end_advice = '围绕"{kw}"做高端化：优先{fb}等高端面料，采用可调节版型与软质内衬，突出原创设计/手工/重工卖点。'.format(
        kw=keyword, fb='、'.join(matched_fabrics[:3]) if matched_fabrics else '羊绒/真丝/提花')

    # 风险提示
    risks = []
    n = features.get('noise_decay', {})
    if n.get('seller_density', 0) > 0.6:
        risks.append('同类卖家密集，内卷度高')
    if n.get('low_price_saturation', 0) > 0.6:
        risks.append('低价铺货占比高，价格带易被拉低')
    if n.get('hot_meme_risk', 0) > 0.6:
        risks.append('短期网红梗属性强，存在快速衰退/高退货风险')
    if features.get('douyin_works', 0) < 5:
        risks.append('抖音样本量不足，分数可信度偏低')
    if not risks:
        risks.append('暂无明显结构性风险')

    # 素材关键词
    material_keywords = top_hashtags[:5] if top_hashtags else [keyword]

    return {
        'trend_name': keyword,
        'elements': {
            'hashtags': top_hashtags,
            'fabrics': matched_fabrics,
        },
        'trend_score': round(score, 4),
        'group_scores': {k: round(v, 4) for k, v in group_scores.items()},
        'lifecycle': lifecycle,
        'action': action,
        'burst_window': burst_window,
        'high_end_advice': high_end_advice,
        'risks': risks,
        'material_keywords': material_keywords,
        'data_summary': {
            'douyin_works': features.get('douyin_works', 0),
            'taobao_products': features.get('taobao_products', 0),
            'bilibili_works': features.get('bilibili_works', 0),
            'suppliers': features.get('suppliers', 0),
        },
    }
