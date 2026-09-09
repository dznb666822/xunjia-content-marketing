# -*- coding: utf-8 -*-
"""
宠物趋势预测 · 阶段一复合加权模型（冷启动）

TrendScore = w1*增长动能 + w2*受众质量 + w3*风格迁移 + w4*可行性 - w5*噪声衰减
"""
from pet_trend.features import _clamp01


def _avg(values):
    return sum(values) / max(len(values), 1)


def compute_group_scores(features):
    """把各因子组的子特征聚合为 0~1 的分组得分。"""
    g = features.get('growth_momentum', {})
    growth = _avg([
        g.get('publish_volume_growth', 0.5),
        g.get('acceleration', 0.5),
        g.get('interaction_divergence', 0.5),
        g.get('new_author_rate', 0.5),
        g.get('cross_platform_heat', 0.5),  # 阶段 B：B站跨平台热度
    ])

    a = features.get('audience_quality', {})
    quality = _avg([
        a.get('author_tier', 0.5),
        a.get('high_end_note_ratio', 0.5),
        a.get('positive_demand_density', 0.5),
        a.get('purchase_intent_density', 0.5),
        1.0 - a.get('low_price_ratio', 0.5),  # 低价流量占比反向
    ])

    s = features.get('style_migration', {})
    style = s.get('human_to_pet_score', 0.5)

    f = features.get('feasibility', {})
    feas = _avg([
        f.get('fabric_procurement', 0.5),
        f.get('craft_difficulty', 0.5),
        f.get('cost_fit', 0.5),
        f.get('silhouette_adapt', 0.5),
    ])

    n = features.get('noise_decay', {})
    noise = _avg([
        n.get('seller_density', 0.5),
        n.get('low_price_saturation', 0.5),
        n.get('hot_meme_risk', 0.3),
    ])

    return {
        'growth_momentum': growth,
        'audience_quality': quality,
        'style_migration': style,
        'feasibility': feas,
        'noise_decay': noise,
    }


def compute_trend_score(features, cfg=None):
    """计算 TrendScore，返回 (score, group_scores)。"""
    if cfg is None:
        from pet_trend import load_trend_config
        cfg = load_trend_config()
    weights = cfg.get('weights', {})
    scores = compute_group_scores(features)
    score = (
        weights.get('growth_momentum', 0.30) * scores['growth_momentum']
        + weights.get('audience_quality', 0.30) * scores['audience_quality']
        + weights.get('style_migration', 0.20) * scores['style_migration']
        + weights.get('feasibility', 0.15) * scores['feasibility']
        - weights.get('noise_decay', 0.05) * scores['noise_decay']
    )
    return _clamp01(score), scores
