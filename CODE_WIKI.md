# 爆款工坊 · xunjia-content-marketing Code Wiki

> AI 内容生产与品牌增长系统 · 全链路抖音内容营销自动化
> 生成时间：2026-09-10

本文档是 `xunjuneirongyingxiao-main` 仓库的 Code Wiki，覆盖项目整体架构、主要模块职责、关键类与函数、依赖关系与运行方式。所有路径引用均相对仓库根 `xunjuneirongyingxiao-main/`。

---

## 目录

1. [项目定位与全链路](#1-项目定位与全链路)
2. [整体架构](#2-整体架构)
3. [仓库结构总览](#3-仓库结构总览)
4. [主项目 DouYin_Spider-master 模块详解](#4-主项目-douyin_spider-master-模块详解)
5. [核心类与函数说明](#5-核心类与函数说明)
6. [数据模型与存储](#6-数据模型与存储)
7. [依赖关系](#7-依赖关系)
8. [项目运行方式](#8-项目运行方式)
9. [关键调用链](#9-关键调用链)
10. [已知技术债与边界](#10-已知技术债与边界)

---

## 1. 项目定位与全链路

`xunjia-content-marketing` 是一套围绕「抖音爆款短视频生产」的全链路工具集，从 **素材采集 → AI 分析 → 智能剪辑 → 政策文件沉淀** 一站式打通。

**核心全链路：**
```
抖音采集 → 火山方舟 AI 视频分析 → AI 脚本重构 → Smart-Clip MCP AI 智能剪辑 → 输出成片
```

仓库由一个主项目 + 多个第三方依赖子项目组成：

| 模块 | 类型 | 角色 |
|------|------|------|
| **DouYin_Spider-master** | 项目主代码 | 业务核心：采集 / 分析 / 出方案 / 混剪 / 漫剧 |
| **Smart-Clip-MCP** | 第三方依赖 | 执行层：FFmpeg 智能剪辑 MCP server |
| **CosyVoice** | 第三方依赖 | TTS：口播视频配音 |
| **imagedl** | 第三方依赖 | 素材获取：46 个图片源客户端 |
| **PolicyPrint** | 第三方依赖 | 政策文件采集（已改造为 requests 版） |
| **remotion-demo** | 项目工具 | Remotion 视频特效演示 |
| **MarketSpider** | 工具集 | 淘宝/京东/1688 数据采集（被 price_research 引用） |

---

## 2. 整体架构

### 2.1 架构全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                    浏览器（前端 SPA）                                │
│   templates/index.html + static/js/{app-*, tools.js}                │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTP / SSE
┌────────────────────────────────▼────────────────────────────────────┐
│                       Flask Web 服务（:5000）                        │
│         web_server.py（入口） → web/（17 个 Blueprint）              │
└──┬──────────┬──────────────┬──────────┬──────────┬─────────────────┘
   │          │              │          │          │
   ▼          ▼              ▼          ▼          ▼
┌──────┐  ┌────────┐    ┌─────────┐ ┌────────┐ ┌────────────┐
│dy_apis│  │services│    │scheduler│ │trendradar│ │web/ai_clip │
│抖音API │  │AI业务层 │    │APSchdlr │ │热点雷达 │  │→Smart-Clip│
└──┬───┘  └───┬────┘    └─────────┘ └─────────┘ └──────┬─────┘
   │           │                                          │
   ▼           ▼                                          ▼
┌──────────┐  ┌─────────────────┐                ┌──────────────┐
│builder/  │  │storage 门面     │                │Smart-Clip MCP│
│utils/   │  │↓ mysql / json   │                │(FFmpeg :8000)│
│签名算法  │  └─────────────────┘                └──────────────┘
└──────────┘           │           │
                       ▼           ▼
              ┌──────────────┐  ┌──────────────┐
              │ MySQL 8.0    │  │ 火山方舟 Ark │
              │ :3308→3306   │  │ 豆包 Seed 2.0│
              └──────────────┘  └──────────────┘
                       ▲
                       │
              ┌─────────────────┐
              │CosyVoice TTS    │
              │(WSL2 :50000)    │
              └─────────────────┘
```

### 2.2 分层架构

| 层 | 路径 | 职责 |
|----|------|------|
| 前端 | [templates/](DouYin_Spider-master/templates) + [static/js/](DouYin_Spider-master/static/js) | 单页应用，按面板拆分 JS |
| 路由层 | [web/](DouYin_Spider-master/web) | 17 个 Blueprint 路由，仅做请求转发 |
| 服务层 | [services/](DouYin_Spider-master/services) | AI 业务、存储门面、TTS、混剪、漫剧 |
| 采集层 | [dy_apis/](DouYin_Spider-master/dy_apis) + [builder/](DouYin_Spider-master/builder) + [utils/](DouYin_Spider-master/utils) | 抖音 Web API 封装 + 签名算法 |
| 调度层 | [scheduler/](DouYin_Spider-master/scheduler) | APScheduler 定时扫描博主/视频 |
| 数据层 | [models/](DouYin_Spider-master/models) + [storage_mysql.py](DouYin_Spider-master/services/storage_mysql.py) | dataclass + MySQL/JSON 双后端 |
| 子系统 | [trendradar/](DouYin_Spider-master/trendradar) | 独立热点雷达（RSS+AI+报告） |
| 外部依赖 | Smart-Clip-MCP / CosyVoice / imagedl / MarketSpider | 剪辑 / TTS / 素材 / 价格调研 |

---

## 3. 仓库结构总览

```
xunjuneirongyingxiao-main/
├── README.md                     # 项目根 README
├── .gitignore
├── DouYin_Spider-master/         # ★ 主项目（业务核心）
│   ├── web_server.py             #   Web 服务入口（仅 30 行）
│   ├── main.py                   #   命令行爬虫入口
│   ├── Dockerfile                #   Python 3.11-slim + ffmpeg + 中文字体
│   ├── docker-compose.yml        #   mysql + app 编排
│   ├── fly.toml                  #   Fly.io 部署配置
│   ├── start_all.bat             #   Windows 一键启动脚本
│   ├── requirements.txt          #   Python 依赖清单
│   ├── .env / .env.example       #   环境变量（密钥/MySQL 等）
│   ├── AGENTS.md                 #   ★ Agent 工作宪法（动手前必看）
│   ├── PROJECT_GUIDE.md          #   项目级开发指南
│   ├── 项目介绍.md / 项目功能介绍.md
│   ├── web/                      #   Flask 路由层（17 个 Blueprint）
│   ├── services/                 #   ★ AI 业务服务层（17 个模块）
│   ├── dy_apis/                  #   抖音 API 封装
│   ├── dy_live/                  #   直播间 WebSocket 监听
│   ├── builder/                  #   请求签名（X-Bogus/A-B/msToken）
│   ├── utils/                    #   签名算法 + 工具函数
│   ├── scheduler/                #   APScheduler 定时任务
│   ├── models/                   #   dataclass 数据模型
│   ├── trendradar/               #   热点雷达子系统（独立）
│   ├── config/                   #   提示词 + 配置文件
│   ├── templates/                #   HTML 模板（index.html / setup.html）
│   ├── static/                   #   前端资源（JS 按面板拆分）
│   ├── scripts/                  #   数据迁移脚本
│   ├── campaign_creator/         #   投放任务子模块（端口 8686）
│   ├── author/                   #   抖音账号管理
│   ├── 量化模型/                  #   宠物趋势预测子模块
│   ├── _rebuild/ debug/ data/    #   历史数据/调试
│   └── datas/                    #   媒体/Excel/上传/输出
├── Smart-Clip-MCP/              # 第三方：AI 智能剪辑 MCP server
├── CosyVoice/                   # 第三方：阿里 TTS 大模型
├── imagedl/                     # 第三方：pyimagedl 0.5.3 镜像
├── PolicyPrint/                 # 第三方：政策文件 PDF 打印
├── remotion-demo/               # 项目工具：Remotion 视频特效演示
└── MarketSpider/                # 工具集：电商爬虫
```

---

## 4. 主项目 DouYin_Spider-master 模块详解

### 4.1 入口与 Web 层

#### `web_server.py` —— Web 服务入口

[web_server.py](DouYin_Spider-master/web_server.py) 是 Flask 主入口（仅 30 行），职责：

1. 把项目根加入 `sys.path`
2. 调用 [web/context.py](DouYin_Spider-master/web/context.py) 的 `init_app()` 初始化全局上下文
3. 调用 [web/__init__.py](DouYin_Spider-master/web/__init__.py) 的 `create_app()` 创建 Flask 实例并启动

关键代码：
```python
host = os.environ.get('WEB_HOST', '0.0.0.0')
port = int(os.environ.get('WEB_PORT', '5000'))
app.run(host=host, port=port, debug=False, threaded=True)
```

#### `web/` —— Blueprint 路由层

[web/__init__.py](DouYin_Spider-master/web/__init__.py) 是应用工厂，注册 17 个 Blueprint：

| Blueprint | 文件 | 职责 |
|-----------|------|------|
| auth | web/auth.pyc | 用户登录/登出/注册 |
| douyin | web/douyin.pyc | 抖音手动工具（搜索/用户/作品/直播/私信） |
| brands | web/brands.pyc | 品牌/SKU CRUD |
| competitors | web/competitors.pyc | 竞品博主 CRUD + 一键拉视频 |
| dashboard | web/dashboard.pyc | 数据看板 |
| analysis | web/analysis.pyc | 视频多模态分析 |
| scripts | web/scripts.pyc | AI 脚本生成 |
| ad | web/ad.pyc | 投流分析 |
| price_research | web/price_research.pyc | 价格调研 |
| trend | web/trend.pyc | 视频趋势 |
| intent | web/intent.pyc | 意向客户分析 |
| trendradar | web/trendradar.pyc | 热点雷达 |
| videos | web/videos.pyc | 视频/素材库/混剪 |
| prompts | web/prompts.pyc | AI 提示词在线编辑 |
| pages | web/pages.pyc | 静态页面 |
| comic | [web/comic.py](DouYin_Spider-master/web/comic.py) | AI 漫剧设计中心 |
| ai_clip | [web/ai_clip.py](DouYin_Spider-master/web/ai_clip.py) | AI 智能剪辑（Smart-Clip MCP） |

> ⚠ **注意**：除 `ai_clip.py` / `comic.py` / `context.py` / `__init__.py` 外，其余蓝图以 `.pyc` 编译产物形式分发。修改前需通过反编译或通过原仓库源码确认 API 形态。

#### `web/context.py` —— 全局运行上下文

[web/context.py](DouYin_Spider-master/web/context.py) 提供共享全局状态：

- `BASE_DIR`：项目根路径（自动 `sys.path` 注入）
- `auth` / `base_path` / `daily_monitor`：全局认证与调度器（由 `init_app()` 初始化）
- `radar_lock` / `radar_running` / `radar_log`：热点雷达运行状态
- `init_app()`：调用 `utils/common_util.init()` + `user_auth.ensure_admin()` + `DailyMonitor.start()`

#### 请求钩子（在 `web/__init__.py` 注册）

```python
@app.before_request
def _load_current_user():
    """根据 session 设置当前用户上下文（供 storage 门面做数据隔离）。"""

@app.teardown_request
def _clear_current_user(exc=None):
    clear_current_user()

@app.after_request
def _no_cache(resp):
    """全局禁用缓存。"""
```

### 4.2 服务层 services/（核心 AI 业务）

[services/](DouYin_Spider-master/services) 是项目的核心增值层，共 17 个模块，全部以火山方舟 Ark API + 豆包 Seed 2.0 为统一 AI 入口。

#### 存储门面（必读）

[services/storage.py](DouYin_Spider-master/services/storage.py) 是**所有数据读写的唯一入口**，业务代码必须通过它，禁止直接读 `datas/app_data/*.json` 或裸 SQL。

核心机制：

- 通过 `STORAGE_BACKEND` 环境变量在 `mysql`（默认）/ `json` 之间切换
- 对外提供 7 个函数：`save_all` / `load_all` / `save_one` / `update_one` / `delete_one` / `find_by_id` / `find_by`
- 用户隔离：`SCOPED_ENTITIES = {"brands", "competitors", "videos", "tasks", "media_library", "mashup_results", "comic_designs"}` 内的实体按 `owner_id` 隔离
- `set_current_user()` / `clear_current_user()` 是 thread-local 上下文，由 `web/__init__.py` 的 `before_request` 注入

#### AI 调用门面

[services/ai_keyword.py](DouYin_Spider-master/services/ai_keyword.py) 提供**所有 AI 调用的统一入口**：

- `_call_ai(prompt)` → 火山方舟 Ark `/responses` 端点
- `_parse_json_response(text)` → 容错 JSON 提取（json-repair 思路，3 重兜底）
- `_build_brand_text(brand)` → 品牌画像文本化（多个 AI 模块复用）
- `extract_keywords(brand)` → 输出 4 类搜索关键词
- `recommend_cross_categories(brand)` → 推荐可借鉴的跨赛道品类

> 约定：新增 AI 调用必须复用 `ai_keyword._call_ai` + `_parse_json_response`，避免重复实现。

#### 各业务服务模块

| 模块 | 文件 | 核心职责 |
|------|------|---------|
| 视频分析 | [services/video_analyzer.py](DouYin_Spider-master/services/video_analyzer.py) | 上传视频到 Ark Files API → 豆包多模态分析文本结构（hook/body/cta）、视频类型、场景、情绪、分镜 |
| 视频分类 | [services/video_classifier.py](DouYin_Spider-master/services/video_classifier.py) | 上传素材视频 → 多模态分类 + 时间线片段标注（供混剪使用） |
| 智能混剪 | [services/video_mashup.py](DouYin_Spider-master/services/video_mashup.py) | 文案拆分 → AI 匹配素材片段 → CosyVoice TTS → FFmpeg 拼接输出 MP4 |
| TTS 配音 | [services/tts.py](DouYin_Spider-master/services/tts.py) | CosyVoice 预置 7 音色 + 零样本克隆 + 按「风格调性+文案」智能配对 |
| 剪辑方案 | [services/video_plan.py](DouYin_Spider-master/services/video_plan.py) | 多模态直出 VideoPlan V2.0 JSON（含 timeline/clips/material_assets/packaging） |
| 脚本生成 | [services/script_generator.py](DouYin_Spider-master/services/script_generator.py) | 基于对标视频结构 + 品牌画像生成参考脚本 |
| 竞品发现 | [services/competitor_discovery.py](DouYin_Spider-master/services/competitor_discovery.py) | 同赛道三步评估（粉丝量级 / 数据稳定 / 内容可复制） + 跨赛道推荐 |
| 投流分析 | [services/ad_advisor.py](DouYin_Spider-master/services/ad_advisor.py) | 基于互动数据 + 内容结构 + 品牌画像输出投流建议 |
| 意向分析 | [services/intent_analyzer.py](DouYin_Spider-master/services/intent_analyzer.py) | 抓取评论区 → AI 分级购买意向（高/中/低/无） |
| 价格调研 | [services/price_research.py](DouYin_Spider-master/services/price_research.py) | 调用 MarketSpider 抓取淘宝/京东/1688 商品 |
| 淘宝抓取 | [services/taobao_api.py](DouYin_Spider-master/services/taobao_api.py) | Headless Chrome 抓取淘宝搜索结果 |
| 数据采集 | [services/data_collector.py](DouYin_Spider-master/services/data_collector.py) | 拉取监听视频的最新互动数据 + 看板查询 |
| 用户认证 | [services/user_auth.py](DouYin_Spider-master/services/user_auth.py) | 注册/登录 + 两级权限（admin/user） + 按用户分配功能 |
| 漫剧设计 | [services/comic_designer.py](DouYin_Spider-master/services/comic_designer.py) | 三阶段剧本→分镜→Seedance 视频提示词工作流 |
| 存储门面 | [services/storage.py](DouYin_Spider-master/services/storage.py) | JSON/MySQL 切换 + 用户数据隔离 |
| MySQL 后端 | [services/storage_mysql.py](DouYin_Spider-master/services/storage_mysql.py) | 11 张表的 CRUD + 建表语句 |
| JSON 后端 | [services/storage_json.py](DouYin_Spider-master/services/storage_json.py) | JSON 文件后端（旧版兼容） |

#### AI 提示词位置约定

- **业务提示词**：写在 `services/<xxx>.py` 内（与 `_call_ai` 同文件），用 Python `.format()` 模板
- **趋势雷达提示词**：写在 [config/ai_analysis_prompt.txt](DouYin_Spider-master/config/ai_analysis_prompt.txt) / [config/ai_translation_prompt.txt](DouYin_Spider-master/config/ai_translation_prompt.txt)，Web 端 `/api/prompts` 可在线编辑
- **漫剧三阶段提示词**：写在 [config/comic_design/](DouYin_Spider-master/config/comic_design)，对应 `comic_designer._load_prompt()`

### 4.3 采集层

#### `dy_apis/douyin_api.py` —— 抖音 API 封装

[dy_apis/douyin_api.py](DouYin_Spider-master/dy_apis/douyin_api.py) 是采集层大头（约 98KB），封装全部抖音 Web API：

| 能力 | 方法 |
|------|------|
| 综合搜索 | `search_some_general_work` |
| 用户搜索 | `search_some_user` |
| 直播搜索 | `search_some_lives` |
| 用户信息 | `get_user_info` / `get_user_all_work_info` |
| 作品详情 | `get_work_info` |
| 粉丝/关注 | `get_follower_list` 等 |
| 直播弹幕 | `live_room_server` |
| 私信 | `create_conversation` / `send_msg` |
| 互动 | `digg` / `collect_aweme` / `publish_comment` |
| 推荐流 | `get_feed` |

调用流程：`DouyinAPI.<方法>(auth, ...)` → `builder/` 签名 → `requests.post` → protobuf/JSON 解析

#### `builder/` —— 请求签名

[builder/](DouYin_Spider-master/builder) 提供 X-Bogus / A-B / msToken / ttwid 等抖音 Web 反爬签名：

- [builder/auth.py](DouYin_Spider-master/builder/auth.py) — `DouyinAuth` 类，cookie 解析 + msToken 惰性获取
- [builder/header.py](DouYin_Spider-master/builder/header.py) — `HeaderBuilder` + `HeaderType` 枚举
- [builder/params.py](DouYin_Spider-master/builder/params.py) — `Params` 类，参数编码与验签
- [builder/proto.py](DouYin_Spider-master/builder/proto.py) — protobuf 构造

#### `utils/` —— 工具函数与签名算法

[utils/](DouYin_Spider-master/utils) 包含核心签名算法（纯 Python 实现）：

- [utils/ab_pure.py](DouYin_Spider-master/utils/ab_pure.py) — A-B 算法
- [utils/xbogus_pure.py](DouYin_Spider-master/utils/xbogus_pure.py) — X-Bogus 签名
- [utils/mstoken.py](DouYin_Spider-master/utils/mstoken.py) — msToken 生成
- [utils/sm3.py](DouYin_Spider-master/utils/sm3.py) — 国密 SM3
- [utils/fingerprint.py](DouYin_Spider-master/utils/fingerprint.py) — 浏览器指纹
- [utils/dy_util.py](DouYin_Spider-master/utils/dy_util.py) — 拼接 URL / 生成 A-Bogus / msToken 等组合
- [utils/common_util.py](DouYin_Spider-master/utils/common_util.py) — `init()` 加载环境与认证
- [utils/data_util.py](DouYin_Spider-master/utils/data_util.py) — `handle_work_info` 数据解析 + `download_work` + `save_to_xlsx`

#### `dy_live/server.py` —— 直播间 WebSocket 监听

[dy_live/server.py](DouYin_Spider-master/dy_live/server.py) 是独立脚本，监听直播弹幕/礼物/进场等事件。需手动指定 `live_id`，**未接入 Web 前端的实时弹幕流**。

#### `dy_apis/douyin_recv_msg.py` —— 私信实时接收

独立脚本，监听抖音私信 WebSocket，**未接入 Web 前端**。

### 4.4 调度层 scheduler/

[scheduler/daily_monitor.py](DouYin_Spider-master/scheduler/daily_monitor.py) 基于 APScheduler 实现两个定时任务：

- `DailyMonitor.scan_new_bloggers()` — 每日 10:00 扫描新博主（根据品牌画像搜索 → 标 `reviewing` 待审核）
- `DailyMonitor.monitor_tracked_bloggers()` — 每日 11:00 监听已关注博主新视频（标 `pending` 待分析）

由 [web/context.py](DouYin_Spider-master/web/context.py) 的 `init_app()` 启动：`daily_monitor = DailyMonitor(auth); daily_monitor.start()`。

### 4.5 数据层 models/

[models/](DouYin_Spider-master/models) 是 4 个 dataclass 数据模型：

- [models/brand.py](DouYin_Spider-master/models/brand.py) — `Brand`：name / category / target_audience / product_desc / style_tone / selling_points / skus
- [models/competitor.py](DouYin_Spider-master/models/competitor.py) — `Competitor`：user_id / sec_uid / nickname / follower_count / status / source_brand_id
- [models/video.py](DouYin_Spider-master/models/video.py) — `Video`：aweme_id / title / stats / text_structure / video_type / scripts
- [models/task.py](DouYin_Spider-master/models/task.py) — `Task`：task_type / status / result_summary / started_at / completed_at

### 4.6 子系统 trendradar/

[trendradar/](DouYin_Spider-master/trendradar) 是独立的热点雷达子系统（v6.10.0）：

- 采集 RSS → AI 过滤 / 分析 / 翻译 → HTML 报告 → 飞书/钉钉通知
- 通过 [web/trendradar.pyc](DouYin_Spider-master/web) 暴露 `/api/trendradar/*` 路由
- 子目录：`ai/` / `commands/` / `core/` / `crawler/` / `notification/` / `report/` / `storage/` / `utils/`
- 主入口 [trendradar/__main__.py](DouYin_Spider-master/trendradar/__main__.py)（约 75KB）
- 上下文类 `AppContext` 在 [trendradar/context.py](DouYin_Spider-master/trendradar/context.py)

### 4.7 配置层 config/

[config/](DouYin_Spider-master/config) 存放可在线编辑的提示词与配置：

- `ai_analysis_prompt.txt` / `ai_translation_prompt.txt` / `ai_interests.txt` — 雷达 AI 提示词
- `frequency_words.txt` / `frequency_words.en.txt` — 词频统计词表
- `config.yaml` / `config.en.yaml` — 雷达配置
- `timeline.yaml` / `timeline.en.yaml` — 时间线配置
- `comic_design/` — 漫剧三阶段角色提示词模板
- `ai_filter/` / `custom/` — AI 过滤器配置

### 4.8 前端层

前端是**前后端不分离的单页应用**（Flask 模板 + 原生 JS）：

- [templates/index.html](DouYin_Spider-master/templates/index.html) — 主控制台 SPA（约 105KB），含 7 个功能面板
- [templates/setup.html](DouYin_Spider-master/templates/setup.html) — 扫码登录/凭证设置页
- [static/js/](DouYin_Spider-master/static/js) — JS 按面板拆分：
  - `app-brands.js` / `app-discovery.js` / `app-monitor.js` / `app-intent.js`
  - `app-price-research.js` / `app-comic.js` / `app-campaign.js`
  - `app-helpers.js` / `app-panels.js`
  - `tools.js` — 手动工具 + 导航 + 公共函数（约 115KB）
- [static/css/style.css](DouYin_Spider-master/static/css/style.css) — 样式

---

## 5. 核心类与函数说明

### 5.1 Web 入口

#### `web_server.py`

| 函数/变量 | 说明 |
|----------|------|
| `app` | `create_app()` 返回的 Flask 实例 |
| `host` / `port` | 从环境变量 `WEB_HOST` / `WEB_PORT` 读取，默认 `0.0.0.0:5000` |

#### `web/__init__.py`

| 函数 | 说明 |
|------|------|
| `create_app()` | Flask 应用工厂：注册 17 个 Blueprint + 请求钩子 |
| `_register_hooks(app)` | 注册 `before_request`（注入登录上下文）/ `teardown_request`（清理）/ `after_request`（禁用缓存） |

#### `web/context.py`

| 函数/变量 | 说明 |
|----------|------|
| `BASE_DIR` | 项目根路径（绝对路径） |
| `auth` | 全局 `DouyinAuth` 实例（由 `init_app()` 设置） |
| `base_path` | 媒体/Excel 输出根路径 dict |
| `daily_monitor` | 全局 `DailyMonitor` 实例 |
| `radar_lock` / `radar_running` / `radar_log` | 雷达运行状态 + 日志缓冲（线程安全） |
| `init_app()` | 初始化 auth / base_path / daily_monitor + 启动调度器 |

### 5.2 存储门面 services/storage.py

| 函数 | 说明 |
|------|------|
| `set_current_user(user_id, role)` | 设置当前登录用户（thread-local） |
| `get_current_user()` | 返回 `(user_id, role)` |
| `clear_current_user()` | 清空当前用户 |
| `save_all(entity_name, data_list)` | 覆盖写入（不做隔离，系统/迁移用） |
| `load_all(entity_name)` | 加载全部（普通用户仅返回自己的数据） |
| `save_one(entity_name, item)` | 保存单条，自动注入 owner_id |
| `update_one(entity_name, item_id, updates)` | 更新单条（普通用户只能改自己的） |
| `delete_one(entity_name, item_id)` | 删除单条 |
| `find_by_id(entity_name, item_id)` | 按 ID 查找（隔离生效） |
| `find_by(entity_name, predicate_func)` | 按谓词过滤 |
| `exists_any(entity_name, item_id)` | 判断存在（不受隔离） |
| `SCOPED_ENTITIES` | 需按用户隔离的实体集合 |
| `BACKEND` | 当前后端类型（`json` / `mysql`） |

### 5.3 AI 调用入口 services/ai_keyword.py

| 函数 | 说明 |
|------|------|
| `_call_ai(prompt)` | 调用 Ark API `/responses` 端点，返回文本 |
| `_parse_json_response(text)` | 3 重兜底 JSON 提取（直接 / ```json``` 块 / 第一个 `{...}` 块） |
| `_build_brand_text(brand)` | 品牌画像 dict → 可读文本 |
| `extract_keywords(brand)` | 输出 4 类搜索关键词（category/scene/audience/content） |
| `recommend_cross_categories(brand)` | 推荐可借鉴的跨赛道品类 |

### 5.4 视频分析 services/video_analyzer.py

| 函数 | 说明 |
|------|------|
| `_get_client()` | 返回 `AsyncArk` 客户端 |
| `analyze_video(video_path, title, desc)` | 异步多模态分析视频（上传 → wait → responses.create → 解析 JSON） |
| `analyze_video_sync(...)` | 同步版本，内部 `asyncio.run(analyze_video)` |
| `_analyze_cover_image(cover_url, title)` | 多模态分析封面图 |
| `analyze_cover_image_sync(...)` | 同步版本 |

输出结构（参见 [services/video_analyzer.py](DouYin_Spider-master/services/video_analyzer.py) L33-39）：
```python
{
    "text_structure": {"hook": "...", "body": "...", "cta": "..."},
    "video_type": "...",
    "scene_desc": "...",
    "mood": "...",
    "product_analysis": {...},
    "marketing_strategy": {...},
    "storyboard": [{...}],
    "raw_response": "..."
}
```

### 5.5 剪辑方案 services/video_plan.py

| 函数 | 说明 |
|------|------|
| `_get_client()` | 返回 `AsyncArk` |
| `_build_prompt(intent, clip_count, ...)` | 构造剪辑执行级脚本的提示词（含 timeline / material_assets / clips / packaging） |
| `generate_video_plan(video_path, intent, ...)` | 异步多模态直出 VideoPlan JSON |
| `_parse_plan_json(raw_text)` | 容错提取 JSON |
| `generate_video_plan_sync(...)` | 同步版本 |

模型：`doubao-seed-2-0-lite-260428`（多模态）。

### 5.6 智能混剪 services/video_mashup.py

| 函数 | 说明 |
|------|------|
| `_find_ffmpeg()` | 探测 ffmpeg/ffprobe 路径（优先 `%LOCALAPPDATA%\ffmpeg\ffmpeg-*\bin\`） |
| `get_video_duration(video_path)` | 用 ffprobe 获取时长（秒） |
| `get_video_aspect(video_path)` | 获取画面比例（`9:16` / `16:9` / `1:1`） |
| `split_script_to_segments(script)` | 文案按句号/逗号拆分 |
| `build_video_inventory(classified_videos)` | 构建视频库描述（含 AI 时间线片段） |
| `ai_match_script_to_videos(...)` | AI 将每段文案匹配到具体视频+时间片段 |
| `_fallback_match(...)` | AI 失败时降级按顺序分配 |

### 5.7 TTS services/tts.py

| 函数/常量 | 说明 |
|----------|------|
| `TTS_SERVICE_URL` | CosyVoice 服务地址（默认 `http://127.0.0.1:50000`） |
| `VOICE_LIBRARY` | CosyVoice-300M-SFT 预置 7 音色 |
| `DEFAULT_VOICE` / `DEFAULT_RATE` | 默认音色「中文女」、默认语速 0.88 |
| `get_voice_library()` | 返回音色库（前端下拉框） |
| `resolve_voice(style_tone, script, preferred)` | 智能配对音色 |

### 5.8 漫剧设计 services/comic_designer.py

| 函数 | 说明 |
|------|------|
| `_load_prompt(filename)` | 从 `config/comic_design/` 读取角色提示词模板 |
| `_make_title(script_text)` | 从剧本首行提取标题 |
| `_build_prompt(role_prompt, script_text, extra_context)` | 角色模板 + 任务指令 + 前置阶段成果 + 剧本 → 单条 user prompt |
| `_get_or_create(design_id, script_text)` | 获取/创建漫剧设计记录 |
| `_run_stage(record, field, prompt)` | 调用 AI 执行单阶段并落库 |
| `design_art(design_id, script_text)` | 阶段一：美术视觉资产 |
| `design_storyboard(design_id, script_text)` | 阶段二：专业分镜表（依赖阶段一） |
| `design_video(design_id, script_text)` | 阶段三：T2I 提示词 + Seedance 视频提示词（依赖阶段二） |
| `to_public(record)` | 列表展示用（不含长文本） |

### 5.9 AI 智能剪辑 web/ai_clip.py

| 函数/路由 | 说明 |
|----------|------|
| `_mcp_call(tool_name, arguments)` | 通过 MCP SSE 协议调用 Smart-Clip 工具 |
| `_parse_response(text)` | 解析 MCP 响应（JSON 或 SSE data 行） |
| `IMAGEDL_SOURCES` | imagedl 支持的 15 个图片搜索源 |
| `MATERIALIZE_STYLES` | 文本→图片素材的 3 种配色（dark / news / light） |
| `_find_cjk_font()` | 探测中文字体路径 |
| `_gradient_bg(...)` | 竖向渐变背景 |
| `_wrap_text(draw, text, font, max_width)` | 自动换行 |
| `_split_segments(text, max_chars)` | 长文本按句号切段 |
| `_render_material_card(...)` | 渲染单张竖屏卡片图 |
| `_save_video_plan(...)` | 落库 VideoPlan 到 `ai_clip_video_plans` 表 |

主要路由：

| 路由 | 方法 | 用途 |
|------|------|------|
| `/api/aiclip/status` | GET | 检测 Smart-Clip MCP 是否在线 |
| `/api/aiclip/test-material/sources` | GET | 返回支持的图片搜索源 |
| `/api/aiclip/test-material` | POST | imagedl 搜图 + 下载 |
| `/api/aiclip/test-policyprint` | POST | 抓取 gov.cn 政策文件 → txt |
| `/api/aiclip/materialize` | POST | 文本 → 竖屏卡片图 |
| `/api/aiclip/upload` | POST | 上传视频（web + 转发 MCP） |
| `/api/aiclip/clip` | POST | 调用 Smart-Clip 智能剪辑 |
| `/api/aiclip/plan` | POST | 生成 V2.0 VideoPlan |
| `/api/aiclip/plan/<plan_id>` | GET | 拉取已落库 VideoPlan |
| `/api/aiclip/plan/list` | GET | 列出最近 N 条 VideoPlan |

### 5.10 漫剧路由 web/comic.py

| 路由 | 方法 | 用途 |
|------|------|------|
| `/api/comic/art` | POST | 阶段一：美术视觉资产 |
| `/api/comic/storyboard` | POST | 阶段二：分镜表 |
| `/api/comic/video` | POST | 阶段三：视频提示词 |
| `/api/comic/history` | GET | 设计历史 |
| `/api/comic/<design_id>` | GET | 单条详情 |
| `/api/comic/<design_id>` | DELETE | 删除 |

### 5.11 竞品发现 services/competitor_discovery.py

筛选阈值常量（位于 [services/competitor_discovery.py](DouYin_Spider-master/services/competitor_discovery.py) L22-32）：

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `FOLLOWER_RATIO_MIN` | 1.0 | 成长期候选粉丝下限倍数 |
| `FOLLOWER_RATIO_MAX` | 5.0 | 成长期候选粉丝上限倍数 |
| `COLD_START_THRESHOLD` | 1000 | 当前粉丝低于此值视为冷启动 |
| `COLD_START_FLOOR` | 10000 | 冷启动时候选粉丝下限 |
| `COLD_START_CEILING` | 100000 | 冷启动时候选粉丝上限 |
| `MIN_FOLLOWERS` | 100 | 候选粉丝硬性最低门槛 |
| `TREND_LOOKBACK_DAYS` | 90 | 数据稳定性回看窗口 |
| `TREND_SAMPLE_WORKS` | 10 | 播放量趋势采样条数 |
| `TREND_MIN_WORKS` | 3 | 近 3 月最少发布数 |
| `REPLICABILITY_MIN_SCORE` | 3 | AI 可复制性评分阈值（1-5） |
| `REPLICABILITY_BATCH_SIZE` | 10 | AI 评估每批候选数 |

### 5.12 调度器 scheduler/daily_monitor.py

`DailyMonitor` 类：

| 方法 | 说明 |
|------|------|
| `__init__(auth)` | 创建 `BackgroundScheduler` |
| `scan_new_bloggers()` | 扫描新博主（根据品牌画像搜索 → 标 `reviewing`） |
| `monitor_tracked_bloggers()` | 监听已关注博主新视频（标 `pending`） |
| `start(scan_hour=10, scan_minute=0)` | 注册两个 cron 任务（10 点扫博主、11 点监听视频） |
| `stop()` | 关闭调度器 |
| `get_status()` | 返回运行状态 + 最近 5 条任务 |

### 5.13 抖音 API dy_apis/douyin_api.py

`DouyinAPI` 类（全部静态方法），核心方法：

| 方法 | 用途 |
|------|------|
| `get_user_all_work_info(auth, user_url, max_count)` | 获取用户全部作品（自动翻页） |
| `get_user_work_info(auth, user_url, max_cursor)` | 获取单页作品 |
| `get_user_info(auth, user_url)` | 获取用户详情 |
| `get_work_info(auth, work_url)` | 获取作品详情 |
| `search_some_general_work(...)` | 综合搜索作品 |
| `search_some_user(auth, query, num)` | 搜索用户 |
| `search_some_lives(...)` | 搜索直播间 |
| `get_follower_list(...)` | 粉丝列表 |
| `create_conversation(...)` / `send_msg(...)` | 私信 |
| `digg(...)` / `collect_aweme(...)` / `publish_comment(...)` | 互动 |
| `get_feed(...)` | 推荐流 |

### 5.14 用户认证 services/user_auth.py

| 函数/常量 | 说明 |
|----------|------|
| `ALL_FEATURES` | 全部功能 key 列表（22 项） |
| `USER_FEATURES` | 普通用户默认可见的功能（9 项核心运营） |
| `ADMIN_ONLY_FEATURES` | 管理员专属（`admin-users`） |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 默认管理员 `admin` / `admin123` |
| `ensure_admin()` | 启动时确保管理员存在 |
| `ensure_user_brands()` | 为无品牌用户补建同名品牌 |
| `register_user(username, password)` | 注册普通用户 |
| `authenticate(username, password)` | 校验密码 |
| `get_user(user_id)` / `get_features(user)` | 用户信息 / 功能列表 |
| `list_users()` | 全部用户列表 |
| `set_user_feature(user_id, feature, enabled)` | 修改用户功能权限 |

### 5.15 投流分析 services/ad_advisor.py

| 函数 | 说明 |
|------|------|
| `_call_ai(prompt)` | 调用 Ark `/responses` |
| `analyze_ad_potential(video_id, budget_range)` | 单视频投流潜力分析 |
| `compare_videos(video_ids)` | 多视频对比 + 按 confidence 排序 |

---

## 6. 数据模型与存储

### 6.1 dataclass 模型

| 模型 | 字段 |
|------|------|
| `Brand` | id / name / category / target_audience / product_desc / style_tone / selling_points / skus / owner_id / created_at / updated_at |
| `Competitor` | id / user_id / sec_uid / nickname / avatar / follower_count / category / status / notes / source_brand_id / filters / pass_count / owner_id |
| `Video` | id / aweme_id / title / description / cover_url / video_url / local_path / duration / author_name / author_id / stats / analysis_status / text_structure / video_type / scene_desc / cover_desc / mood / scripts / competitor_id / first_seen_at |
| `Task` | id / task_type / status / brand_id / result_summary / error_message / started_at / completed_at / owner_id |

### 6.2 MySQL 表清单

[services/storage_mysql.py](DouYin_Spider-master/services/storage_mysql.py) 管理 11 张表（`CREATE TABLE IF NOT EXISTS` 自动建表）：

| 表名 | 用途 | 是否按用户隔离 |
|------|------|----------------|
| `brands` | 品牌画像 | ✅ |
| `competitors` | 竞品博主 | ✅ |
| `videos` | 视频数据 | ✅ |
| `tasks` | 任务记录 | ✅ |
| `users` | 用户账号 | — |
| `media_library` | 素材库 | ✅ |
| `mashup_results` | 混剪结果 | ✅ |
| `intent_analysis` | 意向分析 | ❌（全局共享） |
| `price_research` | 价格调研 | ❌（全局共享） |
| `xiaohongshu_import` | 小红书导入 | — |
| `trend_samples` | 趋势样本 | — |
| `comic_designs` | 漫剧设计 | ✅ |
| `ai_clip_video_plans` | AI 剪辑方案 | ✅ |

字段映射原则：
- 标量字段 → MySQL 真实列
- 嵌套 dict/list → MySQL JSON 列（`_JSON_COLUMNS` 指定）
- `videos.stats` 单个 JSON 列（键数可变，不拆列）

### 6.3 JSON 后端

[services/storage_json.py](DouYin_Spider-master/services/storage_json.py) 是 JSON 文件后端（旧版兼容），数据存储在 `datas/app_data/*.json`，已切换 MySQL 后不会被读取。

---

## 7. 依赖关系

### 7.1 主项目 Python 依赖

来源：[requirements.txt](DouYin_Spider-master/requirements.txt)

| 类别 | 包 | 说明 |
|------|----|------|
| 异步 IO | aiofiles / aiohttp / websockets / websocket-client | 直播间 / 私信 WebSocket |
| HTTP | requests / urllib3 | API 调用 |
| Web 框架 | flask ≥ 3.0 / flask-cors ≥ 4.0 / werkzeug ≥ 3.0 | Flask + Blueprint |
| 调度 | APScheduler ≥ 3.10 | 定时任务 |
| AI SDK | `volcengine-python-sdk[ark] ≥ 5.0` | ⚠ 不要装 `volcenginesdkarkruntime`（空壳包） |
| 数据库 | pymysql / cryptography | MySQL |
| 签名 | protobuf ≥ 5.27.1, < 6.0 | ⚠ `blackboxprotobuf` 必须 `--no-deps` 安装 |
| 视频 | opencv-python-headless ≥ 4.8 / numpy | 抽帧 / 分镜 |
| 雷达 | litellm ≥ 1.40 / ruamel.yaml / json-repair / feedparser / PyYAML / pytz | 多模型路由 + RSS |
| 浏览器 | selenium ≥ 4.15 | 淘宝价格调研（无浏览器时降级） |
| 工具 | loguru / python-dotenv / qrcode / retry / beautifulsoup4 / openpyxl / pillow | 日志 / 配置 / 二维码 / Excel |
| TTS | edge-tts | 已废弃（改用 CosyVoice，仍保留） |

### 7.2 外部服务依赖

| 服务 | 用途 | 端口 | 必需性 |
|------|------|------|--------|
| MySQL 8.0 | 数据持久化 | 3308→3306 | ✅ 必需（STORAGE_BACKEND=mysql） |
| 火山方舟 Ark | AI 大模型 | — | ✅ 必需（所有 AI 功能） |
| CosyVoice | TTS 配音 | 50000 | ⚠ 可选（不启动则配音失效，不影响 Web） |
| Smart-Clip MCP | AI 智能剪辑 | 8000 | ⚠ 可选（不启动则混剪失效） |
| imagedl | 图片素材搜索 | — | ⚠ 可选（Dockerfile 已装 pyimagedl） |
| FFmpeg / ffprobe | 视频处理 | — | ✅ 必需（混剪/抽帧） |

### 7.3 第三方子项目依赖

#### Smart-Clip-MCP

[Smart-Clip-MCP/](Smart-Clip-MCP) — AI 智能剪辑 MCP server（Apache-2.0，作者 Ambrose）：

- 技术栈：Python ≥ 3.11 + FastMCP + librosa + scenedetect + pydantic + openai
- 入口：`smart-clip-mcp = "smart_clip.server:main"`（[pyproject.toml](Smart-Clip-MCP/pyproject.toml)）
- 工具：`smart_clip` / `repurpose` / `highlight_reel` / `analyze_content` / `get_edit_plan` / `get_video_plan`
- 启动：`smart-clip-mcp --transport sse --port 8000 --host 0.0.0.0`
- HTTP 端点：`/health` / `/upload` / `/output/<filename>`

#### CosyVoice

[CosyVoice/](CosyVoice) — FunAudioLLM 的 TTS 大模型（Fun-CosyVoice 3.0）：

- 支持多语言/方言、零样本语音克隆、流式推理、指令控制
- 部署：本地 WSL2 / Docker，端口 50000
- 在主项目中的封装：[services/tts.py](DouYin_Spider-master/services/tts.py)
- 调用端点：`/inference_sft`（预置音色）/ `/inference_zero_shot`（克隆）

#### imagedl

[imagedl/](imagedl) — CharlesPikachu/imagedl 本地镜像（pyimagedl 0.5.3）：

- 主类 `ImageClient` 位于 [imagedl/imagedl.py](imagedl/imagedl.py)
- 包含 46 个图片搜索源客户端（Baidu / Bing / Google / Pixabay / Unsplash / Pexels / NASA / Flickr 等）
- 用法：
  ```python
  from imagedl import imagedl
  client = imagedl.ImageClient(
      image_sources=["BingImageClient"],
      init_image_clients_cfg={"BingImageClient": {"work_dir": "./out", "max_retries": 2}},
  )
  results = client.search(keyword="cute cats", search_limits_per_source=5)
  downloaded = client.download(image_infos=results)
  ```
- 已通过 Dockerfile `pip install pyimagedl` 集成到 web 容器
- Web 端入口：[web/ai_clip.py](DouYin_Spider-master/web/ai_clip.py) 的 `/api/aiclip/test-material`

#### PolicyPrint

[PolicyPrint/](PolicyPrint) — 政府公文检索 + PDF 打印（Ancommie）：

- 原方案：Selenium + Edge + `Page.printToPDF` CDP
- 集成障碍：Edge 缺失 / code+sign 反爬 / JS 渲染三座大山
- **本项目已用 `requests` 方案替代**（[web/ai_clip.py](DouYin_Spider-master/web/ai_clip.py) 的 `/api/aiclip/test-policyprint`），直接抓 `gov.cn/zhengce/` 列表页 + `content_xxx.htm` 详情页

#### remotion-demo

[remotion-demo/](remotion-demo) — Remotion 9:16 带货片头 demo：

- 技术栈：Remotion 4 + React 18.3 + TypeScript 5.6 + KaTeX
- 启动：`npm install` → `npx remotion studio --port=3000`
- 主要组件：
  - `ScriptReplica.tsx` — 复刻爆款剪辑脚本可复刻元素（字幕系统 / 浏览器线框 / 画中画 / 对比图 / whip pan / 小红书卡片 / 撕纸边清单页 / vignette 暗角 / 3D 礼物盒 / 橙色弧线标注）
  - `PetAd.tsx` — 数据驱动批量出片验证
  - `BarChart3D.tsx` / `LineChart3D.tsx` / `PieChart3D.tsx` / `ProgressRing.tsx` / `RankBars.tsx` — 数据可视化
  - `theme.tsx` — 主题

#### MarketSpider

[MarketSpider/](MarketSpider) — 淘宝/京东/1688 商品爬虫（zhangjiancong）：

- 技术栈：Python ≥ 3.8 + Selenium + Tkinter GUI
- 核心文件：
  - `Core.py` — 核心库 v2.0-beta1
  - `Spider_jd.py` — 京东爬虫 v2.0.0
  - `Spider_taobao.py` — 淘宝爬虫 v1.2
  - `1688Spider.py` — 1688 爬虫 v1.0
  - `Starter.py` — 友好启动器
  - `GetCookie.py` — 自动化获取登录 cookie
- 集成位置：[services/price_research.py](DouYin_Spider-master/services/price_research.py) 把 `MarketSpider/` 目录加入 `sys.path`，封装为 API 可调用的后台服务
- 淘宝方案被本项目进一步改造为 Headless Chrome 版（[services/taobao_api.py](DouYin_Spider-master/services/taobao_api.py)）

### 7.4 内部模块依赖图

```
web_server.py
   │
   ├─→ web/__init__.py（create_app）
   │     ├─→ web/context.py（init_app）
   │     │     ├─→ utils/common_util.init（加载 .env / DouyinAuth）
   │     │     ├─→ services/user_auth.ensure_admin
   │     │     ├─→ services/user_auth.ensure_user_brands
   │     │     └─→ scheduler/daily_monitor.DailyMonitor
   │     └─→ 17 个 Blueprint（auth/douyin/.../ai_clip/comic）
   │           ├─→ services/storage（门面）
   │           ├─→ services/ai_keyword._call_ai（AI 入口）
   │           ├─→ services/video_analyzer / video_plan / video_mashup / ...
   │           ├─→ dy_apis/douyin_api（采集）
   │           │     └─→ builder/{auth,header,params,proto}
   │           │           └─→ utils/{ab_pure,xbogus_pure,mstoken,fingerprint}
   │           ├─→ services/tts → CosyVoice（外部）
   │           └─→ web/ai_clip → Smart-Clip MCP（外部）
   │                 └─→ imagedl（外部）
   │
   └─→ models/{brand,competitor,video,task}（dataclass）
```

---

## 8. 项目运行方式

### 8.1 Docker（推荐）

**完整运行栈**：xunjia-mysql + xunjia-web + smart-clip-mcp + Remotion Studio

```bash
# 1. 启动核心三件套（mysql / web / mcp）
cd DouYin_Spider-master
docker-compose up -d

# 2. 跨网络访问 MCP / CosyVoice（容器外访问容器内服务）
# docker-compose.yml 已配置 host.docker.internal + extra_hosts

# 3. 启动 Remotion Studio（独立项目）
cd ../remotion-demo
npm install
npx remotion studio --port=3000
```

**访问入口：**

| 服务 | 地址 |
|------|------|
| xunjia-web 爆款工坊 | http://localhost:5000/ |
| Smart-Clip MCP | http://localhost:8000/sse |
| Remotion Studio | http://localhost:3000/ |
| MySQL | localhost:3308 → 容器 3306 |

**默认账号：** `admin / admin123`

**容器编排要点（[docker-compose.yml](DouYin_Spider-master/docker-compose.yml)）：**
- `mysql` 服务：MySQL 8.0，`MYSQL_DATABASE=douyin_spider`，`MYSQL_USER=douyin`，端口 `3308:3306`，数据卷 `mysql-data`
- `app` 服务：基于根目录 [Dockerfile](DouYin_Spider-master/Dockerfile) 构建，环境变量覆盖 `MYSQL_HOST=mysql`、`STORAGE_BACKEND=mysql`、`WEB_HOST=0.0.0.0`、`SMART_CLIP_MCP_URL=http://host.docker.internal:8000`、`COSYVOICE_URL=http://host.docker.internal:50000`，`extra_hosts` 注入 `host.docker.internal:host-gateway`
- 数据卷：`mysql-data` / `app-datas`（采集媒体） / `app-output`（导出）
- 网络：`xunjia-net` bridge

**Dockerfile 要点（[Dockerfile](DouYin_Spider-master/Dockerfile)）：**
- 基础镜像：`python:3.11-slim`
- 系统包：`curl / gnupg / build-essential / ffmpeg / fonts-wqy-zenhei / tzdata`
- pip 安装：`-r requirements.txt` + `--no-deps blackboxprotobuf` + `pyimagedl`
- 运行期目录：`/app/datas/media_datas`、`/app/datas/excel_datas`、`/app/output`、`/app/Logs`
- 健康检查：`curl -fsS http://127.0.0.1:5000/`
- 启动命令：`python web_server.py`

### 8.2 本地直接运行（最快）

```bash
# 主 Web 服务（端口 5000）
python web_server.py

# 直播监听（独立脚本，需手动指定 live_id）
python dy_live/server.py

# 私信接收
python dy_apis/douyin_recv_msg.py

# 命令行爬虫（原始脚本）
python main.py
```

**Windows 一键启动（[start_all.bat](DouYin_Spider-master/start_all.bat)）：**
- Web Console → http://127.0.0.1:5000
- Live Monitor（默认 `live_id=432433667143`，见 `dy_live/server.py` 第 178 行）
- Campaign Agent → http://127.0.0.1:8686（独立 venv）
- DM Receiver

### 8.3 Fly.io 部署

[fly.toml](DouYin_Spider-master/fly.toml) 已就绪：

- `app = "xunju"`
- `primary_region = "sin"`
- `internal_port = 5000`
- 资源：1 CPU shared / 512MB
- `force_https = true` / `auto_start_machines = true` / `min_machines_running = 1`

部署命令：
```bash
fly deploy
fly secrets set ARK_API_KEY=... DY_COOKIES=...
```

⚠ 容器内必须 `WEB_HOST=0.0.0.0`，否则 Fly 探测失败。

### 8.4 关键环境变量（.env）

来源：[.env.example](DouYin_Spider-master/.env.example) + [AGENTS.md](DouYin_Spider-master/AGENTS.md) §7

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `DY_COOKIES` | 抖音 Web 采集认证 | 必填 |
| `DY_LIVE_COOKIES` | 直播监听 | 可选 |
| `DY_TICKET` / `DY_TS_SIGN` / `DY_CLIENT_CERT` / `DY_PRIVATE_KEY` | 私信签名 | 扫码登录后写入 |
| `ARK_API_KEY` | 火山方舟 API Key | 必填（所有 AI 失效） |
| `AI_API_URL` | Ark 入口 | `https://ark.cn-beijing.volces.com/api/v3` |
| `AI_MODEL` | 豆包模型 | `doubao-seed-2-0-pro-260215` |
| `VIDEO_PLAN_MODEL` | 剪辑方案多模态模型 | `doubao-seed-2-0-lite-260428` |
| `STORAGE_BACKEND` | json / mysql | `mysql`（容器内） |
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DB` | MySQL 连接 | 容器内覆盖为 `mysql:3306` |
| `COSYVOICE_URL` | TTS 服务 | `http://127.0.0.1:50000` |
| `SMART_CLIP_MCP_URL` | Smart-clip MCP | 容器内 `http://smart-clip-mcp:8000` |
| `WEB_HOST` / `WEB_PORT` | Web 监听 | `0.0.0.0` / `5000`（容器必须 0.0.0.0） |
| `TZ` | 时区 | `Asia/Shanghai` |
| `PIP_INDEX_URL` | pip 镜像源 | 国内可改清华源 |

### 8.5 数据迁移脚本

[scripts/](DouYin_Spider-master/scripts) 提供 3 个迁移脚本：

- [scripts/migrate_json_to_mysql.py](DouYin_Spider-master/scripts/migrate_json_to_mysql.py) — JSON 数据迁移到 MySQL
- [scripts/migrate_media_library.py](DouYin_Spider-master/scripts/migrate_media_library.py) — 素材库迁移
- [scripts/migrate_assign_admin.py](DouYin_Spider-master/scripts/migrate_assign_admin.py) — 指派管理员

---

## 9. 关键调用链

### 9.1 AI 分析链路（视频/脚本/关键词/投流/竞品）

```
Web 请求 → web/<blueprint>.py(c) 路由
        → services/<xxx>.py（业务方法）
        → services/ai_keyword._call_ai        ← 所有 AI 调用统一入口
        → volcenginesdkarkruntime.AsyncArk    ← 真正 SDK
        → AI_MODEL（默认 doubao-seed-2-0-pro-260215，多模态场景用 seed-2-0-lite）
        → _parse_json_response（json-repair 容错）
```

### 9.2 智能混剪链路

```
文案 → services/video_mashup.split_script_to_segments（拆句）
    → services/video_classifier 已分类素材 + 时间线
    → _call_ai 匹配每句最佳片段（精确时间戳）
    → services/tts.CosyVoice 逐句配音（预置/克隆音色）
    → FFmpeg subprocess：按时间戳截取 → 拼接 → 片尾短空隙 → 输出 MP4
```

### 9.3 AI 剪辑方案链路（V2.0 VideoPlan）

```
POST /api/aiclip/plan
  → web/ai_clip.api_aiclip_plan
  → services/video_plan.generate_video_plan_sync
    → 上传视频到 Ark Files API（fps=0.5）
    → wait_for_processing
    → responses.create（model=doubao-seed-2-0-lite-260428）
    → _parse_plan_json（容错 JSON 提取）
  → _save_video_plan 落库 ai_clip_video_plans 表
  → 返回 video_plan_id + video_plan
```

### 9.4 采集链路

```
Web 路由 → dy_apis/douyin_api.<方法>
        →  builder/ 签名（X-Bogus / A-Bogus / msToken）
        → requests.post → 抖音 API
        → utils/data_util.handle_work_info 解析
        → utils/data_util.save_to_xlsx 导出（可选）
```

### 9.5 存储读写链路

```
Web 路由 → services/<业务>.py
        → services/storage 门面（save_one / load_all / ...）
        → SCOPED_ENTITIES 内的实体：自动注入/校验 owner_id
        → STORAGE_BACKEND=mysql → storage_mysql → MySQL
        → STORAGE_BACKEND=json  → storage_json  → datas/app_data/*.json

⚠ intent_analysis / price_research 当前未隔离，全局共享
```

### 9.6 用户上下文注入链路

```
请求到达 → web/__init__.py._load_current_user（before_request）
        → 从 session 取 user_id
        → services/user_auth.get_user(user_id)
        → services/storage.set_current_user(user_id, role)
        → 业务代码调用 storage.save_one / load_all 时自动按 owner_id 过滤
        → web/__init__.py._clear_current_user（teardown_request）
```

---

## 10. 已知技术债与边界

### 10.1 来自 AGENTS.md §8 的已知技术债

1. **直播间实时弹幕 / 私信实时接收未接入 Web 前端** — `dy_live/server.py` 与 `dy_apis/douyin_recv_msg.py` 是独立脚本，需手动指定 `live_id`
2. **`web/` 包 13 个蓝图只有 `.pyc`** — 改动需反编译或通过原仓库源码
3. **`intent_analysis` / `price_research` 未做用户隔离** — 不属于 `SCOPED_ENTITIES`
4. **历史 JSON 数据未迁移 MySQL** — `datas/app_data/*.json` 切换前的遗留，当前不被读取
5. **混剪结果无删除 API** — 只有 `/api/mashup/results` 列表
6. **品牌/竞品/意向/价格无 Excel 导出** — 仅 `/api/analysis/export` 与 `/api/scripts/export`
7. **前端「语速」控件残留** — 后端已固定一倍速合成
8. **弃用资源未清理** — WSL 内 `CosyVoice2-0.5B`（约 7.6GB）、`edge-tts`
9. **`blackboxprotobuf` 与 `volcenginesdkarkruntime` 依赖陷阱** — 见 §7.1

### 10.2 依赖陷阱（动手前必看）

| 陷阱 | 后果 | 绕开方式 |
|------|------|----------|
| `pip install volcenginesdkarkruntime` | 启动即 ImportError（空壳包） | 改装 `volcengine-python-sdk[ark] ≥ 5.0` |
| `pip install blackboxprotobuf` | 强制 protobuf==3.10.0，与 `static/*_pb2.py` 的 5.27.1 gencode 冲突 | `pip install --no-deps blackboxprotobuf` |
| 本机裸跑 `python web_server.py` | `bad magic number` | 必须在容器内运行（Dockerfile 已固定 Python 3.11） |
| 容器内监听 `127.0.0.1` | 宿主机无法访问 | 必须设 `WEB_HOST=0.0.0.0` |
| `docker compose` v2 插件 | 本机不可用 | 必须用 `docker-compose`（连字符）v5.0.2 |

### 10.3 改动入口速查表

| 想做的事 | 改这里 |
|---------|--------|
| 加一个 Web 接口 | `web/<对应蓝图>.pyc`（若有源码）或新建 `web/<新蓝图>.py` + 在 `web/__init__.py` 注册；不要回写到 `web_server.py` |
| 加一个 AI 分析维度 | `services/<对应模块>.py`，提示词用 `.format()` 模板，复用 `ai_keyword._call_ai` + `_parse_json_response` |
| 接入新的 AI 模型 | `services/ai_keyword.py._call_ai`（所有 AI 共享），仅改 `AI_MODEL` 环境变量即可切换 |
| 加一个数据实体 | `services/storage_mysql.py` 建表 + `SCOPED_ENTITIES` 加入（如果需要按用户隔离） |
| 改混剪流程 | `services/video_mashup.py`（拼接）+ `services/tts.py`（配音） |
| 改竞品发现三步评估 | `services/competitor_discovery.py._evaluate_replicability`（阈值常量见 §5.11） |
| 改前端某个面板 | `static/js/app-<面板>.js` + `templates/index.html` |
| 改 Web 启动行为 | `web/context.py.init_app()` + `web_server.py` |
| 加一个漫剧阶段 | `services/comic_designer.py` + `config/comic_design/<新阶段>.md` 模板 |
| 加一个雷达提示词 | `config/ai_analysis_prompt.txt`（在线 `/api/prompts` 可编辑） |
| 部署到 Fly.io | `fly.toml` 已就绪；保证 `WEB_HOST=0.0.0.0`、`fly secrets set ARK_API_KEY=... DY_COOKIES=...` |

### 10.4 沟通与协作约定（来自 AGENTS.md §10）

- 用户偏好**指令式、密度高、可验证**——交付要带"在哪改、改了什么、为什么改、怎么验证"
- 涉及多文件改动时，**先列清单 + 影响面**，再动手
- 任何依赖 / 启动方式 / 部署的变动都同步更新 `README.md` 与 `项目介绍.md`
- 跨多步或 15+ 工具调用完成后，**主动总结为 skill**

### 10.5 反向索引（README 没说但代码里有的事实）

- `web/` 包拆分（路由从 `web_server.py` 拆出，工厂模式 + 17 个 Blueprint）
- `services/comic_designer.py` 是「AI 漫剧设计中心」——三阶段剧本到分镜到 Seedance 2.0 视频提示词工作流
- `web/ai_clip.py` 对接 `smart-clip/` MCP，提供「AI 网感剪辑」路由
- `量化模型/` 目录（宠物趋势预测子模块，`sys.path` 已自动加入，由 [web/context.py](DouYin_Spider-master/web/context.py) 识别）
- 前端 `static/js/` 按面板拆分：`app-brands.js` / `app-discovery.js` / `app-monitor.js` / `app-intent.js` / `app-price-research.js` / `app-comic.js` / `app-campaign.js` / `app-helpers.js` / `app-panels.js` + `tools.js`
- `start_all.bat` 默认 `live_id=432433667143`（在 `dy_live/server.py` 第 178 行）
- `requirements.txt` 中 `pymysql` / `cryptography` / `websocket-client` / `aiohttp` / `selenium` 是后加的关键依赖，原仓库缺失

---

## 附录 A：Web 控制台面板

[templates/index.html](DouYin_Spider-master/templates/index.html) 主控台 7 个面板：

| 面板 | 功能 |
|------|------|
| **品牌管理** | 创建/编辑品牌画像（品类/人群/卖点/调性） |
| **竞品发现** | 同赛道+跨赛道博主发现，一键加入监听 |
| **监听中心** | 查看监听状态，手动触发扫博主/拉视频 |
| **视频分析** | 选择视频 → AI 分析内容结构 → 展示结果 |
| **脚本生成** | 选品牌+已分析视频 → AI 生成参考脚本 |
| **数据看板** | 筛选视频数据，查看播放/点赞/互动率，投流分析 |
| **手动工具** | 搜索采集/用户抓取/直播间/私信等传统爬虫功能 |

按功能 key 划分（来自 [services/user_auth.py](DouYin_Spider-master/services/user_auth.py) `ALL_FEATURES`）：
`discovery / monitor / analysis / scripts / price-research / intent / dashboard / tools-search / tools-user / tools-work / tools-live / tools-message / tools-feed / tools-notice / profile / trendradar / prompts / mashup / comic / ai-clip / materials / campaign`

普通用户默认可见：`discovery / monitor / analysis / scripts / mashup / comic / profile / dashboard / ai-clip`

管理员拥有全部 22 项 + `admin-users` 专属。

## 附录 B：模型 ID 速查

| 模型 ID | 用途 |
|---------|------|
| `doubao-seed-2-0-pro-260215` | 默认文本模型（脚本/关键词/投流/竞品可复制性） |
| `doubao-seed-2-0-lite-260428` | 多模态模型（视频分析/视频分类/VideoPlan 剪辑方案） |

## 附录 C：相关文档索引

| 文档 | 路径 | 用途 |
|------|------|------|
| 项目根 README | [README.md](README.md) | 全链路与启动总览 |
| Agent 工作宪法 | [DouYin_Spider-master/AGENTS.md](DouYin_Spider-master/AGENTS.md) | 改代码前必读 |
| 项目级开发指南 | [DouYin_Spider-master/PROJECT_GUIDE.md](DouYin_Spider-master/PROJECT_GUIDE.md) | 模块/提示词/数据模型详解 |
| 项目介绍 | [DouYin_Spider-master/项目介绍.md](DouYin_Spider-master/项目介绍.md) | 当前开发状态全景 |
| 项目功能介绍 | [DouYin_Spider-master/项目功能介绍.md](DouYin_Spider-master/项目功能介绍.md) | 功能清单 |
| imagedl README | [imagedl/README.md](imagedl/README.md) | 集成位置说明 |
| PolicyPrint README | [PolicyPrint/README.md](PolicyPrint/README.md) | 集成障碍与替代方案 |
| MarketSpider README | [MarketSpider/README.md](MarketSpider/README.md) | 爬虫使用说明 |
| Smart-Clip-MCP pyproject | [Smart-Clip-MCP/pyproject.toml](Smart-Clip-MCP/pyproject.toml) | 依赖与入口 |
| CosyVoice README | [CosyVoice/README.md](CosyVoice/README.md) | 部署方式 |
| remotion-demo package.json | [remotion-demo/package.json](remotion-demo/package.json) | npm 脚本 |
| Dockerfile | [DouYin_Spider-master/Dockerfile](DouYin_Spider-master/Dockerfile) | 容器构建 |
| docker-compose.yml | [DouYin_Spider-master/docker-compose.yml](DouYin_Spider-master/docker-compose.yml) | 服务编排 |
| fly.toml | [DouYin_Spider-master/fly.toml](DouYin_Spider-master/fly.toml) | Fly.io 部署 |

---

_本 Wiki 随项目演进，新增模块 / 新增子系统 / 新增部署目标时，请同步追加对应章节；删除功能时，请同步清理相关条目。_
