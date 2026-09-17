-- ============================================================================
-- AI 剪辑模块 · P1 增量 DDL
--
-- 背景：库中已存在 11 张 AI 剪辑表（projects / frame_scripts / frame_shots /
--       materials / material_list_items / subtitles / audio_tracks / effects /
--       render_tasks / prompt_templates / async_tasks），本文件**只加列**，
--       不改动、不删除任何既有列。
--
-- 对应五份文件契约（见 AI剪辑模块重构_P1实现方案_v2.md §12）：
--   script.json        → frame_scripts + frame_shots
--   可供编排.json      → materials（素材能力层）★ 本文件主要补这里
--   reference.json     → frame_scripts（一版 draft）+ frame_shots.material_gap
--   shotlist.json      → frame_shots 工程字段 + subtitles + audio_tracks + effects
--   workbench.ts/json  → 不落库
--
-- ⚠️ MySQL 8.0 不支持 ADD COLUMN IF NOT EXISTS，本文件按「只跑一次」编写。
--    运行时请走 services/aiclip/store.py::ensure_schema()（幂等，自愈）。
-- ============================================================================

-- ---------------------------------------------------------------------------
-- materials：素材能力层（可供编排.json 的落库形态）
-- ---------------------------------------------------------------------------
ALTER TABLE `materials`
  ADD COLUMN `sha1`      VARCHAR(40)  NULL COMMENT '文件内容 sha1：稳定 asset_id + 天然去重（改名不失效）',
  ADD COLUMN `geom`      JSON         NULL COMMENT '几何体检 {w,h,has_alpha,bbox:[x,y,w,h],content_ratio}（content_ratio=真实内容像素占画幅比）',
  ADD COLUMN `media`     JSON         NULL COMMENT '媒体体检 {fps,duration,bitrate,codec,rotation,has_audio,audio_codec}',
  ADD COLUMN `tags`      JSON         NULL COMMENT 'AI 语义标签 {function,desc,scene,keywords,when_not}',
  ADD COLUMN `speech`    JSON         NULL COMMENT '语音 {has_speech,asr_text,lang,segments:[{start,end,text}]}',
  ADD COLUMN `seg_desc`  JSON         NULL COMMENT '片段级描述 [{start,end,desc}]（切点驱动，非逐秒）',
  ADD COLUMN `thumb_url` VARCHAR(512) NULL COMMENT '缩略图访问 URL',
  ADD UNIQUE KEY `uk_materials_sha1` (`sha1`);

-- ---------------------------------------------------------------------------
-- projects：区分片型与画布
--   kind: oral        = 口播型（主轨为口播成片，有贴片层与柔化窗）
--         storyboard  = 分镜型（A-roll 素材段即主轨，无贴片）
-- ---------------------------------------------------------------------------
ALTER TABLE `projects`
  ADD COLUMN `kind`   VARCHAR(16) NULL DEFAULT 'storyboard' COMMENT 'oral 口播型 | storyboard 分镜型',
  ADD COLUMN `canvas` JSON        NULL COMMENT '画布 {w,h,fps}，默认 1080x1920/30';
