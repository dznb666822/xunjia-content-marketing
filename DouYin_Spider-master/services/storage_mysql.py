# -*- coding: utf-8 -*-
"""
MySQL 持久化服务 - 通用 CRUD 操作

与 services/storage.py（JSON 后端）提供完全相同的 7 个对外函数签名：
    save_all / load_all / save_one / update_one / delete_one / find_by_id / find_by

字段映射原则（详见 .trae/documents/MySQL数据库表与字段设计方案.md）：
    - 标量字段 → MySQL 真实列
    - 嵌套 dict/list → MySQL JSON 列（原样 json.dumps 存、json.loads 读）
    - videos.stats → 单个 JSON 列，不拆列（键数可变，拆列会丢数据）

连接参数通过环境变量读取：
    MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DB
"""
import json
import os
import threading

import pymysql
from loguru import logger

# ---- 连接配置 ----
_MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
_MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
_MYSQL_USER = os.environ.get("MYSQL_USER", "root")
_MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
_MYSQL_DB = os.environ.get("MYSQL_DB", "douyin_spider")

# ---- 每张表的列清单（顺序即建表顺序） ----
_TABLES = {
    "brands": [
        "id", "name", "category", "target_audience", "product_desc",
        "style_tone", "selling_points", "skus", "context_file", "owner_id",
        "created_at", "updated_at",
    ],
    "competitors": [
        "id", "user_id", "sec_uid", "nickname", "avatar", "follower_count",
        "category", "status", "notes", "source_brand_id", "filters",
        "pass_count", "owner_id", "created_at", "updated_at",
    ],
    "tasks": [
        "id", "task_type", "status", "brand_id", "result_summary",
        "error_message", "started_at", "completed_at", "owner_id", "created_at",
    ],
    "videos": [
        "id", "aweme_id", "title", "description", "cover_url", "video_url",
        "local_path", "duration", "author_name", "author_id", "stats",
        "analysis_status", "text_structure", "video_type", "scene_desc",
        "cover_desc", "mood", "scripts", "competitor_id", "product_analysis",
        "marketing_strategy", "storyboard", "storyboard_frames",
        "generated_scripts", "script_user_prompt", "first_seen_at",
        "owner_id", "created_at", "updated_at",
    ],
    "users": [
        "id", "username", "password_hash", "role", "features",
        "created_at", "updated_at",
    ],
    "media_library": [
        "id", "filename", "path", "classification", "timeline", "sku_id", "aspect_ratio", "owner_id",
        "created_at", "updated_at",
    ],
    "mashup_results": [
        "id", "task_id", "brand_id", "sku_id", "sku_name", "script",
        "output_path", "output_filename", "duration", "segments",
        "owner_id", "created_at",
    ],
    "intent_analysis": [
        "id", "work_url", "video_title", "analyzed_at", "total",
        "summary", "results", "created_at",
    ],
    "price_research": [
        "id", "keyword", "platform", "platform_name", "products_count",
        "created_at", "products",
    ],
    "xiaohongshu_import": [
        "id", "keyword", "notes", "imported_at", "created_at",
    ],
    "trend_samples": [
        "id", "keyword", "snapshot_at", "douyin_works", "taobao_products",
        "bilibili_works", "suppliers", "group_scores", "features",
        "trend_score", "lifecycle", "label_30d", "label_60d", "created_at",
    ],
    "comic_designs": [
        "id", "title", "script_text", "art_result", "storyboard_result",
        "video_result", "owner_id", "created_at", "updated_at",
    ],
    # AI 自动剪辑 V2.0 — 剪辑方案主表(SOP §13.2.2)
    "ai_clip_video_plans": [
        "id", "source_video_id", "style_id", "style_snapshot", "plan_json",
        "analyzer_meta", "planner_model", "status", "owner_id",
        "created_at", "updated_at",
    ],
}

