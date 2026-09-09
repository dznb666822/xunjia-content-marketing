# -*- coding: utf-8 -*-
"""
存储门面 - 根据 STORAGE_BACKEND 环境变量在 JSON 与 MySQL 后端之间切换。

对外提供 7 个函数（与旧版 storage.py 完全一致）：
    save_all / load_all / save_one / update_one / delete_one / find_by_id / find_by

默认走 JSON 后端（services/storage_json.py），设置环境变量
STORAGE_BACKEND=mysql 后切换为 MySQL 后端（services/storage_mysql.py）。
业务代码无需任何改动。

此外，本模块提供"当前登录用户"上下文与数据隔离：
    - 通过 set_current_user() 设置当前用户（web_server 在请求前后调用）
    - 对 SCOPED_ENTITIES 中的实体，普通用户仅能读写属于自己的数据
    - 管理员不受隔离；未设置当前用户（后台任务/脚本）也不隔离
"""
import os
import threading

from dotenv import load_dotenv

# web_server 在 load_env() 之前就 import 本模块，这里需先加载 .env，
# 否则 STORAGE_BACKEND / MYSQL_* 环境变量读取不到（load_dotenv 默认不覆盖已存在的变量）。
load_dotenv()

BACKEND = os.environ.get("STORAGE_BACKEND", "json")  # 'json' | 'mysql'

if BACKEND == "mysql":
    from services.storage_mysql import (
        save_all as _save_all,
        load_all as _load_all,
        save_one as _save_one,
        update_one as _update_one,
        delete_one as _delete_one,
        find_by_id as _find_by_id,
        find_by as _find_by,
    )
else:
    from services.storage_json import (
        save_all as _save_all,
        load_all as _load_all,
        save_one as _save_one,
        update_one as _update_one,
        delete_one as _delete_one,
        find_by_id as _find_by_id,
        find_by as _find_by,
    )

# ---- 需要按用户隔离数据的实体 ----
SCOPED_ENTITIES = {"brands", "competitors", "videos", "tasks", "media_library", "mashup_results", "comic_designs"}

# ---- 当前登录用户上下文（thread-local，天然适配 Flask 请求线程）----
_ctx = threading.local()


def set_current_user(user_id, role):
    """设置当前登录用户（web_server 的 before_request 调用）。"""
    _ctx.user_id = user_id
    _ctx.role = role


def get_current_user():
    """返回 (user_id, role)，未登录返回 (None, None)。"""
    return (getattr(_ctx, "user_id", None), getattr(_ctx, "role", None))


def clear_current_user():
    _ctx.user_id = None
    _ctx.role = None


def _restricted(entity_name):
    """当前上下文是否需要对指定实体做隔离（普通用户访问受限实体）。"""
    if entity_name not in SCOPED_ENTITIES:
        return False
    user_id, role = get_current_user()
    return user_id is not None and role != "admin"


def save_all(entity_name, data_list):
    """覆盖写入实体全部数据（系统/迁移用，不做隔离）。"""
    return _save_all(entity_name, data_list)


def load_all(entity_name):
    """加载实体全部数据（普通用户仅返回自己的数据）。"""
    data = _load_all(entity_name)
    if _restricted(entity_name):
        user_id, _ = get_current_user()
        data = [d for d in data if d.get("owner_id") == user_id]
    return data


def save_one(entity_name, item):
    """保存单条记录，并自动注入当前用户为 owner。"""
    if entity_name in SCOPED_ENTITIES:
        user_id, _ = get_current_user()
        if user_id is not None and item is not None and "owner_id" not in item:
            item["owner_id"] = user_id
    return _save_one(entity_name, item)


def update_one(entity_name, item_id, updates):
    """更新指定ID的记录（普通用户只能更新自己的数据）。"""
    if _restricted(entity_name):
        existing = _find_by_id(entity_name, item_id)
        if existing is None or existing.get("owner_id") != get_current_user()[0]:
            return None
    return _update_one(entity_name, item_id, updates)


def delete_one(entity_name, item_id):
    """删除指定ID的记录（普通用户只能删除自己的数据）。"""
    if _restricted(entity_name):
        existing = _find_by_id(entity_name, item_id)
        if existing is None or existing.get("owner_id") != get_current_user()[0]:
            return None
    return _delete_one(entity_name, item_id)


def find_by_id(entity_name, item_id):
    """按ID查找记录（普通用户无法查到他人数据）。"""
    item = _find_by_id(entity_name, item_id)
    if item is not None and _restricted(entity_name):
        if item.get("owner_id") != get_current_user()[0]:
            return None
    return item


def exists_any(entity_name, item_id):
    """判断记录是否存在（不受当前用户隔离影响，供系统兜底逻辑使用）。"""
    return _find_by_id(entity_name, item_id) is not None


def find_by(entity_name, predicate_func):
    """按自定义条件查找记录（在隔离后的数据范围内过滤）。"""
    data = load_all(entity_name)
    return [item for item in data if predicate_func(item)]


__all__ = [
    "BACKEND",
    "save_all",
    "load_all",
    "save_one",
    "update_one",
    "delete_one",
    "find_by_id",
    "find_by",
    "exists_any",
    "set_current_user",
    "get_current_user",
    "clear_current_user",
]
