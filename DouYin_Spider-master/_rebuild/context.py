# -*- coding: utf-8 -*-
"""全局运行上下文：项目根路径、sys.path、工作目录与共享状态。

所有路由模块都通过本模块访问共享全局状态（auth / base_path / daily_monitor 等），
从而把原先的 web_server.py 大文件拆分成多个功能模块。
"""
import os
import sys
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 工作目录切到项目根，保证相对路径（配置/日志/数据）正确
os.chdir(BASE_DIR)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 量化模型目录（如存在也加入 sys.path）
_QUANT_DIR = os.path.join(BASE_DIR, '量化模型')
if _QUANT_DIR not in sys.path:
    sys.path.insert(0, _QUANT_DIR)

# ===== 共享全局状态（由 init_app 初始化）=====
auth = None
base_path = None
daily_monitor = None

radar_lock = threading.Lock()
radar_running = False
radar_last_run = None
radar_last_report = None
radar_root = BASE_DIR
radar_config = os.path.join(BASE_DIR, 'config', 'config.yaml')

radar_log = []
radar_log_lock = threading.Lock()
RADAR_LOG_MAX = 300


def init_app():
    """初始化全局认证与调度器（在启动时、app.run 之前调用一次）。"""
    global auth, base_path, daily_monitor
    from utils.common_util import init as _common_init
    from services import user_auth
    from scheduler.daily_monitor import DailyMonitor
    from loguru import logger

    auth, base_path = _common_init()
    user_auth.ensure_admin()
    user_auth.ensure_user_brands()
    daily_monitor = DailyMonitor(auth)
    daily_monitor.start()
    logger.info('应用初始化完成')