# ---- 每张表的 JSON 列（写入时 json.dumps，读取时 json.loads） ----
_JSON_COLUMNS = {
    "brands": {"selling_points", "skus"},
    "competitors": {"filters"},
    "tasks": {"result_summary"},
    "videos": {
        "stats", "text_structure", "scripts", "product_analysis",
        "marketing_strategy", "storyboard", "storyboard_frames",
        "generated_scripts",
    },
    "users": {"features"},
    "media_library": {"classification", "timeline"},
    "mashup_results": {"segments"},
    "intent_analysis": {"summary", "results"},
    "price_research": {"products"},
    "xiaohongshu_import": {"notes"},
    "trend_samples": {"group_scores", "features"},
}

# ---- 建表语句（CREATE TABLE IF NOT EXISTS） ----
_SCHEMA = {
    "brands": """
        CREATE TABLE IF NOT EXISTS brands (
          id               VARCHAR(36)  PRIMARY KEY,
          name             VARCHAR(255) NOT NULL DEFAULT '',
          category         VARCHAR(255) NOT NULL DEFAULT '',
          target_audience  TEXT,
          product_desc     TEXT,
          style_tone       TEXT,
          selling_points   JSON,
          skus             JSON,
          context_file     VARCHAR(255) NULL,
          owner_id         VARCHAR(36) NULL,
          created_at       VARCHAR(32),
          updated_at       VARCHAR(32)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "competitors": """
        CREATE TABLE IF NOT EXISTS competitors (
          id              VARCHAR(36)  PRIMARY KEY,
          user_id         VARCHAR(64),
          sec_uid         VARCHAR(255),
          nickname        VARCHAR(255),
          avatar          TEXT,
          follower_count  BIGINT DEFAULT 0,
          category        VARCHAR(64) DEFAULT 'same_niche',
          status          VARCHAR(32) DEFAULT 'monitoring',
          notes           TEXT,
          source_brand_id VARCHAR(36),
          filters         JSON,
          pass_count      INT DEFAULT 0,
          owner_id        VARCHAR(36) NULL,
          created_at      VARCHAR(32),
          updated_at      VARCHAR(32),
          INDEX idx_source_brand (source_brand_id),
          INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "tasks": """
        CREATE TABLE IF NOT EXISTS tasks (
          id             VARCHAR(36) PRIMARY KEY,
          task_type      VARCHAR(64),
          status         VARCHAR(32) DEFAULT 'pending',
          brand_id       VARCHAR(36),
          result_summary JSON,
          error_message  TEXT,
          started_at     VARCHAR(32),
          completed_at   VARCHAR(32),
          owner_id       VARCHAR(36) NULL,
          created_at     VARCHAR(32),
          INDEX idx_brand (brand_id),
          INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "videos": """
        CREATE TABLE IF NOT EXISTS videos (
          id                 VARCHAR(36)  PRIMARY KEY,
          aweme_id           VARCHAR(64),
          title              TEXT,
          description        TEXT,
          cover_url          TEXT,
          video_url          TEXT,
          local_path         TEXT,
          duration           INT DEFAULT 0,
          author_name        VARCHAR(255),
          author_id          VARCHAR(64),
          stats              JSON,
          analysis_status    VARCHAR(32) DEFAULT 'pending',
          text_structure     JSON,
          video_type         VARCHAR(64),
          scene_desc         TEXT,
          cover_desc         TEXT,
          mood               VARCHAR(64),
          scripts            JSON,
          competitor_id      VARCHAR(36),
          product_analysis   JSON,
          marketing_strategy JSON,
          storyboard         JSON,
          storyboard_frames  JSON,
          generated_scripts  JSON,
          script_user_prompt TEXT,
          first_seen_at      VARCHAR(32),
          owner_id           VARCHAR(36) NULL,
          created_at         VARCHAR(32),
          updated_at         VARCHAR(32),
          INDEX idx_competitor (competitor_id),
          INDEX idx_aweme (aweme_id),
          INDEX idx_analysis_status (analysis_status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "users": """
        CREATE TABLE IF NOT EXISTS users (
          id            VARCHAR(36)  PRIMARY KEY,
          username      VARCHAR(64)  NOT NULL,
          password_hash VARCHAR(255) NOT NULL DEFAULT '',
          role          VARCHAR(16)  NOT NULL DEFAULT 'user',
          features      JSON,
          created_at    VARCHAR(32),
          updated_at    VARCHAR(32),
          UNIQUE KEY uk_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "media_library": """
        CREATE TABLE IF NOT EXISTS media_library (
          id             VARCHAR(36)  PRIMARY KEY,
          filename       VARCHAR(512) NOT NULL DEFAULT '',
          path           VARCHAR(1024) NOT NULL DEFAULT '',
          classification JSON,
          timeline       JSON,
          sku_id         VARCHAR(36) NULL,
          aspect_ratio   VARCHAR(16) NULL,
          owner_id       VARCHAR(36) NULL,
          created_at     VARCHAR(32),
          updated_at     VARCHAR(32),
          INDEX idx_owner (owner_id),
          INDEX idx_sku (sku_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "mashup_results": """
        CREATE TABLE IF NOT EXISTS mashup_results (
          id              VARCHAR(36)  PRIMARY KEY,
          task_id         VARCHAR(36),
          brand_id        VARCHAR(36),
          sku_id          VARCHAR(36),
          sku_name        VARCHAR(255),
          script          TEXT,
          output_path     VARCHAR(1024),
          output_filename VARCHAR(255),
          duration        FLOAT DEFAULT 0,
          segments        JSON,
          owner_id        VARCHAR(36) NULL,
          created_at      VARCHAR(32),
          INDEX idx_task (task_id),
          INDEX idx_sku (sku_id),
          INDEX idx_owner (owner_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "intent_analysis": """
        CREATE TABLE IF NOT EXISTS intent_analysis (
          id            VARCHAR(36)  PRIMARY KEY,
          work_url      TEXT,
          video_title   TEXT,
          analyzed_at   VARCHAR(32),
          total         INT DEFAULT 0,
          summary       JSON,
          results       JSON,
          created_at    VARCHAR(32)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "price_research": """
        CREATE TABLE IF NOT EXISTS price_research (
          id             VARCHAR(36)  PRIMARY KEY,
          keyword        VARCHAR(255),
          platform       VARCHAR(32),
          platform_name  VARCHAR(64),
          products_count INT DEFAULT 0,
          created_at     VARCHAR(32),
          products       JSON
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "xiaohongshu_import": """
        CREATE TABLE IF NOT EXISTS xiaohongshu_import (
          id          VARCHAR(36)  PRIMARY KEY,
          keyword     VARCHAR(255),
          notes       JSON,
          imported_at VARCHAR(32),
          created_at  VARCHAR(32),
          INDEX idx_keyword (keyword)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "trend_samples": """
        CREATE TABLE IF NOT EXISTS trend_samples (
          id             VARCHAR(36)  PRIMARY KEY,
          keyword        VARCHAR(255),
          snapshot_at    VARCHAR(32),
          douyin_works   INT DEFAULT 0,
          taobao_products INT DEFAULT 0,
          bilibili_works INT DEFAULT 0,
          suppliers      INT DEFAULT 0,
          group_scores   JSON,
          features       JSON,
          trend_score    FLOAT DEFAULT 0,
          lifecycle      VARCHAR(32),
          label_30d      FLOAT NULL,
          label_60d      FLOAT NULL,
          created_at     VARCHAR(32),
          INDEX idx_keyword (keyword),
          INDEX idx_snapshot (snapshot_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "comic_designs": """
        CREATE TABLE IF NOT EXISTS comic_designs (
          id                 VARCHAR(36)  PRIMARY KEY,
          title              VARCHAR(255),
          script_text        MEDIUMTEXT,
          art_result         MEDIUMTEXT,
          storyboard_result  MEDIUMTEXT,
          video_result       MEDIUMTEXT,
          owner_id           VARCHAR(36) NULL,
          created_at         VARCHAR(32),
          updated_at         VARCHAR(32),
          INDEX idx_owner (owner_id),
          INDEX idx_updated (updated_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # AI 自动剪辑 V2.0 — 剪辑方案主表(SOP §13.2.2)
    # plan_json 存完整 VideoPlan JSON(片段+包装+画面素材+Style),MEDIUMTEXT 业务层自管
    "ai_clip_video_plans": """
        CREATE TABLE IF NOT EXISTS ai_clip_video_plans (
          id               VARCHAR(36)  PRIMARY KEY,
          source_video_id  VARCHAR(36)  NULL,
          style_id         VARCHAR(36)  NULL,
          style_snapshot   MEDIUMTEXT,
          plan_json        MEDIUMTEXT,
          analyzer_meta    MEDIUMTEXT,
          planner_model    VARCHAR(64),
          status           VARCHAR(32)  DEFAULT 'draft',
          owner_id         VARCHAR(36)  NULL,
          created_at       VARCHAR(32),
          updated_at       VARCHAR(32),
          INDEX idx_owner (owner_id),
          INDEX idx_status (status),
          INDEX idx_video (source_video_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}

# ---- 懒初始化状态（保证建库/建表只执行一次，且线程安全） ----
_init_lock = threading.Lock()
_db_ready = False
_ready_tables = set()

# 需要按用户隔离数据的实体（用于给旧表幂等补齐 owner_id 列）
_OWNER_ENTITIES = {"brands", "competitors", "videos", "tasks", "media_library", "mashup_results", "comic_designs", "ai_clip_video_plans"}


def _get_conn():
    """创建一个新的 MySQL 连接（DictCursor 便于按列名取值）"""
    return pymysql.connect(
        host=_MYSQL_HOST,
        port=_MYSQL_PORT,
        user=_MYSQL_USER,
        password=_MYSQL_PASSWORD,
        database=_MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _get_server_conn():
    """创建一个不指定 database 的连接（用于建库）"""
    return pymysql.connect(
        host=_MYSQL_HOST,
        port=_MYSQL_PORT,
        user=_MYSQL_USER,
        password=_MYSQL_PASSWORD,
        charset="utf8mb4",
    )


def _ensure_database():
    """确保目标数据库存在"""
    conn = _get_server_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE DATABASE IF NOT EXISTS `{}` DEFAULT CHARACTER SET utf8mb4".format(_MYSQL_DB)
            )
        conn.commit()
    finally:
        conn.close()


def _ensure_table(entity):
    """确保实体对应的表存在（首次使用时建库 + 建表）"""
    global _db_ready
    if entity not in _TABLES:
        raise ValueError("未知实体: {}".format(entity))

    with _init_lock:
        if not _db_ready:
            _ensure_database()
            _db_ready = True
        if entity in _ready_tables:
            return
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA[entity])
            conn.commit()
        finally:
            conn.close()
        _ready_tables.add(entity)
        # 兼容已存在的旧表：幂等补齐 owner_id 列
        if entity in _OWNER_ENTITIES:
            _ensure_column(entity, "owner_id", "VARCHAR(36) NULL")
        # 兼容已存在的 users 旧表：幂等补齐 features 列
        if entity == "users":
            _ensure_column(entity, "features", "JSON")
        # 兼容已存在的 brands 旧表：幂等补齐 skus 列
        if entity == "brands":
            _ensure_column(entity, "skus", "JSON")
        # 兼容已存在的 media_library 旧表：幂等补齐 sku_id / aspect_ratio 列
        if entity == "media_library":
            _ensure_column(entity, "sku_id", "VARCHAR(36) NULL")
            _ensure_column(entity, "aspect_ratio", "VARCHAR(16) NULL")


def _ensure_column(entity, column_name, column_type):
    """为已存在的表补齐缺失列（幂等）。"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM `{}` LIKE '{}'".format(entity, column_name))
            if cur.fetchone() is None:
                cur.execute(
                    "ALTER TABLE `{}` ADD COLUMN {} {}".format(entity, column_name, column_type)
                )
        conn.commit()
    finally:
        conn.close()


def _encode_values(entity, data):
    """将传入的 dict 编码为可写入 MySQL 的列值。

    - 过滤掉不在表结构中的未知字段（并打日志，避免静默丢数据）
    - JSON 列做 json.dumps
    """
    json_cols = _JSON_COLUMNS.get(entity, set())
    table_cols = set(_TABLES.get(entity, []))
    encoded = {}
    for k, v in data.items():
        if k not in table_cols:
            logger.warning("MySQL 存储：实体 {} 含未知字段 {}，已忽略".format(entity, k))
            continue
        if k in json_cols:
            encoded[k] = json.dumps(v, ensure_ascii=False) if v is not None else None
        else:
            encoded[k] = v
    return encoded


def _decode_row(entity, row):
    """将 MySQL 行 dict 还原为与 JSON 后端一致的 item dict。

    - JSON 列做 json.loads
    - 值为 None 的列直接跳过（与 JSON 后端"字段不存在"语义一致）
    """
    if row is None:
        return None
    json_cols = _JSON_COLUMNS.get(entity, set())
    item = {}
    for col, val in row.items():
        if val is None:
            continue
        if col in json_cols:
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            item[col] = val
        else:
            item[col] = val
    return item


def save_all(entity_name, data_list):
    """覆盖写入实体全部数据（TRUNCATE 语义 + 批量插入）"""
    _ensure_table(entity_name)
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `{}`".format(entity_name))
            for item in data_list:
                encoded = _encode_values(entity_name, item)
                if not encoded:
                    continue
                cols = list(encoded.keys())
                placeholders = ", ".join(["%s"] * len(cols))
                sql = "INSERT INTO `{}` ({}) VALUES ({})".format(
                    entity_name,
                    ", ".join("`{}`".format(c) for c in cols),
                    placeholders,
                )
                cur.execute(sql, [encoded[c] for c in cols])
        conn.commit()
    finally:
        conn.close()


def load_all(entity_name):
    """加载实体全部数据"""
    _ensure_table(entity_name)
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM `{}`".format(entity_name))
            rows = cur.fetchall()
        return [_decode_row(entity_name, r) for r in rows]
    finally:
        conn.close()


def save_one(entity_name, item):
    """保存单条记录（追加）"""
    _ensure_table(entity_name)
    encoded = _encode_values(entity_name, item)
    if not encoded:
        logger.warning("MySQL 存储：实体 {} 无可写入字段".format(entity_name))
        return item
    cols = list(encoded.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    sql = "INSERT INTO `{}` ({}) VALUES ({})".format(
        entity_name,
        ", ".join("`{}`".format(c) for c in cols),
        placeholders,
    )
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, [encoded[c] for c in cols])
        conn.commit()
    finally:
        conn.close()
    return item


def update_one(entity_name, item_id, updates):
    """更新指定ID的记录，返回更新后的完整记录，未找到返回 None"""
    _ensure_table(entity_name)
    existing = find_by_id(entity_name, item_id)
    if existing is None:
        return None

    encoded = _encode_values(entity_name, updates)
    if encoded:
        set_clause = ", ".join("`{}` = %s".format(k) for k in encoded)
        sql = "UPDATE `{}` SET {} WHERE id = %s".format(entity_name, set_clause)
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, list(encoded.values()) + [item_id])
            conn.commit()
        finally:
            conn.close()

    return find_by_id(entity_name, item_id)


def delete_one(entity_name, item_id):
    """删除指定ID的记录，返回被删除的记录，未找到返回 None"""
    _ensure_table(entity_name)
    existing = find_by_id(entity_name, item_id)
    if existing is None:
        return None
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `{}` WHERE id = %s".format(entity_name), [item_id])
        conn.commit()
    finally:
        conn.close()
    return existing


def find_by_id(entity_name, item_id):
    """按ID查找记录"""
    _ensure_table(entity_name)
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM `{}` WHERE id = %s".format(entity_name), [item_id])
            row = cur.fetchone()
        return _decode_row(entity_name, row)
    finally:
        conn.close()


def find_by(entity_name, predicate_func):
    """按自定义条件查找记录（在 Python 内过滤，与 JSON 后端行为一致）"""
    data_list = load_all(entity_name)
    return [item for item in data_list if predicate_func(item)]
