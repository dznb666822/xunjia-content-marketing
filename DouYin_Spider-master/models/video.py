# -*- coding: utf-8 -*-
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List


@dataclass
class Video:
    """视频数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aweme_id: str = ""
    title: str = ""
    description: str = ""
    cover_url: str = ""
    video_url: str = ""
    local_path: str = ""
    duration: int = 0
    author_name: str = ""
    author_id: str = ""
    stats: Dict = field(default_factory=dict)
    analysis_status: str = "pending"
    text_structure: Dict = field(default_factory=dict)
    video_type: str = ""
    scene_desc: str = ""
    cover_desc: str = ""
    mood: str = ""
    scripts: List[Dict] = field(default_factory=list)
    competitor_id: str = ""
    first_seen_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)
