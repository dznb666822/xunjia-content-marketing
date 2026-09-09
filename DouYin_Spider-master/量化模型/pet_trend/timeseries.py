# -*- coding: utf-8 -*-
"""
宠物趋势预测 · 阶段 C：样本落库 + XGBoost 时序生命周期模型

设计依据（见 宠物趋势预测模型方案.md §4.2）：
- 特征：阶段一五因子分组得分（0~1）+ 各平台数量特征（对数归一化）
- 标签：未来 30/60 天真实涨幅 → 4 类生命周期（萌芽/上升/顶峰/衰退）
- 样本积累 ≥120 条（且带真实标签）后才启用真实训练；
  在此之前可用 weak_label 模式（用阶段一 TrendScore 分桶）跑通管线验证。
- 禁大参数量深度模型：固定 XGBoost（小参数量、可解释、抗小样本）。
"""
import hashlib
import math
import os
import pickle
from collections import Counter
from datetime import datetime, timedelta

from loguru import logger

from services.storage import load_all, save_one, update_one, delete_one, find_by_id

ENTITY = 'trend_samples'
MIN_SAMPLES = 120
# 4 分类目标（顺序即类别索引，与 LabelEncoder 结果一致）
LIFECYCLE_ORDER = ['萌芽', '上升', '顶峰', '衰退']

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_DIR = os.path.join(_BASE, 'models')
_MODEL_PATH = os.path.join(_MODEL_DIR, 'stage_c_xgb.pkl')


def _now():
    return datetime.now().strftime('%Y%m%d%H%M%S')


def _kw_id(keyword):
    return hashlib.md5(keyword.encode('utf-8')).hexdigest()[:8]


# ---------------- 生命周期映射 ----------------
def lifecycle_from_score(score):
    """阶段一弱标签：TrendScore 分桶 → 4 类生命周期（管线验证用）。"""
    if score > 0.75:
        return '萌芽'
    if score > 0.55:
        return '上升'
    if score > 0.35:
        return '顶峰'
    return '衰退'


def lifecycle_from_growth(growth):
    """真实标签：未来 30 天涨幅（比例）→ 4 类生命周期。"""
    if growth is None:
        return None
    if growth > 0.5:
        return '萌芽'
    if growth > 0.15:
        return '上升'
    if growth > -0.05:
        return '顶峰'
    return '衰退'


# ---------------- 样本落库 ----------------
def save_sample(keyword, features, group_scores, trend_score, lifecycle, snapshot_at=None):
    """落库一个特征快照样本（同 keyword+snapshot_at 幂等覆盖）。"""
    snapshot_at = snapshot_at or _now()
    item_id = 'ts_{}_{}'.format(snapshot_at, _kw_id(keyword))
    if find_by_id(ENTITY, item_id) is not None:
        delete_one(ENTITY, item_id)
    item = {
        'id': item_id,
        'keyword': keyword,
        'snapshot_at': snapshot_at,
        'douyin_works': int(features.get('douyin_works', 0) or 0),
        'taobao_products': int(features.get('taobao_products', 0) or 0),
        'bilibili_works': int(features.get('bilibili_works', 0) or 0),
        'suppliers': int(features.get('suppliers', 0) or 0),
        'group_scores': group_scores,
        'features': features,
        'trend_score': float(trend_score or 0),
        'lifecycle': lifecycle,
        'label_30d': None,
        'label_60d': None,
        'created_at': _now(),
    }
    return save_one(ENTITY, item)


def load_samples():
    return load_all(ENTITY)


def labeled_count():
    return sum(1 for s in load_samples() if s.get('label_30d') is not None)


# ---------------- 特征矩阵 ----------------
FEATURE_COLS = [
    'growth_momentum', 'audience_quality', 'style_migration', 'feasibility', 'noise_decay',
    'douyin_works', 'taobao_products', 'bilibili_works', 'suppliers',
]


def _feature_vector(sample):
    gs = sample.get('group_scores') or {}
    return [
        float(gs.get('growth_momentum', 0.5)),
        float(gs.get('audience_quality', 0.5)),
        float(gs.get('style_migration', 0.5)),
        float(gs.get('feasibility', 0.5)),
        float(gs.get('noise_decay', 0.5)),
        min(math.log1p(float(sample.get('douyin_works', 0) or 0)) / 6.0, 1.0),
        min(math.log1p(float(sample.get('taobao_products', 0) or 0)) / 8.0, 1.0),
        min(math.log1p(float(sample.get('bilibili_works', 0) or 0)) / 6.0, 1.0),
        min(math.log1p(float(sample.get('suppliers', 0) or 0)) / 8.0, 1.0),
    ]


def _build_matrix(samples, label_key):
    X, y = [], []
    for s in samples:
        lab = s.get(label_key)
        if lab is None:
            continue
        X.append(_feature_vector(s))
        y.append(lab)
    return X, y


