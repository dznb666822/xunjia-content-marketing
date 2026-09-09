# -*- coding: utf-8 -*-
"""
竞品发现引擎
整合AI关键词提取 + 抖音搜索API，自动搜索对标博主
筛选规则：
  1. 粉丝量级相近：候选粉丝数为当前账号的 1-5 倍
  2. 数据稳定向好：近3个月持续更新，最近10条视频播放量趋势稳定或上升
  3. 内容形式可复制：AI 评估候选的核心优势是否容易复制
"""

import time
import json
import statistics as py_stats
from loguru import logger

from dy_apis.douyin_api import DouyinAPI
from models.competitor import Competitor
from services import ai_keyword
from services.storage import find_by_id, find_by, save_one

# ---- 筛选配置 ----
FOLLOWER_RATIO_MIN = 1.0   # 成长期倍数下限（候选粉丝 / 当前粉丝 >= 1）
FOLLOWER_RATIO_MAX = 5.0   # 成长期倍数上限（候选粉丝 / 当前粉丝 <= 5）
COLD_START_THRESHOLD = 1000   # 当前粉丝低于此值视为"冷启动"，改用绝对区间筛选
COLD_START_FLOOR = 10000      # 冷启动时候选粉丝下限（过滤僵尸/空号）
COLD_START_CEILING = 100000   # 冷启动时候选粉丝上限（避开头部大号，保证可复制性）
MIN_FOLLOWERS = 100        # 候选粉丝最低门槛（硬性要求，低于此值直接不通过）
TREND_LOOKBACK_DAYS = 90   # 数据稳定性回看窗口（近3个月）
TREND_SAMPLE_WORKS = 10    # 播放量趋势采样条数
TREND_MIN_WORKS = 3        # 近3个月最少发布数，低于则视为不活跃
REPLICABILITY_MIN_SCORE = 3  # AI可复制性评分阈值（1-5分，>=3保留）
REPLICABILITY_BATCH_SIZE = 10  # AI可复制性评估每批候选数（控制单次请求大小，避免超时）


def _extract_user_info(user_item):
    """
    从搜索结果中的用户条目提取关键字段。

    兼容两种格式：
    1. {"user_info": {"uid": ..., "sec_uid": ..., "nickname": ..., ...}}
    2. 直接扁平字段

    字段名说明（与抖音 /aweme/v1/web/discover/search 接口 user_info 对应）：
        uid / sec_uid / nickname / follower_count / mplatform_followers_count / avatar_thumb
    """
    if isinstance(user_item, dict) and "user_info" in user_item:
        info = user_item["user_info"]
    else:
        info = user_item

    avatar = info.get("avatar_thumb", {})
    if isinstance(avatar, dict):
        avatar_urls = avatar.get("url_list", [])
        avatar = avatar_urls[0] if avatar_urls else ""
    elif isinstance(avatar, str):
        pass
    else:
        # avatar_medium fallback
        medium = info.get("avatar_medium", {})
        if isinstance(medium, dict):
            avatar_urls = medium.get("url_list", [])
            avatar = avatar_urls[0] if avatar_urls else ""
        else:
            avatar = ""

    # 粉丝数：优先 follower_count，部分账号该字段为0时回退 mplatform_followers_count
    follower_count = info.get("follower_count", 0) or 0
    if not follower_count:
        follower_count = info.get("mplatform_followers_count", 0) or 0

    return {
        "user_id": str(info.get("uid", "")),
        "sec_uid": info.get("sec_uid", ""),
        "nickname": info.get("nickname", ""),
        "avatar": avatar,
        "follower_count": int(follower_count),
    }


def _is_competitor_exists(user_id):
    """检查该 user_id 的竞品是否已存在于存储中"""
    existing = find_by("competitors", lambda c: c.get("user_id") == str(user_id))
    return len(existing) > 0


