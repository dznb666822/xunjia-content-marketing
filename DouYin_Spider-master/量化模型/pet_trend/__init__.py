# -*- coding: utf-8 -*-
"""
宠物趋势预测 · 配置加载与包入口
"""
import os

import yaml

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_yaml(name):
    path = os.path.join(_BASE, 'config', name)
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_trend_config():
    """加载 config/pet_trend.yaml"""
    return _load_yaml('pet_trend.yaml')


def load_fabric_kb():
    """加载 config/pet_fabric_kb.yaml"""
    return _load_yaml('pet_fabric_kb.yaml')