# ---------------- 训练 ----------------
def train_stage_c(min_samples=MIN_SAMPLES, weak_label=False):
    """训练 XGBoost 生命周期分类器。

    - weak_label=False：用 label_30d 真实涨幅（需跨时间样本积累）
    - weak_label=True：用阶段一 TrendScore 分桶作弱标签（管线验证）

    返回 dict：{status, samples, labeled, trained, model_path, accuracy, lifecycle_dist, message}
    """
    samples = load_samples()
    if weak_label:
        label_key = '_label'
        for s in samples:
            s[label_key] = s.get('lifecycle') if s.get('lifecycle') in LIFECYCLE_ORDER \
                else lifecycle_from_score(float(s.get('trend_score', 0) or 0))
    else:
        label_key = '_label'
        for s in samples:
            s[label_key] = lifecycle_from_growth(s.get('label_30d'))

    X, y = _build_matrix(samples, label_key)
    result = {
        'status': 'pending',
        'samples': len(samples),
        'labeled': len(y),
        'trained': False,
        'model_path': None,
        'accuracy': None,
        'lifecycle_dist': dict(Counter(y)),
        'message': '',
    }
    if len(y) < min_samples:
        result['status'] = 'accumulating'
        result['message'] = '有标签样本 {}/{}，继续积累（需跨 30/60 天回填真实涨幅后训练）'.format(len(y), min_samples)
        return result

    try:
        import xgboost as xgb
        from sklearn.preprocessing import LabelEncoder
        from sklearn.metrics import accuracy_score

        le = LabelEncoder()
        y_enc = le.fit_transform(y)
        n_classes = len(le.classes_)
        if n_classes == 2:
            model = xgb.XGBClassifier(
                n_estimators=120, max_depth=4, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8, reg_alpha=1.0, reg_lambda=1.0,
                objective='binary:logistic', eval_metric='logloss',
                random_state=42, verbosity=0,
            )
        else:
            model = xgb.XGBClassifier(
                n_estimators=120, max_depth=4, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8, reg_alpha=1.0, reg_lambda=1.0,
                objective='multi:softprob', num_class=n_classes,
                eval_metric='mlogloss', random_state=42, verbosity=0,
            )
        model.fit(X, y_enc)

        os.makedirs(_MODEL_DIR, exist_ok=True)
        with open(_MODEL_PATH, 'wb') as f:
            pickle.dump({'model': model, 'classes': le.classes_.tolist()}, f)

        result['status'] = 'trained'
        result['trained'] = True
        result['model_path'] = _MODEL_PATH
        result['accuracy'] = float(accuracy_score(y_enc, model.predict(X)))
        result['message'] = 'XGBoost 时序模型训练完成，样本 {} 条'.format(len(y))
    except Exception as e:
        logger.error('阶段 C 训练失败: {}'.format(e))
        result['status'] = 'error'
        result['trained'] = False
        result['message'] = '训练失败: {}'.format(str(e))
    return result


# ---------------- 预测 ----------------
def predict_lifecycle(features, group_scores, model_path=None):
    """用训练好的模型预测生命周期。返回 {status, lifecycle, message}。"""
    model_path = model_path or _MODEL_PATH
    if not os.path.exists(model_path):
        return {'status': 'no_model', 'lifecycle': None, 'message': '模型尚未训练（样本不足）'}
    try:
        with open(model_path, 'rb') as f:
            bundle = pickle.load(f)
        model = bundle['model']
        classes = bundle['classes']
        sample = {
            'group_scores': group_scores,
            'douyin_works': features.get('douyin_works', 0),
            'taobao_products': features.get('taobao_products', 0),
            'bilibili_works': features.get('bilibili_works', 0),
            'suppliers': features.get('suppliers', 0),
        }
        idx = int(model.predict([_feature_vector(sample)])[0])
        return {'status': 'ok', 'lifecycle': classes[idx], 'message': ''}
    except Exception as e:
        return {'status': 'error', 'lifecycle': None, 'message': str(e)}


# ---------------- 标签回填（跨时间，供后续积累） ----------------
def backfill_labels(current_counts, days=30):
    """对 days 天前的样本回填真实涨幅标签。

    current_counts: {keyword: 当前抖音作品数}
    涨幅 = (当前作品数 - 样本作品数) / max(样本作品数, 1)
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d%H%M%S')
    updated = 0
    for s in load_samples():
        if s.get('label_30d') is not None:
            continue
        if (s.get('snapshot_at') or '') > cutoff:
            continue
        kw = s.get('keyword')
        if kw not in current_counts:
            continue
        base = float(s.get('douyin_works', 0) or 0)
        cur = float(current_counts[kw])
        growth = (cur - base) / max(base, 1.0)
        update_one(ENTITY, s['id'], {'label_30d': round(growth, 4)})
        updated += 1
    return updated