def _get_user_works(auth, sec_uid):
    """
    拉取单个用户的作品列表（最多拉取若干页）。
    字段名说明（与 /aweme/v1/web/aweme/post 接口 aweme_list 对应）：
        aweme_id / desc / create_time(unix秒) / statistics.play_count / statistics.digg_count
    """
    if not sec_uid:
        return []
    user_url = "https://www.douyin.com/user/{}".format(sec_uid)
    try:
        return DouyinAPI.get_user_all_work_info(auth, user_url)
    except Exception as e:
        logger.warning("拉取用户作品失败 sec_uid={}: {}".format(sec_uid, e))
        return []


def _analyze_video_trend(work_list):
    """
    分析博主的数据稳定性：
    1. 统计近3个月发布的视频数
    2. 取最近 TREND_SAMPLE_WORKS 条视频，比较前后半段点赞数判断趋势

    注意：抖音 web 版列表接口 (/aweme/v1/web/aweme/post) 的 statistics.play_count
    恒为 0（真实播放量仅 app 详情接口返回），因此趋势判断与均量均使用 digg_count（点赞数）。

    返回:
        {
            "recent_count": 近3个月发布数,
            "sample_count": 采样条数,
            "avg_digg": 平均点赞数,
            "avg_play": 平均播放量（真实值，web列表接口通常为0）,
            "trend": "up" / "stable" / "volatile" / "down",
            "recent_works": [{"title", "play_count", "digg_count", "days_ago"}, ...]
        }
    """
    if not work_list:
        return {"recent_count": 0, "sample_count": 0, "avg_digg": 0, "avg_play": 0,
                "trend": "down", "recent_works": []}

    now = time.time()
    recent = []
    for w in work_list:
        try:
            create_time = int(w.get("create_time", 0))
        except (TypeError, ValueError):
            create_time = 0
        if create_time > 0 and (now - create_time) <= TREND_LOOKBACK_DAYS * 86400:
            stats = w.get("statistics", {}) or {}
            try:
                play_count = int(stats.get("play_count", 0) or 0)
            except (TypeError, ValueError):
                play_count = 0
            try:
                digg_count = int(stats.get("digg_count", 0) or 0)
            except (TypeError, ValueError):
                digg_count = 0
            recent.append({
                "title": w.get("desc", "") or "",
                "play_count": play_count,
                "digg_count": digg_count,
                "create_time": create_time,
            })

    if len(recent) < TREND_MIN_WORKS:
        return {"recent_count": len(recent), "sample_count": 0, "avg_digg": 0, "avg_play": 0,
                "trend": "inactive", "recent_works": []}

    # 按发布时间倒序，取最近 TREND_SAMPLE_WORKS 条
    recent.sort(key=lambda x: x["create_time"], reverse=True)
    sample = recent[:TREND_SAMPLE_WORKS]

    # 趋势指标用点赞数（play_count 在 web 列表接口恒为 0）
    digs = [w["digg_count"] for w in sample]
    avg_digg = sum(digs) / len(digs)
    plays = [w["play_count"] for w in sample]
    avg_play = sum(plays) / len(plays)
    half = len(sample) // 2
    first_half_avg = sum(digs[:half]) / max(half, 1)
    second_half_avg = sum(digs[half:]) / max(len(sample) - half, 1)

    # 趋势判定
    if second_half_avg > first_half_avg * 1.1:
        trend = "up"
    elif second_half_avg < first_half_avg * 0.7:
        trend = "down"
    else:
        trend = "stable"

    # 波动率（标准差/均值），>0.6 视为忽高忽低
    if avg_digg > 0 and len(digs) > 1:
        std = py_stats.stdev(digs) if len(digs) > 1 else 0
        if std / avg_digg > 0.6:
            trend = "volatile"

    recent_works = [
        {
            "title": w["title"],
            "play_count": w["play_count"],
            "digg_count": w["digg_count"],
            "days_ago": int((now - w["create_time"]) // 86400),
        }
        for w in sample
    ]
    return {"recent_count": len(recent), "sample_count": len(sample),
            "avg_digg": int(avg_digg), "avg_play": int(avg_play),
            "trend": trend, "recent_works": recent_works}


def _evaluate_replicability(brand, candidates):
    """
    AI 评估候选博主的"内容形式可复制性"。

    通过粉丝倍数 + 数据稳定性筛选的候选，构造作品摘要，
    调用豆包大模型判断其核心优势是否可复制（选题/脚本/拍摄 vs 明星脸/设备/资源）。

    分批调用（每批 REPLICABILITY_BATCH_SIZE 个候选），避免一次性打包
    大量候选导致 prompt 过大、推理模型响应超时；单批失败不影响其他批次。

    返回:
        {user_id: {"score": 1-5, "replicable_points": [], "non_replicable_points": [], "reason": ""}}
    """
    if not candidates:
        return {}

    # 构造品牌画像文本与候选摘要
    brand_text = ai_keyword._build_brand_text(brand)

    candidates_payload = []
    for cand in candidates:
        works = [
            {
                "title": w["title"][:60],
                "digg_count": w["digg_count"],
                "days_ago": w["days_ago"],
            }
            for w in cand.get("recent_works", [])
        ][:6]  # 每个候选最多提交6条作品，控制token
        candidates_payload.append({
            "user_id": cand["user_id"],
            "nickname": cand["nickname"],
            "follower_count": cand["follower_count"],
            "avg_digg": cand.get("avg_digg", 0),
            "trend": cand.get("trend", ""),
            "recent_works": works,
        })

    evaluated = {}
    BATCH_SIZE = REPLICABILITY_BATCH_SIZE
    total_batches = (len(candidates_payload) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(candidates_payload), BATCH_SIZE):
        batch = candidates_payload[i:i + BATCH_SIZE]
        batch_no = i // BATCH_SIZE + 1

        prompt = """你是一个专业的抖音内容拆解专家。请根据以下候选对标博主的近期作品数据，评估每个博主的"内容形式可复制性"。

品牌画像（评估时需结合该品牌可达到的水平）：
{brand_text}

评估原则：
1. 可复制的核心优势（参考价值高）：选题思路、脚本结构、拍摄手法、剪辑节奏、内容形式
2. 难以复制的核心优势（参考价值低）：明星脸/高颜值出镜、昂贵专业设备、独家资源/渠道、依赖超级粉丝基本盘的爆款

候选博主数据：
{candidates_json}

请为每个博主输出 1-5 分的可复制性评分（5=非常容易复制，1=几乎无法复制），只输出JSON：
{{
    "results": [
        {{
            "user_id": "候选的user_id",
            "score": 3,
            "replicable_points": ["可复制的优势点"],
            "non_replicable_points": ["难以复制的优势点"],
            "reason": "综合判断理由"
        }}
    ]
}}""".format(
            brand_text=brand_text,
            candidates_json=json.dumps(batch, ensure_ascii=False),
        )

        try:
            response_text = ai_keyword._call_ai(prompt)
            result = ai_keyword._parse_json_response(response_text)
            results = result.get("results", []) if isinstance(result, dict) else []
            for item in results:
                uid = str(item.get("user_id", ""))
                if uid:
                    evaluated[uid] = {
                        "score": int(item.get("score", 0) or 0),
                        "replicable_points": item.get("replicable_points", []),
                        "non_replicable_points": item.get("non_replicable_points", []),
                        "reason": item.get("reason", ""),
                    }
            logger.info(f"可复制性评估批次 {batch_no}/{total_batches} 完成, 解析 {len(results)} 个博主")
        except Exception as e:
            logger.error(f"AI可复制性评估批次 {batch_no}/{total_batches} 失败: {type(e).__name__}: {e}")

    return evaluated


def discover_same_niche(auth, brand_id: str, my_follower_count: int = 0) -> dict:
    """
    搜索同赛道对标博主（三步筛选）。

    1. 从 storage 加载品牌画像
    2. 调用 AI 提取关键词
    3. 遍历 category_keywords，调用抖音搜索用户
    4. 去重得到候选池
    5. 筛选一（粉丝量级相近，分段策略）：
       - 冷启动（当前粉丝 < COLD_START_THRESHOLD）：候选粉丝取绝对区间 [COLD_START_FLOOR, COLD_START_CEILING]
       - 有基本盘（当前粉丝 >= COLD_START_THRESHOLD）：候选粉丝为当前的 [FOLLOWER_RATIO_MIN, FOLLOWER_RATIO_MAX] 倍
    6. 筛选二（数据稳定向好）：近3个月持续更新，最近10条视频播放量趋势稳定/上升
    7. 筛选三（内容形式可复制）：AI 评估核心优势是否容易复制（评分>=3保留）
    8. 通过者自动持久化到 competitors 存储

    参数:
        auth: DouyinAuth 对象
        brand_id: 品牌画像 ID
        my_follower_count: 当前账号粉丝数；-1/None 跳过粉丝筛选，>=0 时启用（0 视为冷启动）

    返回:
        {
            "brand_id", "competitors", "keywords_used", "total_found",
            "filter_stats": 各筛选阶段淘汰统计（含 follower_mode）,
            "errors"
        }
    """
    brand = find_by_id("brands", brand_id)
    if brand is None:
        logger.error(f"品牌画像不存在: {brand_id}")
        return {"brand_id": brand_id, "competitors": [], "keywords_used": [], "total_found": 0}

    logger.info(f"开始同赛道竞品发现, 品牌: {brand.get('name', '')} (ID: {brand_id}), 当前粉丝数: {my_follower_count}")

    # 调用 AI 提取关键词
    try:
        keywords_result = ai_keyword.extract_keywords(brand)
    except Exception as e:
        logger.error(f"AI关键词提取失败: {e}")
        return {"brand_id": brand_id, "competitors": [], "keywords_used": [], "total_found": 0}

    category_keywords = keywords_result.get("category_keywords", [])
    logger.info(f"获取到 {len(category_keywords)} 个品类关键词: {category_keywords}")

    # ===== 搜索去重，构建候选池 =====
    seen_ids = set()
    candidates = []
    errors = []

    for keyword in category_keywords:
        logger.info(f"搜索关键词: {keyword}")
        try:
            users = DouyinAPI.search_some_user(auth, keyword, 10)
        except Exception as e:
            logger.warning(f"搜索关键词 '{keyword}' 失败: {e}")
            errors.append({"keyword": keyword, "error": str(e)})
            continue

        for user_item in users:
            info = _extract_user_info(user_item)
            uid = info["user_id"]
            if not uid or uid in seen_ids:
                continue
            seen_ids.add(uid)
            info["keyword"] = keyword
            candidates.append(info)

    logger.info(f"搜索完成, 候选博主 {len(candidates)} 个")

    # ===== 筛选统计 =====
    filter_stats = {
        "total_candidates": len(candidates),
        "follower_mode": "disabled",
        "follower_pass": 0,
        "follower_fail": 0,
        "trend_pass": 0,
        "trend_fail": 0,
        "replicability_pass": 0,
        "replicability_fail": 0,
        "ai_eval_failed": 0,
    }

    # ===== 筛选一：粉丝量级相近（分段策略，只标注不淘汰） =====
    # 模式说明：
    #   disabled    未传当前粉丝数，跳过筛选
    #   cold_start  当前账号 < COLD_START_THRESHOLD（冷启动）：候选粉丝取绝对区间 [COLD_START_FLOOR, COLD_START_CEILING]
    #   ratio       当前账号已有基本盘：候选粉丝为当前的 [FOLLOWER_RATIO_MIN, FOLLOWER_RATIO_MAX] 倍
    follower_filter_mode = "disabled"
    if my_follower_count is not None and my_follower_count >= 0:
        if my_follower_count < COLD_START_THRESHOLD:
            follower_filter_mode = "cold_start"
            for cand in candidates:
                fans = cand["follower_count"]
                if fans < MIN_FOLLOWERS:
                    ok, reason = False, f"粉丝 {fans}，低于最低门槛 {MIN_FOLLOWERS}"
                elif COLD_START_FLOOR <= fans <= COLD_START_CEILING:
                    ok, reason = True, f"粉丝 {fans}，在冷启动区间 [{COLD_START_FLOOR}, {COLD_START_CEILING}] 内"
                elif fans < COLD_START_FLOOR:
                    ok, reason = False, f"粉丝 {fans}，低于冷启动下限 {COLD_START_FLOOR}（疑似僵尸/空号）"
                else:
                    ok, reason = False, f"粉丝 {fans}，超出冷启动上限 {COLD_START_CEILING}（头部大号，冷启动难复制）"
                cand["follower_check"] = {"pass": ok, "mode": follower_filter_mode, "reason": reason}
                filter_stats["follower_pass" if ok else "follower_fail"] += 1
        else:
            follower_filter_mode = "ratio"
            for cand in candidates:
                fans = cand["follower_count"]
                ratio = fans / my_follower_count if my_follower_count > 0 else 0
                if fans < MIN_FOLLOWERS:
                    ok, reason = False, f"粉丝 {fans}，低于最低门槛 {MIN_FOLLOWERS}"
                elif FOLLOWER_RATIO_MIN <= ratio <= FOLLOWER_RATIO_MAX:
                    ok, reason = True, f"粉丝 {fans}，为当前的 {ratio:.2f} 倍（区间 {FOLLOWER_RATIO_MIN}-{FOLLOWER_RATIO_MAX}）"
                else:
                    ok, reason = False, f"粉丝 {fans}，为当前的 {ratio:.2f} 倍，超出区间 {FOLLOWER_RATIO_MIN}-{FOLLOWER_RATIO_MAX}"
                cand["follower_check"] = {"pass": ok, "mode": follower_filter_mode, "reason": reason, "ratio": round(ratio, 2)}
                filter_stats["follower_pass" if ok else "follower_fail"] += 1
        filter_stats["follower_mode"] = follower_filter_mode
    else:
        # 未启用粉丝筛选：全部标记通过
        for cand in candidates:
            cand["follower_check"] = {"pass": True, "mode": "disabled", "reason": "未填写当前粉丝数，未启用粉丝筛选"}
        filter_stats["follower_pass"] = len(candidates)
    logger.info(f"筛选一(粉丝量级, {follower_filter_mode}): 通过 {filter_stats['follower_pass']}, 未通过 {filter_stats['follower_fail']}")

    # ===== 筛选二：数据稳定向好（拉取作品分析趋势，只标注不淘汰） =====
    for cand in candidates:
        works = _get_user_works(auth, cand.get("sec_uid", ""))
        trend = _analyze_video_trend(works)
        cand.update(trend)  # recent_count / sample_count / avg_digg / avg_play / trend / recent_works
        t = trend["trend"]
        if t in ("up", "stable"):
            ok = True
            reason = f"近3月发布 {trend['recent_count']} 条，均赞 {trend['avg_digg']}，趋势 {t}"
        elif t == "inactive":
            ok = False
            reason = f"近3月仅发布 {trend['recent_count']} 条（少于 {TREND_MIN_WORKS} 条），不活跃"
        elif t == "down":
            ok = False
            reason = f"近3月发布 {trend['recent_count']} 条，均赞 {trend['avg_digg']}，数据整体下降"
        else:  # volatile
            ok = False
            reason = f"均赞 {trend['avg_digg']}，数据波动剧烈（爆款后回落风险）"
        cand["trend_check"] = {"pass": ok, "trend": t, "recent_count": trend["recent_count"],
                               "avg_digg": trend["avg_digg"], "reason": reason}
        filter_stats["trend_pass" if ok else "trend_fail"] += 1
        logger.info(f"  趋势评估: {cand['nickname']} [{t}] {'通过' if ok else '未通过'} - {reason}")
    logger.info(f"筛选二(数据稳定): 通过 {filter_stats['trend_pass']}, 未通过 {filter_stats['trend_fail']}")

    # ===== 筛选三：AI 内容可复制性评估（仅前两条都通过的候选） =====
    # 前置门槛：粉丝量级通过（筛选一）且数据稳定通过（筛选二）才进入AI评估
    ai_candidates = [
        cand for cand in candidates
        if cand.get("follower_check", {}).get("pass") is True
        and cand.get("trend_check", {}).get("pass") is True
    ]
    logger.info(f"筛选三前置门槛: {len(ai_candidates)}/{len(candidates)} 个候选进入AI可复制性评估")

    evaluated = {}
    if ai_candidates:
        evaluated = _evaluate_replicability(brand, ai_candidates)
        if not evaluated:
            filter_stats["ai_eval_failed"] = len(ai_candidates)
            logger.warning("AI可复制性评估全部失败, 相关候选标记为待人工判断")

    for cand in candidates:
        # 未通过前两条筛选的候选不进入AI评估
        if cand.get("follower_check", {}).get("pass") is not True or cand.get("trend_check", {}).get("pass") is not True:
            cand["replicability_check"] = {"pass": None, "score": None,
                                           "reason": "未进入AI评估：粉丝量级或数据稳定性未达标"}
            continue
        eval_info = evaluated.get(cand["user_id"])
        if eval_info is None:
            cand["replicability_check"] = {"pass": None, "score": None, "reason": "AI 评估失败，待人工判断"}
        else:
            score = eval_info["score"]
            ok = score >= REPLICABILITY_MIN_SCORE
            reason = f"可复制性评分 {score}/5"
            if eval_info.get("replicable_points"):
                reason += f"，可复制点: {'、'.join(eval_info['replicable_points'][:2])}"
            if eval_info.get("non_replicable_points"):
                reason += f"，难点: {'、'.join(eval_info['non_replicable_points'][:2])}"
            cand["replicability_check"] = {"pass": ok, "score": score, "reason": reason}
            filter_stats["replicability_pass" if ok else "replicability_fail"] += 1

    # ===== 保存全部候选（含未通过筛选的，供人工复核） =====
    competitors = []
    for cand in candidates:
        uid = cand["user_id"]
        if _is_competitor_exists(uid):
            continue

        # 组装筛选评估（供前端标注理由）
        filters = []
        if cand.get("follower_check"):
            filters.append(cand["follower_check"])
        if cand.get("trend_check"):
            filters.append(cand["trend_check"])
        if cand.get("replicability_check"):
            filters.append(cand["replicability_check"])
        passed = sum(1 for f in filters if f.get("pass") is True)

        notes = f"关键词: {cand.get('keyword', '')}"
        notes += f" | 筛选: {passed}/{len(filters)} 通过"
        if cand.get("trend"):
            notes += f" | 近3月发布: {cand.get('recent_count', 0)} | 均赞: {cand.get('avg_digg', 0)} | 趋势: {cand.get('trend', '')}"

        competitor = Competitor(
            user_id=uid,
            sec_uid=cand.get("sec_uid", ""),
            nickname=cand.get("nickname", ""),
            avatar=cand.get("avatar", ""),
            follower_count=cand.get("follower_count", 0),
            category="same_niche",
            status="pending",  # 待人工复核，不会进入自动监听
            notes=notes,
            source_brand_id=brand_id,
        )
        competitor_dict = competitor.to_dict()
        competitor_dict["filters"] = filters      # 供前端展示筛选理由
        competitor_dict["pass_count"] = passed    # 供前端排序/标记

        try:
            save_one("competitors", competitor_dict)
            competitors.append(competitor_dict)
            logger.info(f"  保存候选: {cand['nickname']} (粉丝: {cand['follower_count']}, 筛选通过: {passed}/{len(filters)})")
        except Exception as e:
            logger.warning(f"持久化竞品失败 {cand['nickname']}: {e}")

    # 排序：筛选通过数多的在前，同通过数按粉丝降序
    competitors.sort(key=lambda c: (c.get("pass_count", 0), c.get("follower_count", 0)), reverse=True)

    logger.info(f"同赛道竞品发现完成, 共展示 {len(competitors)} 个候选")

    return {
        "brand_id": brand_id,
        "competitors": competitors,
        "keywords_used": category_keywords,
        "total_found": len(competitors),
        "filter_stats": filter_stats,
        "errors": errors,
    }


def discover_cross_category(auth, brand_id: str) -> dict:
    """
    搜索跨赛道对标博主。

    1. 从 storage 加载品牌画像
    2. 调用 AI 推荐跨赛道品类
    3. 对每个推荐品类，用其 search_keywords 搜索用户
    4. 去重合并结果

    参数:
        auth: DouyinAuth 对象
        brand_id: 品牌画像 ID

    返回:
        {"brand_id": ..., "categories": [...], "competitors": [...]}
    """
    brand = find_by_id("brands", brand_id)
    if brand is None:
        logger.error(f"品牌画像不存在: {brand_id}")
        return {"brand_id": brand_id, "categories": [], "competitors": []}

    logger.info(f"开始跨赛道竞品发现, 品牌: {brand.get('name', '')} (ID: {brand_id})")

    # 调用 AI 推荐跨赛道品类
    try:
        cross_result = ai_keyword.recommend_cross_categories(brand)
    except Exception as e:
        logger.error(f"AI跨赛道推荐失败: {e}")
        return {"brand_id": brand_id, "categories": [], "competitors": []}

    categories = cross_result.get("categories", [])
    logger.info(f"获取到 {len(categories)} 个跨赛道推荐")

    # 搜索并去重
    seen_ids = set()
    all_competitors = []
    errors = []

    for cat in categories:
        cat_name = cat.get("name", "未知品类")
        search_keywords = cat.get("search_keywords", [])
        logger.info(f"搜索跨赛道品类: {cat_name}, 关键词: {search_keywords}")

        for keyword in search_keywords:
            try:
                users = DouyinAPI.search_some_user(auth, keyword, 10)
            except Exception as e:
                logger.warning(f"搜索关键词 '{keyword}' 失败: {e}")
                errors.append({"keyword": keyword, "error": str(e)})
                continue

            for user_item in users:
                info = _extract_user_info(user_item)
                uid = info["user_id"]
                if not uid or uid in seen_ids:
                    continue
                seen_ids.add(uid)

                # 构建 Competitor 实例
                competitor = Competitor(
                    user_id=info["user_id"],
                    sec_uid=info["sec_uid"],
                    nickname=info["nickname"],
                    avatar=info["avatar"],
                    follower_count=info["follower_count"],
                    category="cross_niche",
                    status="monitoring",
                    notes=f"[{cat_name}] {cat.get('reason', '')}",
                    source_brand_id=brand_id,
                )
                competitor_dict = competitor.to_dict()

                if _is_competitor_exists(uid):
                    continue

                try:
                    save_one("competitors", competitor_dict)
                    all_competitors.append(competitor_dict)
                    logger.info(f"  新增竞品: {info['nickname']} (粉丝: {info['follower_count']})")
                except Exception as e:
                    logger.warning(f"持久化竞品失败 {info['nickname']}: {e}")

    # 按粉丝数降序排列
    all_competitors.sort(key=lambda c: c.get("follower_count", 0), reverse=True)

    logger.info(f"跨赛道竞品发现完成, 共找到 {len(all_competitors)} 个新竞品")

    return {
        "brand_id": brand_id,
        "categories": categories,
        "competitors": all_competitors,
        "errors": errors,
    }
