# DouYin_Spider 项目文档

## 1. 项目概述

DouYin_Spider 是一个抖音数据采集、AI分析与内容运营一体化的解决方案。除了基础的爬虫功能外，集成了火山方舟豆包大模型，实现了从数据采集到内容策略输出的全链路闭环。

**技术栈**：Python 3.11 + Flask + APScheduler + 火山方舟 Ark API (豆包 Seed 2.0)

## 2. 架构总览

```
┌─────────────────────────────────────────────────────┐
│                  templates/index.html                │
│                    (Web 控制台)                       │
├─────────────────────────────────────────────────────┤
│              static/js/app.js + tools.js             │
│                  (前端业务逻辑)                       │
├─────────────────────────────────────────────────────┤
│                   web_server.py                      │
│              (Flask 路由 + API 网关)                  │
├──────────┬──────────┬──────────┬───────────────────┤
│ dy_apis/ │ builder/ │ utils/   │    services/       │
│ 抖音API  │ 签名算法 │ 工具函数  │   AI业务服务        │
│ 封装层   │         │          │                    │
├──────────┴──────────┴──────────┼───────────────────┤
│        dy_live/                │   scheduler/       │
│      直播间WebSocket            │   定时调度          │
├────────────────────────────────┼───────────────────┤
│         models/                │    datas/          │
│       数据模型                 │   持久化数据        │
└────────────────────────────────┴───────────────────┘
```

## 3. 目录结构

```
DouYin_Spider-master/
├── web_server.py                # Web 控制台入口（Flask，40个API路由）
├── main.py                      # 命令行爬虫入口
├── .env                         # 配置文件（Cookie、API Key等密钥）
├── requirements.txt             # Python 依赖
│
├── builder/                     # 请求签名与构建
│   ├── auth.py                  #   Cookie 解析
│   ├── header.py                #   HTTP 请求头
│   ├── params.py                #   参数编码与验签
│   ├── xbogus_pure.py           #   X-Bogus 签名（纯Python）
│   └── ab_pure.py               #   A-B 算法
│
├── dy_apis/                     # 抖音 API 封装
│   ├── douyin_api.py            #   全部 API（搜索/用户/作品/直播/私信/互动）
│   └── douyin_recv_msg.py       #   私信 WebSocket 实时接收
│
├── dy_live/                     # 直播间监控
│   └── server.py                #   WebSocket 弹幕/礼物/进场监听
│
├── services/                    # ★ AI 业务服务层（核心）
│   ├── video_analyzer.py        #   视频内容分析（多模态）
│   ├── script_generator.py      #   AI 脚本生成
│   ├── competitor_discovery.py  #   竞品发现引擎
│   ├── data_collector.py        #   数据采集与看板
│   ├── ai_keyword.py            #   AI 关键词 + 跨赛道推荐
│   ├── ad_advisor.py            #   投流分析建议
│   └── storage.py               #   JSON 文件持久化
│
├── scheduler/                   # 定时任务
│   └── daily_monitor.py         #   每日博主扫描 + 新视频监听
│
├── models/                      # 数据模型 (dataclass)
│   ├── brand.py                 #   品牌画像
│   ├── competitor.py            #   竞品博主
│   ├── video.py                 #   视频数据
│   └── task.py                  #   任务记录
│
├── utils/                       # 工具函数
│   ├── common_util.py           #   环境加载、认证初始化
│   ├── data_util.py             #   数据解析、下载、Excel导出
│   └── spider_util.py           #   爬取流程编排
│
├── static/                      # 静态资源
│   ├── js/
│   │   ├── app.js               #   主业务逻辑（品牌/竞品/分析/脚本/看板）
│   │   └── tools.js             #   手动工具逻辑（搜索/用户/直播/私信）
│   └── css/style.css
│
├── templates/
│   └── index.html               #   单页应用（7个功能面板）
│
├── datas/                       # 数据存储（自动生成）
│   ├── app_data/                #   JSON 持久化（brands/competitors/videos/tasks）
│   ├── media_datas/             #   下载的图片/视频
│   └── excel_datas/             #   导出的 Excel
│
└── newsign/                     # 备用 Node.js 签名方案（可选）
```

