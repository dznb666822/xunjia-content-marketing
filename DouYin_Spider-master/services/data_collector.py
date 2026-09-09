# -*- coding: utf-8 -*-
"""
数据采集与看板服务
定期拉取监听视频的互动数据，并提供看板数据查询
"""
from datetime import datetime, timedelta

from dy_apis.douyin_api import DouyinAPI
from services.storage import load_all, update_one, find_by


def collect_video_stats(auth) -> dict:
    """
    拉取所有监听视频的最新互动数据。

    遍历所有 videos，通过 DouyinAPI.get_work_info 获取作品详情，
    提取统计信息并更新到存储中。

    Args:
        auth: DouyinAuth 对象

    Returns:
        {"updated_count": N, "errors": [...]}
    """
    videos = load_all("videos")
    errors = []
    updated_count = 0

    for video in videos:
        aweme_id = video.get("aweme_id", "")
        if not aweme_id:
            errors.append({"video_id": video.get("id", ""), "error": "缺少 aweme_id"})
            continue

        work_url = "https://www.douyin.com/video/{}".format(aweme_id)

        try:
            resp_json = DouyinAPI.get_work_info(auth, work_url)
            aweme_detail = resp_json.get("aweme_detail", {})
            if not aweme_detail:
                errors.append({"video_id": video.get("id", ""), "aweme_id": aweme_id,
                               "error": "API 返回未包含 aweme_detail"})
                continue

            statistics = aweme_detail.get("statistics", {})
            # 字段映射：抖音API返回的统计字段
            stats = {
                "digg_count": statistics.get("digg_count", 0),
                "comment_count": statistics.get("comment_count", 0),
                "share_count": statistics.get("share_count", 0),
                "play_count": statistics.get("play_count", 0),
                "collect_count": statistics.get("collect_count", 0),
                "download_count": statistics.get("download_count", 0),
                "forward_count": statistics.get("forward_count", 0),
                "whatsapp_share_count": statistics.get("whatsapp_share_count", 0),
            }

            updates = {
                "stats": stats,
                "updated_at": datetime.now().isoformat()
            }
            update_one("videos", video.get("id"), updates)
            updated_count += 1
        except Exception as e:
            errors.append({
                "video_id": video.get("id", ""),
                "aweme_id": aweme_id,
                "error": str(e)
            })

    return {"updated_count": updated_count, "errors": errors}


def get_dashboard_data(brand_id: str = None, competitor_id: str = None,
                       video_type: str = None, days: int = 30) -> list:
    """
    获取看板数据，支持按品牌、竞品、视频类型和时间范围筛选。

    Args:
        brand_id: 品牌ID，通过 competitor.source_brand_id 关联查找
        competitor_id: 竞品ID，直接筛选
        video_type: 视频类型筛选
        days: 只返回最近N天内的视频

    Returns:
        筛选后的视频数据列表
    """
    videos = load_all("videos")
    if not videos:
        return []

    # 按 brand_id 筛选：找到该品牌下的所有竞品，再筛选视频
    if brand_id:
        related_competitors = find_by("competitors",
                                      lambda c: c.get("source_brand_id") == brand_id)
        related_competitor_ids = {c.get("id") for c in related_competitors}
        videos = [v for v in videos if v.get("competitor_id") in related_competitor_ids]

    # 按 competitor_id 直接筛选
    if competitor_id:
        videos = [v for v in videos if v.get("competitor_id") == competitor_id]

    # 按 video_type 筛选
    if video_type:
        videos = [v for v in videos if v.get("video_type") == video_type]

    # 按时间范围筛选：最近N天
    if days and days > 0:
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()
        videos = [v for v in videos if v.get("first_seen_at", "") >= cutoff_iso]

    return videos
