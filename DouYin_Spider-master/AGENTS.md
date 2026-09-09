# AGENTS.md —— xunjia-content-marketing 项目级 Agent 配置指令

> 适用范围：任何 AI agent 在本项目（抖音内容运营一体化平台 / 爆款工坊）工作时，请先加载并遵守本文件。
> 本文件是 agent 的"工作宪法"——比系统提示词更具体，比 README 更面向"动手改代码"。

---

## 0. 一句话定位

本项目基于开源 [DouYin_Spider](https://github.com/cv-cat/Douyin_Spider) 二次开发，目标是 **从「竞品数据采集 → AI 内容分析 → 脚本/混剪生产 → 数据看板」的抖音内容运营闭环**。所有 AI 能力统一走 **火山方舟 Ark API + 豆包 Seed 2.0**，所有数据走 **MySQL（默认）/ JSON** 双后端门面，所有视频处理依赖 **FFmpeg**。

---

## 1. 角色与边界

你是项目的**主程级协作者**，要：

- **主动读代码再动手**——本项目半数蓝图只有编译产物（`.pyc`），不要在没读源码前猜测 API 形态。
- **保留所有可复用入口**——`services/ai_keyword._call_ai`、`services/storage` 门面、`web/context` 共享状态都是项目"约定俗成"，新增 AI 调用 / 存储读写前必须先复用它们。
- **任何会改变 API/数据契约的改动**先告知影响面，再动手。
- **凡涉及抖音 Cookie、ARK_API_KEY、MySQL 密码**——只读不写，绝不外泄，绝不提交到 git。

你不应做：

- ❌ 伪造 AI 分析结果、伪造看板数据、伪造视频互动数据。
- ❌ 把 `web_server.py` 写回"路由大文件"——本项目已刻意把路由拆分到 `web/*.py(c)`，恢复单文件是技术债倒退。
- ❌ 绕过 `services/storage` 门面直接读 `datas/app_data/*.json`——`STORAGE_BACKEND=mysql` 时该路径不会被读取。
- ❌ 在 `services/storage.py` 之外另起一套用户隔离逻辑——`SCOPED_ENTITIES` + `set_current_user` 是唯一通路。
- ❌ 在根目录直接 `python -m http.server` 或 `flask run` 之外的方式起 Web——会丢失 `web/context.init_app()` 的全局状态注入。

---

## 2. 架构地图（动手前必看）

```
本仓库根（项目根）/
├── web_server.py              # 入口（30 行），仅做：路径注入 + init_app() + app.run()
├── web/                       # ★ Flask Blueprint 路由层（17 个蓝图）
│   ├── __init__.py            #   app 工厂 + register_blueprint + before_request 注入登录上下文
│   ├── context.py             #   共享全局：auth / base_path / daily_monitor / radar 锁
│   ├── ai_clip.py             #   AI 剪辑（Smart-clip MCP）
│   ├── comic.py               #   AI 漫剧（comic_designer）
│   └── *.pyc ×13              #   其余蓝图（ad/analysis/auth/brands/...）编译产物
├── services/                  # ★ AI 业务服务层（核心，17 个模块）
│   ├── storage.py             #   门面：save_all/load_all/save_one/update_one/delete_one/find_by_id/find_by
│   ├── storage_mysql.py       #   MySQL 后端
│   ├── storage_json.py        #   JSON 后端
│   ├── ai_keyword.py          #   ★ 唯一 Ark 调用入口 _call_ai + _build_brand_text（被其他 AI 模块复用）
│   ├── video_analyzer.py      #   多模态视频内容分析（豆包多模态）
│   ├── video_classifier.py    #   素材库分类 + 时间线
│   ├── video_mashup.py        #   智能混剪（FFmpeg + TTS 拼接）
│   ├── tts.py                 #   CosyVoice 预置音色 + 零样本克隆
│   ├── script_generator.py    #   AI 脚本生成（基于视频/基于类型）
│   ├── competitor_discovery.py#   同赛道三步评估 + 跨赛道推荐
│   ├── ad_advisor.py          #   投流分析
│   ├── intent_analyzer.py     #   评论意向分级
│   ├── price_research.py      #   淘宝/1688 价格调研
│   ├── taobao_api.py          #   淘宝 Selenium 抓取
│   ├── data_collector.py      #   数据采集 + 看板
│   ├── user_auth.py           #   用户/权限
│   └── comic_designer.py      #   ★ AI 漫剧设计中心（README 未列，三阶段：美术指导→分镜总导演→Seedance 2.0 视频提示词）
├── dy_apis/                   # 抖音 API 封装（2060 行大头在 douyin_api.py）
├── dy_live/server.py          # 直播间 WebSocket 监听（独立脚本）
├── builder/  utils/           # 抖音签名（X-Bogus/A-B/msToken）
├── scheduler/daily_monitor.py # APScheduler 每日 10:00 扫博主 / 11:00 拉视频
├── models/                    # dataclass：brand / competitor / video / task
├── config/
│   ├── ai_*.txt               # 趋势雷达 AI 提示词（在线可编辑）
│   ├── frequency_words*.txt
│   ├── timeline*.yaml
│   └── comic_design/          # 漫剧三阶段角色提示词模板（用户可改）
├── smart-clip/                # 集成子系统：AI 网感剪辑 MCP server（Docker，8000）
├── cosyvoice/                 # 集成子系统：阿里 TTS（Dockerfile.cpu，50000）
├── trendradar/                # 集成子系统：多平台热点雷达
├── static/js/                 # 前端 SPA（按面板拆分：app-brands.js / app-discovery.js / app-monitor.js / ...）
├── templates/                 # index.html 主控台 / setup.html 凭证设置
├── Dockerfile                 # python:3.11-slim + ffmpeg + 中文字体 + tzdata
├── docker-compose.yml         # mysql:8.0 (3308→3306) + app (5000) + cosyvoice-tts + smart-clip-mcp
├── fly.toml                   # Fly.io 部署配置（sin 区域，512MB）
├── start_all.bat              # Windows 一键起 Web + 直播监听 + 私信接收
└── .env / .env.example        # DY_COOKIES / ARK_API_KEY / MYSQL_* / STORAGE_BACKEND
```

---

## 3. 技术栈与版本锁定

| 层级 | 技术 | 关键版本约束 |
|------|------|------------|
| Python | 3.11 | Dockerfile 已固定 `python:3.11-slim` |
| Web | Flask ≥ 3.0 + flask-cors ≥ 4.0 + werkzeug ≥ 3.0 | Blueprint 模式 |
| 调度 | APScheduler ≥ 3.10 | 跨线程调度 |
| AI SDK | `volcengine-python-sdk[ark] ≥ 5.0` | ⚠ PyPI 上的 `volcenginesdkarkruntime` 是空壳包，不要装 |
| 存储 | MySQL 8.0（默认）或 JSON | `STORAGE_BACKEND=mysql/json` |
| 签名 | protobuf ≥ 5.27.1, < 6.0 | `blackboxprotobuf` 必须 `--no-deps` 安装（会强锁 protobuf==3.10.0） |
| 视频 | FFmpeg（含 ffprobe） | 优先探测 `%LOCALAPPDATA%\ffmpeg\ffmpeg-*\bin\`，降级 PATH |
| TTS | CosyVoice-300M-SFT（WSL2/Docker，端口 50000） | `/inference_sft` 预置音色 / `/inference_zero_shot` 克隆 |
| 雷达 | litellm ≥ 1.40 + ruamel.yaml + json-repair + feedparser | |
| 价格调研 | selenium ≥ 4.15 | 无浏览器时降级但不影响启动 |
| 视频抽帧 | opencv-python-headless ≥ 4.8.0 + numpy | |

⚠ **依赖陷阱**：`volcenginesdkarkruntime` 与 `blackboxprotobuf` 是项目踩过的两个坑——前者导致启动即崩（空包），后者破坏 protobuf 5.x。Dockerfile 已用 `--no-deps` 绕开，但若手动 `pip install` 必须保留这两条注释。

---

## 4. 关键调用链（改功能前先沿链路走一遍）

### 4.1 AI 分析链路（视频/脚本/关键词/投流/竞品）
```
Web 请求 → web/<blueprint>.pyc 路由
        → services/<xxx>.py（业务方法）
        → services/ai_keyword._call_ai        ← 所有 AI 调用的唯一入口
        → volcenginesdkarkruntime.AsyncArk    ← 真正 SDK（不要换 volcenginesdkarkruntime）
        → AI_MODEL（默认 doubao-seed-2-0-pro-260215，多模态场景另用 seed-2-0-lite）
        → _parse_json_response（json-repair 容错，详见 ai_keyword.py）
```

### 4.2 智能混剪链路
```
文案 → services/video_mashup.split_script（拆句）
    → services/video_classifier 已分类素材 + 时间线
    → _call_ai 匹配每句最佳片段（精确时间戳）
    → services/tts.CosyVoice 逐句配音（预置/克隆音色）
    → FFmpeg subprocess：按时间戳截取 → 拼接 → 片尾短空隙 → 输出 MP4
```

### 4.3 采集链路
```
Web 路由 → dy_apis/douyin_api.<方法>  →  builder/ 签名（X-Bogus/A-B/msToken）
                                       →  utils/spider_util 编排
                                       →  utils/data_util.handle_work_info 解析
                                       →  utils/data_util.save_to_xlsx 导出
```

### 4.4 存储读写链路
```
Web 路由 → services/<业务>.py
        → services/storage 门面（save_one / load_all / ...）
        → SCOPED_ENTITIES 内的实体：自动注入/校验 owner_id（brands/competitors/videos/tasks/media_library/mashup_results/comic_designs）
        → STORAGE_BACKEND=mysql → storage_mysql → MySQL
        → STORAGE_BACKEND=json  → storage_json  → datas/app_data/*.json
        ⚠ intent_analysis / price_research 当前未隔离，全局共享
```

---

## 5. AI 提示词维护约定

- 视频分析、脚本生成、关键词、投流、可复制性等**业务提示词**写在 `services/<xxx>.py` 内（与 `_call_ai` 同文件），用 Python `.format()` 模板变量。
- 趋势雷达**提示词**写在 `config/ai_analysis_prompt.txt` / `config/ai_translation_prompt.txt`，Web 端 `/api/prompts` 可在线编辑。
- **漫剧三阶段**角色提示词在 `config/comic_design/`，对应 `services/comic_designer.py` 的 `_load_prompt(filename)`。
- 改提示词后必须验证输出仍是合法 JSON（`_parse_json_response` 已带容错，但模板破洞会拖到运行期才暴露）。

---

## 6. 部署与启动

### 本地直接跑（最快）
```bash
python web_server.py                  # 起 Web（5000）
python dy_live/server.py              # 直播监听（独立脚本，需手动指定 live_id）
python dy_apis/douyin_recv_msg.py     # 私信接收
# 或 Windows 一键
start_all.bat
```

### Docker 编排（推荐）
```bash
docker compose up -d --build
docker compose logs -f app
docker compose down       # 保留数据卷
docker compose down -v    # 清空 MySQL + datas
```

容器网络 `xunjia-net` 内部互访：
- Web → MySQL：`mysql:3306`（已通过 `MYSQL_HOST=mysql` 覆盖 .env）
- Web → CosyVoice：`http://cosyvoice-tts:50000`（已设 `COSYVOICE_URL`）
- Web → Smart-clip：`http://smart-clip-mcp:8000`（已设 `SMART_CLIP_MCP_URL`）

### Fly.io
`fly.toml` 已就绪：`app=xunju`、`primary_region=sin`、`internal_port=5000`、512MB / 1 CPU。注意容器内必须 `WEB_HOST=0.0.0.0`，否则 Fly 探测失败。

---

## 7. 关键环境变量（.env）

| 变量 | 用途 | 默认 |
|------|------|------|
| `DY_COOKIES` | 抖音 Web 采集认证 | 必填，无则搜索/采集全失败 |
| `DY_LIVE_COOKIES` | 直播监听 | 可选 |
| `ARK_API_KEY` | 火山方舟 API Key | 必填，所有 AI 失效 |
| `AI_API_URL` | Ark 入口 | `https://ark.cn-beijing.volces.com/api/v3` |
| `AI_MODEL` | 豆包模型 | `doubao-seed-2-0-pro-260215` |
| `STORAGE_BACKEND` | json / mysql | `mysql` |
| `MYSQL_HOST/PORT/USER/PASSWORD/DB` | MySQL 连接 | 容器内覆盖 `mysql:3306` |
| `COSYVOICE_URL` | TTS 服务地址 | `http://127.0.0.1:50000` |
| `SMART_CLIP_MCP_URL` | Smart-clip MCP | 容器内 `http://smart-clip-mcp:8000` |
| `WEB_HOST` / `WEB_PORT` | Web 监听 | `0.0.0.0` / `5000`（容器必须 0.0.0.0） |
| `TZ` | 时区 | `Asia/Shanghai` |

---

## 8. 已知技术债（不要在不知情时重复造）

来自 `项目介绍.md §7`，按"踩雷风险"排序：

1. **直播间实时弹幕 / 私信实时接收未接入 Web 前端**——`dy_live/server.py` 与 `dy_apis/douyin_recv_msg.py` 是独立脚本，需要手动指定 `live_id`，前端只暴露主动操作。
2. **`web/` 包 13 个蓝图只有 `.pyc`**——做改动要看 `.pyc`（反编译）拿到真实签名；新增蓝图请保持源码形式，不要再造一批 `.pyc`。
3. **`intent_analysis` / `price_research` 未做用户隔离**——不属于 `SCOPED_ENTITIES`，所有登录用户看到同一份数据。
4. **历史 JSON 数据未迁移 MySQL**——`datas/app_data/*.json`、`data/intent_analysis/`、`data/price_research/` 切换前的遗留，当前不被读取。
5. **混剪结果无删除 API**——只有 `/api/mashup/results` 列表，缺 DELETE。
6. **品牌/竞品/意向/价格无 Excel 导出**——仅视频分析 `/api/analysis/export` 与脚本 `/api/scripts/export` 支持导出。
7. **前端"语速"控件残留**——后端已固定一倍速合成，前端选项被忽略。
8. **弃用资源未清理**——WSL 内 `CosyVoice2-0.5B`（约 7.6GB）与 `requirements.txt` 的 `edge-tts` 已废弃。
9. **`blackboxprotobuf` 与 `volcenginesdkarkruntime` 依赖陷阱**——见 §3。

---

## 9. 典型改动入口速查

| 想做的事 | 改这里 |
|---------|--------|
| 加一个 Web 接口 | `web/<对应蓝图>.pyc`（若有源码）or 新建 `web/<新蓝图>.py` + 在 `web/__init__.py` 注册；不要回写到 `web_server.py` |
| 加一个 AI 分析维度 | `services/<对应模块>.py`，提示词用 `.format()` 模板，复用 `ai_keyword._call_ai` + `_parse_json_response` |
| 接入新的 AI 模型 | `services/ai_keyword.py._call_ai`（所有 AI 共享），仅改 `AI_MODEL` 环境变量即可切换 |
| 加一个数据实体 | `services/storage_mysql.py` 建表 + `SCOPED_ENTITIES` 加入（如果需要按用户隔离） |
| 改混剪流程 | `services/video_mashup.py`（拼接）+ `services/tts.py`（配音） |
| 改竞品发现三步评估 | `services/competitor_discovery.py` 的 `_evaluate_replicability`（阈值常量见 `MIN_FOLLOWERS`、`COLD_START_*`、`FOLLOWER_RATIO_MIN/MAX`、`REPLICABILITY_BATCH_SIZE=10`） |
| 改前端某个面板 | `static/js/app-<面板>.js`（brands/discovery/monitor/intent/price-research/comic/helpers/panels）+ `templates/index.html` |
| 改 Web 启动行为 | `web/context.py.init_app()` + `web_server.py` |
| 加一个漫剧阶段 | `services/comic_designer.py` + `config/comic_design/<新阶段>.md` 模板 |
| 加一个雷达提示词 | `config/ai_analysis_prompt.txt`（在线 `/api/prompts` 可编辑） |
| 部署到 Fly.io | `fly.toml` 已就绪；保证 `WEB_HOST=0.0.0.0`、`fly secrets set ARK_API_KEY=... DY_COOKIES=...` |

---

## 10. 沟通与协作约定

- 用户偏好**指令式、密度高、可验证**——交付要带"在哪改、改了什么、为什么改、怎么验证"。
- 涉及多文件改动时，**先列清单 + 影响面**，再动手。
- 任何依赖 / 启动方式 / 部署的变动都同步更新 `README.md` 与 `项目介绍.md`（用户有"交付即文档"的习惯）。
- 每次实质性工作结束，追加一条到 `.workbuddy/memory/YYYY-MM-DD.md`（append-only），长期事实写 `MEMORY.md`。
- 跨多步或 15+ 工具调用完成后，**主动总结为 skill** 写入 `~/.workbuddy/skills/`。

---

## 11. 反向索引：README 没说但代码里有的事实

- `web/` 包拆分（路由从 `web_server.py` 拆出，工厂模式 + 17 个 Blueprint）。
- `services/comic_designer.py` 是"AI 漫剧设计中心"——三阶段剧本到分镜到 Seedance 2.0 视频提示词工作流；提示词模板可由用户在 `config/comic_design/` 自改。
- `web/ai_clip.py` 对接 `smart-clip/` MCP，提供"AI 网感剪辑"路由。
- `quant 模型/` 目录（量化模型预测，`sys.path` 已自动加入）是宠物趋势预测子模块，被 `web/context.py` 识别。
- 前端 `static/js/` 按面板拆分：`app-brands.js / app-discovery.js / app-monitor.js / app-intent.js / app-price-research.js / app-comic.js / app-helpers.js / app-panels.js` + `tools.js`。
- `start_all.bat` 默认 `live_id=432433667143`（在 `dy_live/server.py` 第 178 行）。
- `requirements.txt` 中 `pymysql`、`cryptography`、`websocket-client`、`aiohttp`、`selenium` 是后加的关键依赖，原仓库缺失。

---

_本指令随项目演进：新增模块 / 新增子系统 / 新增部署目标时，请同步追加对应章节；删除功能时，请同步清理本文件的相关条目。_