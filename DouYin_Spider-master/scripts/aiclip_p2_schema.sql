-- AI 剪辑模块 · P2 素材理解增量 DDL（增量，不动已有结构）
-- 执行方式：容器启动后由 services/aiclip/store.ensure_schema() 幂等自愈补齐；
--           本文件仅作留档，手工执行等价。
--
-- 复用 P1 已建的四列（原设计者本就为 AI 打标预留）：
--   ai_classify      varchar(64)  ← 理解出的素材形态（产品展示/真人出镜口播/...）
--   classify_status  varchar(32)  ← 理解状态机 pending|running|done|failed|skipped
--   tags             json         ← 语义层
--   speech           json         ← 语音层（ASR 逐句 + 时间戳）
--   seg_desc         json         ← 可编排单元 units
--
-- 本次新增四列：只补"过程与成本"，不重复存语义。

ALTER TABLE `materials`
  ADD COLUMN `understand_at`     VARCHAR(32) NULL COMMENT '理解完成时间',
  ADD COLUMN `understand_error`  VARCHAR(512) NULL COMMENT '理解失败原因',
  ADD COLUMN `understand_ver`    VARCHAR(16) NULL COMMENT '理解流水线版本，prompt 改动后据此批量重跑',
  ADD COLUMN `understand_cost`   JSON NULL COMMENT '理解开销 {model,input_tokens,output_tokens,seconds,calls}';

-- 便于"把当前项目还没理解的素材捞出来"
-- （已有 idx_type_status 覆盖 type+status，这里针对理解状态单列）
ALTER TABLE `materials`
  ADD KEY `idx_understand_status` (`classify_status`, `understand_ver`);

-- ---------------------------------------------------------------------------
-- 字段语义对照（写代码时以本表为准）
-- ---------------------------------------------------------------------------
--  ai_classify      = {"kind"}                产品展示 / 真人出镜口播 / 真人演示 /
--                                            场景空镜 / 信息图 / 文字板 / 包装特写 / 其他
--  classify_status  = pending | running | done | failed | skipped
--                     skipped = 该素材形态无需理解（目前不用，保留）
--  tags             = {"list":[...], "summary":"...", "modality":{...},
--                      "text_on_screen":"...", "notes":"..."}
--                     text_on_screen ← 硬字幕雷区（素材自带字幕会与成片字幕打架）
--                     notes          ← 竞品露出 / 过曝 等使用注意事项
--  speech           = {"has_speech":bool, "language":"zh", "has_music":bool,
--                      "has_env_sound":bool, "speech_desc":"...",
--                      "segments":[{"start","end","text"}], "full_text":"...",
--                      "raw_span": <模型给的总跨度，用于漂移校正留档>}
--  seg_desc         = [ unit, ... ]            ★ 可编排单元
--                     unit = {"start","end","visual","speech","usable_for":[...]}
--                     图片素材恒为 1 个 unit（start=end=0）
--
--  units 是 ② 参考脚本的直接输入：剧本的一个镜 → 找 usable_for 命中的 unit。
