# -*- coding: utf-8 -*-
"""AI 剪辑模块 · 独立 DAL。

为什么不复用 services.storage 门面：
    门面的 find_by 是「load_all() 全表拉进 Python 再过滤」，没有 JOIN / 分页 /
    排序 / 事务，而这套 schema 是关系型的（projects → frame_scripts →
    frame_shots，projects ↔ materials 多对多）。所以新模块写独立 DAL。

对齐已有 11 张表：本模块**只加列、只补一张引用表**，不另起一套。
    项目            → projects
    素材（全库资产）→ materials
    项目 ↔ 素材引用 → project_materials  ★ 11 张表里缺这张，本次补上
    剧本            → frame_scripts / frame_shots（P2 用）

连接参数与 services/storage_mysql.py 完全一致：
    MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DB
"""
import json
import os
import threading

import pymysql
from loguru import logger

# ---------------------------------------------------------------------------
# 连接
# ---------------------------------------------------------------------------
_MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
_MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
_MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
_MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
_MYSQL_DB = os.environ.get('MYSQL_DB', 'douyin_spider')

_schema_lock = threading.Lock()
_schema_ready = False


def get_conn():
    return pymysql.connect(
        host=_MYSQL_HOST, port=_MYSQL_PORT, user=_MYSQL_USER,
        password=_MYSQL_PASSWORD, database=_MYSQL_DB,
        charset='utf8mb4', autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


# ---------------------------------------------------------------------------
# JSON 列（pymysql 不能直接绑 dict/list，必须自己 dumps/loads）
# ---------------------------------------------------------------------------
JSON_COLS = {
    'materials': ('geom', 'media', 'tags', 'speech', 'seg_desc', 'understand_cost'),
    'projects': ('canvas',),
    'frame_scripts': ('generate_params', 'script_json', 'reference_json', 'gen_cost'),
}


def _encode(table, data):
    """dict/list → json 字符串；None 原样保留。

    这里**故意不查白名单**：pymysql 本来就不接受 dict/list 作参数，
    所以任何 dict/list 值都必须 dumps；查白名单反倒会漏
    （P2 就漏过 `understand_cost`，报 "dict can not be used as parameter"）。
    """
    out = {}
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = v
    return out


def _discover_json_cols():
    """从 information_schema 读真实 JSON 列，合并进白名单。

    `_decode` 需要知道哪些列要 loads；白名单是手写的容易漏，
    所以以库为准兜底补全（只在 ensure_schema 里跑一次）。
    """
    try:
        rows = query(
            "SELECT TABLE_NAME AS t, COLUMN_NAME AS c FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND DATA_TYPE='json'", [_MYSQL_DB])
    except Exception as e:
        logger.warning('aiclip: 发现 JSON 列失败: {}'.format(e))
        return
    for r in rows or []:
        t, c = r.get('t'), r.get('c')
        if not t or not c:
            continue
        JSON_COLS[t] = tuple(sorted(set(JSON_COLS.get(t, ())) | {c}))


def _decode(table, row):
    """json 字符串 → dict/list。"""
    if not row:
        return row
    cols = JSON_COLS.get(table, ())
    for c in cols:
        v = row.get(c)
        if isinstance(v, (str, bytes, bytearray)) and v:
            try:
                row[c] = json.loads(v)
            except (ValueError, TypeError):
                pass
    return row


# ---------------------------------------------------------------------------
# 通用 CRUD
# ---------------------------------------------------------------------------
def query(sql, args=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or [])
            return cur.fetchall() or []
    finally:
        conn.close()


def query_one(sql, args=None):
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            n = cur.execute(sql, args or [])
        conn.commit()
        return n
    finally:
        conn.close()


def execute_many(sql, seq):
    if not seq:
        return 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            n = cur.executemany(sql, seq)
        conn.commit()
        return n
    finally:
        conn.close()


def insert(table, data):
    d = _encode(table, data)
    cols = list(d.keys())
    sql = 'INSERT INTO `{}` ({}) VALUES ({})'.format(
        table, ', '.join('`{}`'.format(c) for c in cols),
        ', '.join(['%s'] * len(cols)))
    execute(sql, [d[c] for c in cols])
    return data


def update(table, row_id, data):
    d = _encode(table, data)
    if not d:
        return 0
    sql = 'UPDATE `{}` SET {} WHERE `id` = %s'.format(table, ', '.join(
        '`{}` = %s'.format(k) for k in d))
    return execute(sql, list(d.values()) + [row_id])


def fetch(table, sql_where='', args=None, order='', limit=None, offset=None):
    sql = 'SELECT * FROM `{}`'.format(table)
    if sql_where:
        sql += ' WHERE ' + sql_where
    if order:
        sql += ' ORDER BY ' + order
    if limit is not None:
        sql += ' LIMIT {}'.format(int(limit))
        if offset:
            sql += ' OFFSET {}'.format(int(offset))
    return [_decode(table, r) for r in query(sql, args)]


def fetch_by_id(table, row_id):
    r = query_one('SELECT * FROM `{}` WHERE `id` = %s'.format(table), [row_id])
    return _decode(table, r) if r else None


def count(table, sql_where='', args=None):
    sql = 'SELECT COUNT(*) AS n FROM `{}`'.format(table)
    if sql_where:
        sql += ' WHERE ' + sql_where
    r = query_one(sql, args)
    return int(r['n']) if r else 0


# ---------------------------------------------------------------------------
# 幂等 schema 自愈（对应 scripts/aiclip_p1_schema.sql）
#   已经跑过 DDL 的库不会有任何动作；换库 / 新环境则自动补上。
# ---------------------------------------------------------------------------
_EXTRA_COLUMNS = [
    ('materials', 'sha1', "VARCHAR(40) NULL COMMENT '文件内容 sha1：稳定 asset_id + 天然去重'"),
    ('materials', 'geom', "JSON NULL COMMENT '几何体检 {w,h,has_alpha,bbox,content_ratio}'"),
    ('materials', 'media', "JSON NULL COMMENT '媒体体检 {fps,duration,bitrate,codec,has_audio}'"),
    ('materials', 'tags', "JSON NULL COMMENT 'AI 语义标签 {list,summary,modality,text_on_screen,notes}'"),
    ('materials', 'speech', "JSON NULL COMMENT '语音 {has_speech,language,segments,full_text}'"),
    ('materials', 'seg_desc', "JSON NULL COMMENT '可编排单元 units [{start,end,visual,speech,usable_for}]'"),
    ('materials', 'thumb_url', "VARCHAR(512) NULL COMMENT '缩略图访问 URL'"),
    # ---- P2 素材理解（全模态 LLM）状态机 ----
    ('materials', 'understand_at', "VARCHAR(32) NULL COMMENT '理解完成时间'"),
    ('materials', 'understand_error', "VARCHAR(512) NULL COMMENT '理解失败原因'"),
    ('materials', 'understand_ver', "VARCHAR(16) NULL COMMENT '理解流水线版本，prompt 改动后据此重跑'"),
    ('materials', 'understand_cost', "JSON NULL COMMENT '理解开销 {model,input_tokens,output_tokens,seconds,calls}'"),
    ('projects', 'kind', "VARCHAR(16) NULL DEFAULT 'storyboard' COMMENT 'oral|storyboard'"),
    ('projects', 'canvas', "JSON NULL COMMENT '画布 {w,h,fps}'"),
    # ---- P3 剧本导入 + 参考脚本（LLM 第 1 次，叙事层）----
    # frame_scripts 一行 = 一个版本的脚本。source 区分它是什么：
    #   'import'    剧本导入（① 的产物，纯剧本，无素材引用）
    #   'reference' 参考脚本（② 的产物，剧本镜 × 素材理解 → 带素材引用）
    ('frame_scripts', 'requirement', "TEXT NULL COMMENT '用户需求：这条片子要什么效果'"),
    ('frame_scripts', 'script_json', "JSON NULL COMMENT '剧本结构化原文（镜数组，导入时的原样留档）'"),
    ('frame_scripts', 'reference_json', "JSON NULL COMMENT '参考脚本（② 产出）。**这是权威副本**，md 只是它的投影'"),
    ('frame_scripts', 'reference_md', "LONGTEXT NULL COMMENT '人看版 md（reference_json 的渲染投影）'"),
    ('frame_scripts', 'gen_status', "VARCHAR(32) NULL COMMENT 'draft|generating|done|failed'"),
    ('frame_scripts', 'gen_error', "VARCHAR(512) NULL COMMENT '生成失败原因'"),
    ('frame_scripts', 'gen_cost', "JSON NULL COMMENT 'LLM 开销 {model,input_tokens,output_tokens,seconds,calls}'"),
    # frame_shots 同样一行一义：script_id 指向哪个 frame_scripts 版本，就属于哪一层。
    # 剧本镜只有 content/subtitle_text/duration 这些；参考镜才带 material_id/in_offset。
    ('frame_shots', 'angle', "VARCHAR(32) NULL COMMENT '机位角度：平视|俯拍|仰拍|第一人称（剧本的「景别/构图」拆三段之一）'"),
    ('frame_shots', 'characters_scene', "TEXT NULL COMMENT '人物&场景'"),
    ('frame_shots', 'ref_image', "VARCHAR(512) NULL COMMENT '参考拍摄图片'"),
    ('frame_shots', 'audio_note', "TEXT NULL COMMENT '音效/音频节奏'"),
    ('frame_shots', 'source_seq', "INT NULL COMMENT '★参考镜指回剧本镜序号（LLM#2 拆并镜后仍能对号，人审改不丢）'"),
    ('frame_shots', 'band', "VARCHAR(8) NULL COMMENT '落位档：A上带|B下带|C全屏|END覆盖层'"),
    ('frame_shots', 'material_id', "VARCHAR(36) NULL COMMENT '★素材引用（原表完全没有这个字段）'"),
    ('frame_shots', 'in_offset', "FLOAT NULL COMMENT '素材入点秒'"),
    ('frame_shots', 'out_offset', "FLOAT NULL COMMENT '素材出点秒'"),
    ('frame_shots', 'unit_index', "INT NULL COMMENT '用该素材的第几个可编排单元（seg_desc 下标）'"),
    ('frame_shots', 'match_reason', "TEXT NULL COMMENT '为什么选这条素材（不匹配时写缺口原因）'"),
    ('frame_shots', 'subtitle_style', "VARCHAR(64) NULL COMMENT '字幕样式：白字|黄字|公式|清单'"),

    # ---- 素材理解的人工校对（P4）----
    # 为什么要有这两个：模型理解会因同音词写错别字（"耳净"→"耳镜"、"洁耳液"→"洁尔液"），
    # 而理解结果是 ② 参考脚本的输入 —— 错字会一路带进成片字幕。
    # 所以必须能改，而且要知道「这条是模型原文还是人工校对过的」。
    ('materials', 'understand_edited_at', "DATETIME NULL COMMENT '人工校对的最后时间，NULL = 纯模型结果'"),
    ('materials', 'understand_edited_by', "VARCHAR(64) NULL COMMENT '校对者'"),

    # ---- P5c TTS 语音（audio_tracks 承载：一镜一段旁白）----
    # audio_tracks 本来就是「成片的声轨」表（kind/segment/url/duration/shot_id/
    # is_ai_generated/sort_order/status），TTS 旁白正好是其中一类（kind='tts'），
    # 所以不另起表 —— 与 P1「对齐已有 schema，别再造一套」的立场一致。
    # 需要补的是「这段从哪句台词、用哪个音色合成的」这几个溯源字段：
    ('audio_tracks', 'shot_seq', "INT NULL COMMENT '★对应参考脚本镜号 seq（TTS 清单的稳定键）'"),
    ('audio_tracks', 'text_content', "TEXT NULL COMMENT 'TTS 台词文本（= 该镜 subtitle_text，改了就要重生成）'"),
    # ⚠️ 64 而不是 32：火山豆包的 speaker id 长这样
    #    zh_female_shuangkuaisisi_uranus_bigtts（39 字符），32 会直接 DataError 1406。
    #    列宽是「当时用谁」定的，换 provider 就得出事 —— 所以 _WIDEN_COLUMNS 兜底。
    ('audio_tracks', 'voice_id', "VARCHAR(64) NULL COMMENT 'TTS 音色 id：火山 speaker（zh_female_xxx_bigtts）或 CosyVoice 名（中文女）'"),
    ('audio_tracks', 'speech_rate', "FLOAT NULL COMMENT 'TTS 语速倍率（1.0 = 原速；火山侧换算成 speech_rate ∈ [-50,100]）'"),
    ('audio_tracks', 'gen_error', "VARCHAR(512) NULL COMMENT 'TTS 合成失败原因'"),
    ('audio_tracks', 'gen_at', "VARCHAR(32) NULL COMMENT 'TTS 合成完成时间'"),
]

# 历史列宽不够时**自动加宽**（幂等，只加宽不缩窄）。
#   「补列」机制只管「这一列有没有」，不管「够不够宽」——
#   而列宽往往是「当时用哪家引擎」决定的：P5c 首版音色是 CosyVoice 的「中文女」（3 字），
#   VARCHAR(32) 绰绰有余；换成火山后 speaker 是 39 字符，写入直接
#   `pymysql.err.DataError: (1406, "Data too long for column 'voice_id'")`。
_WIDEN_COLUMNS = [
    ('audio_tracks', 'voice_id', 64,
     "VARCHAR(64) NULL COMMENT 'TTS 音色 id：火山 speaker（zh_female_xxx_bigtts）或 CosyVoice 名（中文女）'"),
]

_CREATE_PROJECT_MATERIALS = """
CREATE TABLE IF NOT EXISTS `project_materials` (
  `id`          VARCHAR(36) PRIMARY KEY,
  `project_id`  VARCHAR(36) NOT NULL,
  `material_id` VARCHAR(36) NOT NULL,
  `seq`         INT DEFAULT 0,
  `added_at`    VARCHAR(32),
  `owner_id`    VARCHAR(36),
  UNIQUE KEY `uk_project_material` (`project_id`, `material_id`),
  KEY `idx_pm_project` (`project_id`),
  KEY `idx_pm_material` (`material_id`),
  KEY `idx_pm_owner` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def ensure_schema():
    """幂等补列 + 补引用表。进程内只跑一次。"""
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        try:
            for table, col, ddl in _EXTRA_COLUMNS:
                row = query_one(
                    "SELECT COUNT(*) AS n FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                    [_MYSQL_DB, table, col])
                if row and int(row['n']) == 0:
                    execute('ALTER TABLE `{}` ADD COLUMN `{}` {}'.format(table, col, ddl))
                    logger.info('aiclip schema: 补列 {}.{}'.format(table, col))

            for table, col, width, ddl in _WIDEN_COLUMNS:
                r = query_one(
                    "SELECT CHARACTER_MAXIMUM_LENGTH AS n FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                    [_MYSQL_DB, table, col])
                cur_w = r.get('n') if r else None
                if cur_w is not None and int(cur_w) < width:
                    execute('ALTER TABLE `{}` MODIFY COLUMN `{}` {}'.format(table, col, ddl))
                    logger.info('aiclip schema: 加宽 {}.{} 字符长度 {} -> {}'.format(
                        table, col, cur_w, width))

            row = query_one(
                "SELECT COUNT(*) AS n FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='materials' "
                "AND INDEX_NAME='uk_materials_sha1'", [_MYSQL_DB])
            if row and int(row['n']) == 0:
                execute('ALTER TABLE `materials` ADD UNIQUE KEY `uk_materials_sha1` (`sha1`)')
                logger.info('aiclip schema: 补唯一键 materials.sha1')

            execute(_CREATE_PROJECT_MATERIALS)
            _discover_json_cols()
            _schema_ready = True
        except Exception as e:  # 不因 schema 自愈失败拖垮进程
            logger.error('aiclip schema ensure 失败: {}'.format(e))


def health():
    """给 /api/aiclip/health 用的连通性自检。"""
    info = {'mysql': False, 'schema_ready': False}
    try:
        r = query_one('SELECT 1 AS ok')
        info['mysql'] = bool(r)
        info['schema_ready'] = _schema_ready
    except Exception as e:
        info['error'] = str(e)
    return info
