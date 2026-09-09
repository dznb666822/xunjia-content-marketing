# -*- coding: utf-8 -*-
"""
用户账号与权限服务。

- users 实体：id / username / password_hash / role
- 两级角色：admin（全部功能）/ user（受限功能集）
- 数据隔离由 services/storage.py 门面根据当前登录用户完成
"""
import uuid
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from services import storage

# 功能模块 key（与前端 data-panel 一一对应）
ALL_FEATURES = [
    "discovery", "monitor", "analysis", "scripts", "price-research",
    "intent", "dashboard", "tools-search", "tools-user", "tools-work",
    "tools-live", "tools-message", "tools-feed", "tools-notice",
    "profile", "trendradar", "prompts", "mashup", "comic", "ai-clip", "materials", "campaign",
]

# 普通用户默认可见的功能（核心运营闭环），管理员拥有 ALL_FEATURES 全部
USER_FEATURES = [
    "discovery", "monitor", "analysis", "scripts", "mashup", "comic",
    "profile", "dashboard", "ai-clip",
]

# 管理员专属入口（不参与对普通用户的授权）
ADMIN_ONLY_FEATURES = ["admin-users"]

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def _find_by_username(username):
    users = storage.load_all("users")
    for u in users:
        if u.get("username") == username:
            return u
    return None


def ensure_admin():
    """确保管理员账号存在（不存在则创建）。返回是否新建。"""
    if _find_by_username(ADMIN_USERNAME) is None:
        now = datetime.now().isoformat()
        storage.save_one("users", {
            "id": str(uuid.uuid4()),
            "username": ADMIN_USERNAME,
            "password_hash": generate_password_hash(ADMIN_PASSWORD),
            "role": "admin",
            "created_at": now,
            "updated_at": now,
        })
        return True
    return False


def register_user(username, password):
    """注册普通用户账号。返回用户 dict，失败抛 ValueError。"""
    username = (username or "").strip()
    if not username:
        raise ValueError("账号不能为空")
    if not password:
        raise ValueError("密码不能为空")
    if len(password) < 6:
        raise ValueError("密码长度至少 6 位")
    if _find_by_username(username) is not None:
        raise ValueError("账号已存在")

    now = datetime.now().isoformat()
    user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "password_hash": generate_password_hash(password),
        "role": "user",
        "features": list(USER_FEATURES),
        "created_at": now,
        "updated_at": now,
    }
    storage.save_one("users", user)
    _create_brand_for_user(user)
    return user


def _find_brand_by_owner(owner_id):
    """查找某用户拥有的品牌（品牌与账户一一对应）。"""
    for b in storage.load_all("brands"):
        if b.get("owner_id") == owner_id:
            return b
    return None


def _create_brand_for_user(user):
    """为指定用户创建同名品牌（品牌=账户，一一对应）。"""
    now = datetime.now().isoformat()
    storage.save_one("brands", {
        "id": str(uuid.uuid4()),
        "name": user.get("username", ""),
        "category": "",
        "target_audience": "",
        "product_desc": "",
        "style_tone": "",
        "selling_points": [],
        "skus": [],
        "owner_id": user["id"],
        "created_at": now,
        "updated_at": now,
    })


def ensure_user_brands():
    """为所有尚无品牌的用户补建同名品牌（幂等）。返回新建数量。"""
    created = 0
    for u in storage.load_all("users"):
        if _find_brand_by_owner(u["id"]) is not None:
            continue
        _create_brand_for_user(u)
        created += 1
    return created


def authenticate(username, password):
    """校验账号密码。成功返回用户 dict，失败返回 None。"""
    username = (username or "").strip()
    user = _find_by_username(username)
    if user is None:
        return None
    if not check_password_hash(user.get("password_hash", ""), password or ""):
        return None
    return user


def get_user(user_id):
    return storage.find_by_id("users", user_id)


def get_features(user):
    """返回用户可见的功能 key 列表。"""
    if not user:
        return []
    if user.get("role") == "admin":
        return list(ALL_FEATURES) + list(ADMIN_ONLY_FEATURES)
    allowed = set(user.get("features") or USER_FEATURES)
    return [f for f in ALL_FEATURES if f in allowed]


def to_public(user):
    """去除敏感字段后的用户信息（用于返回给前端）。"""
    if not user:
        return None
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "features": get_features(user),
    }


def list_users():
    """返回所有用户（public 形式），供管理员查看。"""
    return [to_public(u) for u in storage.load_all("users")]


def set_user_feature(user_id, feature, enabled):
    """给指定用户新增/移除某个功能权限。返回更新后的用户。"""
    user = storage.find_by_id("users", user_id)
    if user is None:
        raise ValueError("用户不存在")
    if user.get("role") == "admin":
        raise ValueError("不能修改管理员权限")
    if feature not in ALL_FEATURES:
        raise ValueError("未知功能: {}".format(feature))

    features = set(user.get("features") or USER_FEATURES)
    if enabled:
        features.add(feature)
    else:
        features.discard(feature)
    storage.update_one("users", user_id, {"features": sorted(features)})
    return storage.find_by_id("users", user_id)
