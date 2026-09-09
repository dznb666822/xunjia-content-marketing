# -*- coding: utf-8 -*-
"""
JSON 文件持久化服务 - 通用 CRUD 操作
数据存储在 datas/app_data/ 目录下

本模块是 JSON 后端实现，由 services/storage.py 门面在 STORAGE_BACKEND=json
（默认）时导入。业务代码不应直接 import 本模块。
"""
import json
import os
import threading

# 数据存储根目录
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datas", "app_data"
)

# 实体名 -> 线程锁 的映射
_locks = {}
_locks_lock = threading.Lock()


def _get_lock(entity_name):
    """获取指定实体的线程锁，不存在则创建"""
    with _locks_lock:
        if entity_name not in _locks:
            _locks[entity_name] = threading.Lock()
        return _locks[entity_name]


def _ensure_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _get_file_path(entity_name):
    """获取实体对应的JSON文件路径"""
    return os.path.join(DATA_DIR, "{}.json".format(entity_name))


def save_all(entity_name, data_list):
    """保存实体全部数据到JSON文件（覆盖写入）

    Args:
        entity_name: 实体名称（如 "brands", "competitors"）
        data_list: 数据列表
    """
    _ensure_dir()
    lock = _get_lock(entity_name)
    with lock:
        file_path = _get_file_path(entity_name)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)


def load_all(entity_name):
    """加载实体全部数据

    Args:
        entity_name: 实体名称

    Returns:
        数据列表，文件不存在时返回空列表
    """
    _ensure_dir()
    file_path = _get_file_path(entity_name)
    if not os.path.exists(file_path):
        return []
    lock = _get_lock(entity_name)
    with lock:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []


def save_one(entity_name, item):
    """保存单条记录（追加到列表末尾）

    Args:
        entity_name: 实体名称
        item: 单条数据字典

    Returns:
        保存的item
    """
    data_list = load_all(entity_name)
    data_list.append(item)
    save_all(entity_name, data_list)
    return item


def update_one(entity_name, item_id, updates):
    """更新指定ID的记录

    Args:
        entity_name: 实体名称
        item_id: 记录ID
        updates: 要更新的字段字典

    Returns:
        更新后的记录字典，未找到返回None
    """
    data_list = load_all(entity_name)
    for item in data_list:
        if item.get("id") == item_id:
            item.update(updates)
            save_all(entity_name, data_list)
            return item
    return None


def delete_one(entity_name, item_id):
    """删除指定ID的记录

    Args:
        entity_name: 实体名称
        item_id: 记录ID

    Returns:
        被删除的记录字典，未找到返回None
    """
    data_list = load_all(entity_name)
    for i, item in enumerate(data_list):
        if item.get("id") == item_id:
            deleted = data_list.pop(i)
            save_all(entity_name, data_list)
            return deleted
    return None


def find_by_id(entity_name, item_id):
    """按ID查找记录

    Args:
        entity_name: 实体名称
        item_id: 记录ID

    Returns:
        记录字典，未找到返回None
    """
    data_list = load_all(entity_name)
    for item in data_list:
        if item.get("id") == item_id:
            return item
    return None


def find_by(entity_name, predicate_func):
    """按自定义条件查找记录

    Args:
        entity_name: 实体名称
        predicate_func: 断言函数，接受一个item字典参数，返回bool

    Returns:
        匹配的记录列表
    """
    data_list = load_all(entity_name)
    return [item for item in data_list if predicate_func(item)]
