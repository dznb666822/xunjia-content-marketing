-- ============================================================================
-- AI 剪辑模块 · P3 增量 DDL（剧本导入 + 参考脚本）
--   ① 剧本导入       xlsx「分镜脚本」sheet → frame_scripts(source='import') + frame_shots(N)
--   ② 参考脚本       LLM#1：剧本镜 × 素材理解 × 用户需求 → reference_json + reference_md
--
-- 设计口径：**只加列，不动已有结构**（与 P1/P2 一致）。
--   本文件的每一条，services/aiclip/store.py 的 _EXTRA_COLUMNS 里都有等价项，
--   ensure_schema() 会幂等补齐 —— 这里留档是为了让 DBA 能一眼看到改了什么。
--
-- frame_scripts 一行的语义由 source 决定：
--   'import'     剧本导入（① 的产物）—— script_json 是权威
--   'reference'  参考脚本（② 的产物）—— reference_json 是权威，reference_md 只是投影
-- frame_shots 归属由 script_id 决定：指向 import 版就是剧本镜，指向 reference 版就是参考镜。
-- ============================================================================

-- ---------- frame_scripts：剧本 / 参考脚本的版本容器 ----------
ALTER TABLE `frame_scripts`
  ADD COLUMN `requirement`    TEXT         NULL COMMENT '用户需求：这条片子要什么效果',
  ADD COLUMN `script_json`    JSON         NULL COMMENT '剧本结构化原文（镜数组，导入时原样留档）',
  ADD COLUMN `reference_json` JSON         NULL COMMENT '参考脚本（② 产出）。★权威副本，md 只是投影',
  ADD COLUMN `reference_md`   LONGTEXT     NULL COMMENT '人看版 md（reference_json 的渲染投影）',
  ADD COLUMN `gen_status`     VARCHAR(32)  NULL COMMENT 'draft|generating|done|failed',
  ADD COLUMN `gen_error`      VARCHAR(512) NULL COMMENT '生成失败原因',
  ADD COLUMN `gen_cost`       JSON         NULL COMMENT 'LLM 开销 {model,input_tokens,output_tokens,seconds,calls}';

-- ---------- frame_shots：镜级字段 ----------
-- 「景别/构图」在剧本里是一格（"中景/平视/三分法构图"），原表要拆三段：
--   shot_size(中景) + angle(平视) + composition(三分法构图)
ALTER TABLE `frame_shots`
  ADD COLUMN `angle`            VARCHAR(32)  NULL COMMENT '机位角度：平视|俯拍|仰拍|第一人称',
  ADD COLUMN `characters_scene` TEXT         NULL COMMENT '人物&场景',
  ADD COLUMN `ref_image`        VARCHAR(512) NULL COMMENT '参考拍摄图片',
  ADD COLUMN `audio_note`       TEXT         NULL COMMENT '音效/音频节奏',
  -- 下面 8 列是 ② 才填的：★ 原表完全没有素材引用字段，② 的能力全靠这几列
  ADD COLUMN `source_seq`       INT          NULL COMMENT '参考镜指回剧本镜序号（拆并镜后仍能对号）',
  ADD COLUMN `band`             VARCHAR(8)   NULL COMMENT '落位档：A上带|B下带|C全屏|END覆盖层',
  ADD COLUMN `material_id`      VARCHAR(36)  NULL COMMENT '素材引用',
  ADD COLUMN `in_offset`        FLOAT        NULL COMMENT '素材入点秒',
  ADD COLUMN `out_offset`       FLOAT        NULL COMMENT '素材出点秒',
  ADD COLUMN `unit_index`       INT          NULL COMMENT '用该素材的第几个可编排单元（seg_desc 下标）',
  ADD COLUMN `match_reason`     TEXT         NULL COMMENT '为什么选这条素材（不匹配时写缺口原因）',
  ADD COLUMN `subtitle_style`   VARCHAR(64)  NULL COMMENT '字幕样式：白字|黄字|公式|清单';

-- ---------- 素材缺口闭环（11 张表里已存在，此处仅说明用法） ----------
-- frame_shots.material_gap = 1 时，缺口写进 material_list_items：
--   INSERT INTO material_list_items (id, project_id, shot_id, need_desc, resolve_result, ...)
-- 参考脚本阶段素材不够时就走这条，而不是硬塞一条不合适的素材。
