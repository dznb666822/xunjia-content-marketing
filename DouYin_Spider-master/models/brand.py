# -*- coding: utf-8 -*-
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List


@dataclass
class Brand:
    """品牌画像数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: str = ""
    target_audience: str = ""
    product_desc: str = ""
    style_tone: str = ""
    selling_points: List[str] = field(default_factory=list)
    skus: List[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)
