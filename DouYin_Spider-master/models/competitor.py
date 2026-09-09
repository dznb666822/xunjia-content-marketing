# -*- coding: utf-8 -*-
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Competitor:
    """对标博主数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    sec_uid: str = ""
    nickname: str = ""
    avatar: str = ""
    follower_count: int = 0
    category: str = "same_niche"
    status: str = "monitoring"
    notes: str = ""
    source_brand_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)
