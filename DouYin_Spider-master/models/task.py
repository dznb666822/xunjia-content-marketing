# -*- coding: utf-8 -*-
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict


@dataclass
class Task:
    """任务记录模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = ""
    status: str = "pending"
    brand_id: str = ""
    result_summary: Dict = field(default_factory=dict)
    error_message: str = ""
    started_at: str = ""
    completed_at: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)
