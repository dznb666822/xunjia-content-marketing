# -*- coding: utf-8 -*-
"""AI 剪辑模块 · 存储与体检层。

对外暴露：
    store       —— 独立 DAL（不走 services.storage 门面）
    projects    —— 项目业务逻辑
    materials   —— 素材业务逻辑（导入 / 去重 / 项目引用）
    probe       —— 素材体检（ffprobe + PIL 实测，零 LLM）
    paths       —— 文件仓路径规则
    ark         —— 火山方舟全模态调用层
    understand  —— 素材理解流水线（音画分离 → 可编排单元）
"""

from services.aiclip import paths  # noqa: F401
from services.aiclip import store  # noqa: F401
from services.aiclip import probe  # noqa: F401
from services.aiclip import projects  # noqa: F401
from services.aiclip import materials  # noqa: F401
from services.aiclip import ark  # noqa: F401
from services.aiclip import understand  # noqa: F401

__all__ = ['paths', 'store', 'probe', 'projects', 'materials', 'ark', 'understand']