## 4. 功能模块详解

### 4.1 数据采集层

| 功能 | API 端点 | 说明 |
|------|----------|------|
| 综合搜索 | `POST /api/search_works` | 搜索视频/图文，支持排序、时长筛选 |
| 用户搜索 | `POST /api/search_users` | 搜索抖音用户 |
| 直播搜索 | `POST /api/search_lives` | 搜索直播间 |
| 用户信息 | `POST /api/get_user_info` | 获取用户详情 |
| 用户作品 | `POST /api/get_user_all_works` | 获取全部作品 |
| 粉丝/关注 | `POST /api/get_follower_list` 等 | 粉丝和关注列表 |
| 作品详情 | `POST /api/get_work_info` | 作品信息 + 评论 |
| 推荐流 | `POST /api/get_feed` | 首页推荐 |
| 下载作品 | `POST /api/download_work` | 下载视频/图片 |
| 交互操作 | `POST /api/digg` 等 | 点赞/收藏/评论 |

### 4.2 AI 业务服务层（services/）

这是项目的核心增值模块，所有服务均调用火山方舟豆包大模型。

#### 视频分析 (video_analyzer.py)
- **输入**：视频文件 + 标题 + 文案
- **输出**：`text_structure`（钩子/正文/CTA）、`video_type`（视频类型）、`scenes`（场景描述）、`emotion`（情绪分析）
- **调用方式**：上传视频到 Ark Files API → 多模态分析

#### 脚本生成 (script_generator.py)
- **输入**：已分析视频的文本结构 + 品牌画像
- **输出**：N个版本的参考脚本（含 Hook/Body/CTA/完整脚本）
- **提示词位置**：L154（基于视频）、L228（按类型）

#### 竞品发现 (competitor_discovery.py)
- **同赛道发现（三步评估，前两条硬门槛，只标注不淘汰）**：AI 提取品牌关键词 → 抖音搜索 → 评估每个候选并**全部展示**，每条筛选结果附理由供人工复核
  - 评估一 粉丝量级（分段策略，传 `my_follower_count`，留空不启用）：
    - 通用最低门槛：粉丝 < 100（`MIN_FOLLOWERS`）直接不通过
    - 冷启动（当前粉丝 < 1000，含 0）：粉丝区间 [10000, 100000]，避开头部大号、过滤僵尸号
    - 有基本盘（当前粉丝 ≥ 1000）：粉丝为当前的 1-5 倍
    - 阈值常量：`MIN_FOLLOWERS`、`COLD_START_THRESHOLD/FLOOR/CEILING`、`FOLLOWER_RATIO_MIN/MAX`
  - 评估二 数据稳定向好：近3个月持续更新（≥3条），最近10条视频点赞数趋势 up/stable 判定通过，down/volatile/inactive 标注未通过及理由（web 列表接口无播放量，用点赞数做趋势）
  - 评估三 内容形式可复制：**仅粉丝量级（评估一）与数据稳定（评估二）都通过的候选进入 AI 评估**，未达标者标注"未进入AI评估"；分批调用（每批 `REPLICABILITY_BATCH_SIZE=10`）控制单次请求大小避免超时，评分与理由写入 `replicability_check`，提示词见 6.8
  - 保存：所有候选以 `status="pending"`（待复核）保存，不自动进入监听；通过数多的排前，前端标注 ✅/⚠️/❔ + 理由，人工判断后点"添加到监听"转正
- **跨赛道推荐**：AI 推荐可借鉴的跨品类 → 搜索对应博主
- **接口字段**：搜索用户 `user_info.follower_count`（0 时回退 `mplatform_followers_count`）、作品 `aweme_list[].statistics.digg_count`（注意：web 版列表接口 `play_count` 恒为 0，趋势与均量均用 `digg_count` 点赞数计算）、`create_time`（unix秒）

