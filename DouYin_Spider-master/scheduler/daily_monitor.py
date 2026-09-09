# -*- coding: utf-8 -*-
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from loguru import logger

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from dy_apis.douyin_api import DouyinAPI
from models.competitor import Competitor
from models.video import Video
from models.task import Task
from services.storage import load_all, save_one


class DailyMonitor:
    """基于 APScheduler 的每日定时任务调度器"""

    DOUYIN_USER_URL = "https://www.douyin.com/user/{sec_uid}"

    def __init__(self, auth):
        self.auth = auth
        self.scheduler = BackgroundScheduler()
        self._last_tasks = []

    def scan_new_bloggers(self):
        """扫描发现新博主 - 根据品牌画像搜索并将新博主标为待审核"""
        task = Task(
            task_type="scan_bloggers",
            status="running",
            started_at=datetime.now().isoformat()
        )
        task_data = task.to_dict()
        save_one("tasks", task_data)

        new_count = 0
        try:
            brands = load_all("brands")
            existing_competitors = load_all("competitors")
            existing_ids = set(c.get("user_id", "") for c in existing_competitors)

            for brand in brands:
                search_queries = []
                name = brand.get("name", "").strip()
                category = brand.get("category", "").strip()
                if name:
                    search_queries.append(name)
                if category and category not in search_queries:
                    search_queries.append(category)

                for query in search_queries:
                    try:
                        users = DouyinAPI.search_some_user(self.auth, query, 10)
                        for user_data in users:
                            user_info = user_data.get("user_info", {})
                            uid = str(user_info.get("uid", ""))
                            sec_uid = user_info.get("sec_uid", "")
                            nickname = user_info.get("nickname", "")
                            avatar_info = user_info.get("avatar_medium") or user_info.get("avatar_thumb", {})
                            avatar = ""
                            if isinstance(avatar_info, dict):
                                avatar_urls = avatar_info.get("url_list", [])
                                if avatar_urls:
                                    avatar = avatar_urls[0]
                            follower_count = int(user_info.get("follower_count", 0))

                            if not uid or uid in existing_ids:
                                continue

                            competitor = Competitor(
                                user_id=uid,
                                sec_uid=sec_uid,
                                nickname=nickname,
                                avatar=avatar,
                                follower_count=follower_count,
                                category="same_niche",
                                status="reviewing",
                                source_brand_id=brand.get("id", "")
                            )
                            save_one("competitors", competitor.to_dict())
                            existing_ids.add(uid)
                            new_count += 1
                            logger.info(f"发现新博主: {nickname} (uid={uid})")
                    except Exception as e:
                        logger.error(f"搜索品牌 '{query}' 时出错: {e}")

            task_data["status"] = "completed"
            task_data["result_summary"] = {"new_bloggers_found": new_count}
            task_data["completed_at"] = datetime.now().isoformat()
            logger.info(f"扫描新博主完成, 发现 {new_count} 个新博主")
        except Exception as e:
            task_data["status"] = "failed"
            task_data["error_message"] = str(e)
            task_data["completed_at"] = datetime.now().isoformat()
            logger.error(f"扫描新博主失败: {e}")

        save_one("tasks", task_data)
        self._last_tasks.append(task_data)
        if len(self._last_tasks) > 20:
            self._last_tasks = self._last_tasks[-20:]

    def monitor_tracked_bloggers(self):
        """监听已追踪博主的新作品"""
        task = Task(
            task_type="monitor_videos",
            status="running",
            started_at=datetime.now().isoformat()
        )
        task_data = task.to_dict()
        save_one("tasks", task_data)

        new_video_count = 0
        try:
            competitors = load_all("competitors")
            monitoring = [c for c in competitors if c.get("status") == "monitoring"]
            existing_videos = load_all("videos")
            existing_aweme_ids = set(v.get("aweme_id", "") for v in existing_videos)

            for comp in monitoring:
                sec_uid = comp.get("sec_uid", "")
                user_id = comp.get("user_id", "")
                competitor_id = comp.get("id", "")

                if not sec_uid and not user_id:
                    continue

                uid_for_url = sec_uid or user_id
                user_url = self.DOUYIN_USER_URL.format(sec_uid=uid_for_url)

                try:
                    works = DouyinAPI.get_user_all_work_info(self.auth, user_url, max_count=50)
                    for work in works:
                        aweme_id = str(work.get("aweme_id", ""))
                        if not aweme_id or aweme_id in existing_aweme_ids:
                            continue

                        video = Video(
                            aweme_id=aweme_id,
                            title=work.get("desc", ""),
                            description=work.get("desc", ""),
                            cover_url=work.get("video", {}).get("cover", {}).get("url_list", [""])[0] if isinstance(work.get("video"), dict) else "",
                            duration=int(work.get("video", {}).get("duration", 0)) if isinstance(work.get("video"), dict) else 0,
                            author_name=comp.get("nickname", ""),
                            author_id=str(user_id),
                            stats=work.get("statistics", {}),
                            analysis_status="pending",
                            competitor_id=competitor_id
                        )
                        save_one("videos", video.to_dict())
                        existing_aweme_ids.add(aweme_id)
                        new_video_count += 1
                        logger.info(f"发现新视频: {aweme_id} (博主: {comp.get('nickname', '')})")
                except Exception as e:
                    logger.error(f"获取博主 {comp.get('nickname', '')} 作品时出错: {e}")

            task_data["status"] = "completed"
            task_data["result_summary"] = {"new_videos_found": new_video_count}
            task_data["completed_at"] = datetime.now().isoformat()
            logger.info(f"监听博主视频完成, 发现 {new_video_count} 个新视频")
        except Exception as e:
            task_data["status"] = "failed"
            task_data["error_message"] = str(e)
            task_data["completed_at"] = datetime.now().isoformat()
            logger.error(f"监听博主视频失败: {e}")

        save_one("tasks", task_data)
        self._last_tasks.append(task_data)
        if len(self._last_tasks) > 20:
            self._last_tasks = self._last_tasks[-20:]

    def start(self, scan_hour=10, scan_minute=0):
        """启动定时调度
        :param scan_hour: 扫描新博主的小时（默认10点）
        :param scan_minute: 分钟（默认0分）
        """
        self.scheduler.add_job(
            self.scan_new_bloggers,
            CronTrigger(hour=scan_hour, minute=scan_minute),
            id="scan_new_bloggers",
            name="每日扫描新博主",
            replace_existing=True
        )
        self.scheduler.add_job(
            self.monitor_tracked_bloggers,
            CronTrigger(hour=scan_hour + 1, minute=scan_minute),
            id="monitor_tracked_bloggers",
            name="每日监听博主视频",
            replace_existing=True
        )
        self.scheduler.start()
        logger.info(f"每日监听调度器已启动 (扫描: {scan_hour}:{scan_minute:02d}, 监听: {scan_hour + 1}:{scan_minute:02d})")

    def stop(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("每日监听调度器已关闭")

    def get_status(self):
        """返回调度器运行状态和最近任务执行记录"""
        return {
            "running": self.scheduler.running,
            "last_tasks": self._last_tasks[-5:] if self._last_tasks else []
        }
