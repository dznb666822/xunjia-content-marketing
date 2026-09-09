# 爆款工坊 · xunjia-content-marketing

> AI 内容生产与品牌增长系统 · 全链路抖音内容营销自动化

## 这是什么

一套围绕「抖音爆款短视频生产」的全链路工具集，从**素材采集 → AI 分析 → 智能剪辑 → 政策文件沉淀**一站式打通。核心服务 `xunjia-web` 把火山方舟豆包多模态、Smart-Clip MCP、CosyVoice TTS、imagedl 等能力编排成一条可发布的成片流水线。

**全链路：** 抖音采集 → 火山方舟 AI 视频分析 → AI 脚本重构 → Smart-Clip MCP AI 智能剪辑 → 输出成片

## 仓库结构

```
xunjuneirongyingxiao-main/
├── DouYin_Spider-master/   # ★ 主入口：xunjia-web (Flask, :5000) - 业务核心
├── Smart-Clip-MCP/          # 第三方依赖：Ambrose1/Smart-Clip-MCP (MCP, SSE, :8000)
├── CosyVoice/               # 第三方依赖：FunAudioLLM/CosyVoice (TTS, :50000)
├── imagedl/                 # 第三方依赖：pyimagedl 0.5.3 - 素材获取（Bing/百度/...)
├── PolicyPrint/             # 第三方依赖：政策文件 PDF 打印（本项目改造为 requests 版）
├── remotion-demo/           # Remotion 视频特效展示（含 ScriptReplica 复刻脚本）
└── MarketSpider/            # 抖音数据采集工具集
```

| 模块 | 类型 | 角色 |
|------|------|------|
| **DouYin_Spider-master** | 项目主代码 | 业务核心：采集 / 分析 / 出方案 / 混剪 / 漫剧 |
| **Smart-Clip-MCP** | 第三方依赖 | 执行层：FFmpeg 智能剪辑 |
| **CosyVoice** | 第三方依赖 | TTS：口播视频配音 |
| **imagedl** | 第三方依赖 | 素材获取：46 个图片源客户端 |
| **PolicyPrint** | 第三方依赖 | 政策文件采集（已改造为容器 requests 版） |
| **remotion-demo** | 项目工具 | Remotion 视频特效演示 |
| **MarketSpider** | 工具集 | 抖音数据采集 |

## 快速启动（Docker）

**完整运行栈**（xunjia-mysql + xunjia-web + smart-clip-mcp + Remotion Studio）：

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

## 关键技术栈

- **后端：** Flask 2.x + Blueprint（web/ai_clip.py 等 20+ 模块）
- **AI 模型：** Doubao 多模态（`doubao-seed-2-0-lite-260428` / `doubao-seed-2-0-pro-260215`），火山方舟 AsyncArk SDK
- **MCP 服务：** FastMCP 4.0.x + SSE 协议
- **数据库：** MySQL 8（`storage_mysql.py` 统一存储层）
- **剪辑引擎：** Smart-Clip MCP（FFmpeg 包装）
- **视频合成：** Remotion（React 视频框架）
- **TTS：** CosyVoice（待 docker 化完成）
- **素材：** imagedl（46 个图片源）+ Pillow（文本→图片素材）

## 核心能力

### 1. AI 智能混剪（核心）

**链路：** 上传视频 → 豆包多模态分析 → VideoPlan JSON → Smart-Clip MCP 执行剪辑

- **出方案**（`POST /api/aiclip/plan`）：多模态直出「剪辑执行级脚本」，含素材清单（A 主口播 / B 动作 / C 对比 / D UI 截图 / E 贴纸）、逐秒时间轴、节奏设计、字幕规范、特效清单
- **执行剪辑**（`POST /api/aiclip/execute`）：方案交给 Smart-Clip MCP 切

### 2. 素材获取（独立面板）

`http://localhost:5000/` → 左导航「创作组」→ **素材获取**

- **网络图片**（imagedl）：Bing / 百度 / DuckDuckGo / Pixabay / Unsplash / Pexels / Bing 壁纸
- **政策文件**（gov.cn）：标题关键词过滤、链接抓取、正文提取
- **文本转图素材**：政策 txt → 竖屏卡片图（深色 / 政务红 / 浅色），可直接当视频画面用

### 3. Remotion 特效演示（remotion-demo）

`ScriptReplica` 组件复刻爆款剪辑脚本可复刻元素（字幕系统 / 浏览器线框 / 画中画 / 对比图 / whip pan / 小红书卡片 / 撕纸边清单页 / vignette 暗角 / 3D 礼物盒 / 橙色弧线标注）。

## 环境约束

- **Docker Compose：** 本机仅 `docker-compose` v5.0.2（连字符），`docker compose` v2 插件不可用
- **Python 版本：** 镜像使用 Python 3.11，本机裸跑会 `bad magic number`，必须在容器内运行
- **跨网络访问：** web 容器用 `host.docker.internal:port` + `extra_hosts` 访问宿主机服务
- **火山方舟账号：** 模型 ID 已写在 `services/video_analyzer.py`，需配置 `ARK_API_KEY` 环境变量

## 已知限制 / 后续路线图

- [ ] CosyVoice Docker 化部署尚未跑通（TTS 服务未启动）
- [ ] Smart-Clip MCP `/health` 路由 404（功能正常，4.0.3 已移除）
- [ ] 出方案→Remotion 自动批量出片链路未打通
- [ ] document_library 表方案待实施

## License

主代码采用项目内业务约定。第三方子项目（Smart-Clip-MCP / CosyVoice / imagedl / PolicyPrint）保留各自原始 LICENSE。