#### AI 关键词 (ai_keyword.py)
- **关键词策略**：生成核心词/长尾词/场景词/竞品词
- **跨赛道推荐**：推荐可借鉴品类及策略
- **提示词位置**：L161（关键词）、L212（跨赛道）

#### 投流分析 (ad_advisor.py)
- **输入**：视频互动数据（播放/点赞/评论/分享/下载）
- **输出**：投流建议、预算分配、受众定向、ROI预测
- **提示词位置**：L71

#### 数据看板 (data_collector.py)
- 按品牌/博主/类型/时间筛选视频数据
- 采集最新互动数据

### 4.3 定时调度 (scheduler/daily_monitor.py)
- **每日10:00**：扫描新博主（基于竞品发现）
- **每日11:00**：监听已关注博主的新视频
- 基于 APScheduler，支持手动触发和状态查询

### 4.4 直播间监听 (dy_live/server.py)
- WebSocket 连接直播弹幕服务器
- 实时接收：弹幕、礼物、进场、关注、点赞、热度
- Protobuf 协议解析

## 5. Web 控制台面板

| 面板 | 功能 |
|------|------|
| **品牌管理** | 创建/编辑品牌画像（品类/人群/卖点/调性） |
| **竞品发现** | 同赛道+跨赛道博主发现，一键加入监听 |
| **监听中心** | 查看监听状态，手动触发扫博主/拉视频 |
| **视频分析** | 选择视频 → AI分析内容结构 → 展示结果 |
| **脚本生成** | 选品牌+已分析视频 → AI生成参考脚本 |
| **数据看板** | 筛选视频数据，查看播放/点赞/互动率，投流分析 |
| **手动工具** | 搜索采集/用户抓取/直播间/私信等传统爬虫功能 |

## 6. 所有 AI 提示词（完整原文）

> 说明：提示词中 `{brand_info}`、`{ref_structure}` 等为 Python `.format()` 模板变量，运行时会被替换为实际数据。

---

### 6.1 视频内容结构分析

- **文件**：[services/video_analyzer.py](file:///c:/Users/33664/Desktop/监听/DouYin_Spider-master/services/video_analyzer.py) L41
- **模型**：豆包 Seed 2.0 多模态（传入视频文件）
- **输入变量**：`{title}` 视频标题、`{desc}` 视频文案
- **输出**：JSON（text_structure / video_type / scene_desc / mood）

```
请分析以下视频的内容结构和创作特征，以JSON格式输出。

视频标题：{title}
视频文案：{desc}

请分析并输出以下结构的JSON（只输出JSON，不要包含markdown代码块标记）：
{
    "text_structure": {
        "hook": "前3秒的抓睛点/开头的吸引点是什么",
        "body": "正文的叙事逻辑和内容展开方式",
        "cta": "结尾的转化引导（点赞/关注/评论/购买引导等）"
    },
    "video_type": "视频类型：教程类/展示类/剧情类/测评类/开箱类/Vlog类/口播类/混剪类",
    "scene_desc": "画面场景描述，包括拍摄环境、人物动作、画面切换节奏",
    "mood": "情绪基调：轻松/严肃/温馨/搞笑/励志/焦虑/好奇"
}
```

---

### 6.2 封面图片描述

- **文件**：[services/video_analyzer.py](file:///c:/Users/33664/Desktop/监听/DouYin_Spider-master/services/video_analyzer.py) L186
- **模型**：豆包 Seed 2.0 多模态（传入封面图片URL）
- **输入变量**：`{title}` 视频标题
- **输出**：纯文本描述（1-2句话）

```
请简要描述这张视频封面的内容（1-2句话即可），包括：
1. 画面主体（人物/产品/场景）
2. 色调和视觉风格
3. 封面上是否有文字，文字内容是什么

视频标题：{title}

请直接输出描述，无需JSON格式。
```

---

### 6.3 基于视频生成参考脚本

- **文件**：[services/script_generator.py](file:///c:/Users/33664/Desktop/监听/DouYin_Spider-master/services/script_generator.py) L154
- **模型**：豆包 Seed 2.0 文本
- **输入变量**：`{num_variants}` 版本数、`{brand_info}` 品牌信息、`{ref_structure}` 对标视频结构
- **输出**：JSON（scripts 数组）

```
你是一个专业的内容运营和脚本策划专家。请根据以下信息，为品牌生成 {num_variants} 个不同版本的短视频参考脚本。

{brand_info}

参考对标视频的结构：
{ref_structure}

要求：
1. 保留对标视频的文本结构框架和节奏
2. 内容替换为该品牌的产品/服务信息
3. 保持品牌的风格调性
4. 确保钩子有抓睛力，CTA有转化力
5. 每个版本有不同的切入角度

请以JSON格式输出（只输出JSON，不要markdown代码块）：
{
    "scripts": [
        {
            "version": 1,
            "angle": "版本切入角度描述",
            "hook": "钩子脚本文案",
            "body": "正文脚本文案",
            "cta": "转化引导文案",
            "full_script": "完整脚本（合并hook+body+cta）",
            "estimated_duration": "预估时长（秒）"
        }
    ]
}
```

---

### 6.4 按类型生成脚本模板

- **文件**：[services/script_generator.py](file:///c:/Users/33664/Desktop/监听/DouYin_Spider-master/services/script_generator.py) L228
- **模型**：豆包 Seed 2.0 文本
- **输入变量**：`{num_variants}` 版本数、`{video_type}` 视频类型、`{brand_info}` 品牌信息
- **输出**：JSON（scripts 数组）

```
你是一个专业的内容运营专家。请为以下品牌生成 {num_variants} 个"{video_type}"类型的短视频脚本模板。

{brand_info}

视频类型：{video_type}

请根据该类型的典型结构和该品牌的调性，生成可复用的脚本模板。

请以JSON格式输出（只输出JSON）：
{
    "scripts": [
        {
            "version": 1,
            "angle": "切入角度",
            "hook": "钩子模板",
            "body": "正文模板",
            "cta": "CTA模板",
            "full_script": "完整脚本模板",
            "estimated_duration": "预估时长"
        }
    ]
}
```

---

### 6.5 搜索关键词策略

- **文件**：[services/ai_keyword.py](file:///c:/Users/33664/Desktop/监听/DouYin_Spider-master/services/ai_keyword.py) L161
- **模型**：豆包 Seed 2.0 文本
- **输入变量**：`{brand_text}` 品牌画像文本
- **输出**：JSON（category/scene/audience/content 四类关键词）

```
你是一个专业的抖音搜索关键词策略专家。请根据以下品牌/账号画像，为该品牌在抖音平台上生成搜索关键词策略。

{brand_text}

请输出严格的JSON格式（不要包含其他任何文字），结构如下：
{
    "category_keywords": ["品类搜索词1", "品类搜索词2", ...],
    "scene_keywords": ["场景搜索词1", "场景搜索词2", ...],
    "audience_keywords": ["人群搜索词1", "人群搜索词2", ...],
    "content_keywords": ["内容形式搜索词1", "内容形式搜索词2", ...]
}

要求：
1. category_keywords: 用户会搜索的品类/产品词，如"宠物衣服"、"狗狗穿搭"、"猫咪衣服"。5-10个。
2. scene_keywords: 使用场景相关，如"遛狗穿搭"、"宠物生日派对"、"春节宠物装"。3-6个。
3. audience_keywords: 目标人群会搜的词，如"铲屎官必备"、"养狗新手推荐"。3-6个。
4. content_keywords: 内容形式词，如"教程"、"测评"、"穿搭"、"vlog"、"开箱"。3-6个。
5. 每个关键词应简洁、符合抖音用户搜索习惯、有实际搜索量潜力。
6. 只输出JSON，不要任何额外解释。
```

---

### 6.6 跨赛道品类推荐

- **文件**：[services/ai_keyword.py](file:///c:/Users/33664/Desktop/监听/DouYin_Spider-master/services/ai_keyword.py) L212
- **模型**：豆包 Seed 2.0 文本
- **输入变量**：`{brand_text}` 品牌画像文本
- **输出**：JSON（categories 数组，每项含 name/reason/search_keywords）

```
你是一个专业的抖音内容策略专家。请根据以下品牌/账号画像，分析并推荐该品牌可以借鉴的"跨赛道"品类。

{brand_text}

请输出严格的JSON格式（不要包含其他任何文字），结构如下：
{
    "categories": [
        {
            "name": "可借鉴的品类名称",
            "reason": "为什么值得借鉴（具体说明该品类的内容形式、选题策略、运营模式等方面值得学习的地方）",
            "search_keywords": ["在该品类下可以搜索的关键词1", "关键词2", ...]
        }
    ]
}

要求：
1. 推荐3-5个跨赛道品类。
2. 每个品类应来自不同的领域（如母婴、美食、美妆、家居、教育等），与本品牌的赛道有明显差异但有可借鉴之处。
3. reason要具体，不能泛泛而谈，说明具体可借鉴的切入点。
4. search_keywords 3-5个，是在抖音上搜索该品类相关内容会用到的词。
5. 只输出JSON，不要任何额外解释。
```

---

### 6.7 投流分析建议

- **文件**：[services/ad_advisor.py](file:///c:/Users/33664/Desktop/监听/DouYin_Spider-master/services/ad_advisor.py) L71
- **模型**：豆包 Seed 2.0 文本
- **输入变量**：`{stats}` 互动数据、`{video_type}` 类型、`{mood}` 情绪、`{text_structure}` 文本结构、`{brand_info}` 品牌信息、`{budget_range}` 预算
- **输出**：JSON（should_advertise / confidence / recommended_budget / target_audience / expected_roi / optimization_tips / risk_warning）

```
你是一个专业的抖音投流分析师。请根据以下视频数据，分析是否值得投流以及给出具体建议。

视频数据：
- 点赞数：{digg_count}
- 评论数：{comment_count}
- 分享数：{share_count}
- 播放数：{play_count}
- 收藏数：{collect_count}
- 视频类型：{video_type}
- 情绪基调：{mood}
- 钩子内容：{hook}
- 正文内容：{body}
- CTA内容：{cta}

{brand_info}

可接受预算范围：{budget_range}元

请分析以下维度并给出建议（输出JSON格式，只输出JSON不要markdown代码块）：
{
    "should_advertise": true/false,
    "confidence": "高/中/低",
    "reason": "推荐或不推荐投流的核心理由",
    "recommended_budget": "建议投流预算（如500-1000元/天）",
    "target_audience": {
        "age_range": "建议年龄范围",
        "gender": "建议性别",
        "interests": ["建议兴趣标签"],
        "regions": ["建议地域"]
    },
    "expected_roi": "预期ROI范围",
    "optimization_tips": ["优化建议列表"],
    "risk_warning": "风险提示"
}
```

---

### 6.8 内容可复制性评估（同赛道竞品发现筛选三）

- **文件**：[services/competitor_discovery.py](file:///c:/Users/33664/Desktop/监听/DouYin_Spider-master/services/competitor_discovery.py) `_evaluate_replicability`
- **模型**：豆包 Seed 2.0 文本
- **输入变量**：`{brand_text}` 品牌画像文本、`{candidates_json}` 候选博主摘要（昵称/粉丝数/均播/趋势/最近6条作品标题与数据）
- **输出**：JSON（results 数组，每项含 user_id / score 1-5 / replicable_points / non_replicable_points / reason）

```
你是一个专业的抖音内容拆解专家。请根据以下候选对标博主的近期作品数据，评估每个博主的"内容形式可复制性"。

品牌画像（评估时需结合该品牌可达到的水平）：
{brand_text}

评估原则：
1. 可复制的核心优势（参考价值高）：选题思路、脚本结构、拍摄手法、剪辑节奏、内容形式
2. 难以复制的核心优势（参考价值低）：明星脸/高颜值出镜、昂贵专业设备、独家资源/渠道、依赖超级粉丝基本盘的爆款

候选博主数据：
{candidates_json}

请为每个博主输出 1-5 分的可复制性评分（5=非常容易复制，1=几乎无法复制），只输出JSON：
{
    "results": [
        {
            "user_id": "候选的user_id",
            "score": 3,
            "replicable_points": ["可复制的优势点"],
            "non_replicable_points": ["难以复制的优势点"],
            "reason": "综合判断理由"
        }
    ]
}
```

> **提示词调用链**：`_evaluate_replicability` 复用 `ai_keyword._call_ai` + `ai_keyword._parse_json_response` + `ai_keyword._build_brand_text`，无需重复实现。

## 7. 数据模型

### Brand（品牌画像）
`name / category / target_audience / product_desc / style_tone / selling_points`

### Competitor（竞品博主）
`user_id / sec_uid / nickname / follower_count / category / status`

### Video（视频数据）
`aweme_id / title / desc / stats / analysis_status / text_structure / video_type / scripts`

### Task（任务记录）
`task_type / status / result_summary / created_at / completed_at`

## 8. 环境配置

### .env 关键配置
```env
DY_COOKIES='...'           # 抖音 Cookie（必填，用于 API 认证）
DY_LIVE_COOKIES='...'      # 直播 Cookie（可选）
ARK_API_KEY='...'          # 火山方舟 API Key（必填，AI 功能依赖）
AI_API_URL='...'           # Ark API 地址
AI_MODEL='...'             # 模型 ID（doubao-seed-2-0-pro-260215）
```

### 安装与启动
```powershell
pip install -r requirements.txt
pip install "volcengine-python-sdk[ark]"   # Ark Runtime SDK
python web_server.py                       # 启动 → http://127.0.0.1:5000
```

## 9. 已验证的模块状态

| 模块 | 状态 | 说明 |
|------|:---:|------|
| builder/ | 真实 | 签名算法，被所有 API 调用依赖 |
| dy_apis/douyin_api.py | 真实 | 核心 API 封装，所有数据采集依赖 |
| dy_live/server.py | 真实 | WebSocket 直播间监听 |
| services/video_analyzer.py | 真实 | 多模态视频分析，已修复 Ark SDK 导入 |
| services/script_generator.py | 真实 | AI 脚本生成，已修复响应解析 |
| services/competitor_discovery.py | 真实 | 竞品发现，整合 AI + 搜索 |
| services/data_collector.py | 真实 | 数据采集与看板 |
| services/ai_keyword.py | 真实 | AI 关键词策略 |
| services/ad_advisor.py | 真实 | 投流分析 |
| services/storage.py | 真实 | JSON 文件持久化 |
| scheduler/daily_monitor.py | 真实 | APScheduler 定时任务 |
| models/* | 真实 | dataclass 数据模型 |

**无假模块。** 所有 services/ 和 scheduler/ 下的功能均有完整的业务代码实现。

## 10. 已清理的死代码

| 文件 | 清理项 | 说明 |
|------|--------|------|
| `web_server.py` L7 | `import time` | 未使用 |
| `web_server.py` L11 | `Response` from flask | 未使用 |
| `web_server.py` L24 | `save_all` import | 未在路由中调用 |
| `web_server.py` L27 | `storage_load_all` alias | 未使用 |
| `web_server.py` L30 | `analyze_cover_image_sync` | 未使用 |

## 11. 常见问题

**Q: 搜索无结果？**
A: 检查 `.env` 中 Cookie 是否登录且未过期。

**Q: AI 脚本生成失败？**
A: 确认 ARK_API_KEY 有效、模型已开通。模型 `doubao-seed-2-0-pro-260215` 是推理模型，响应格式已适配。

**Q: 视频分析无输出？**
A: 需先在"竞品发现"面板拉取博主视频，再到"视频分析"面板选择分析。

**Q: 直播间监听无输出？**
A: 需修改 `dy_live/server.py` 中的 `live_id` 为正在直播的房间号。
