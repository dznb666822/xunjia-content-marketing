# 抖音内容运营一体化平台

> 从「竞品数据采集 → AI 内容分析 → 脚本/混剪生产 → 数据看板」的抖音内容运营闭环。

本项目在开源项目 [DouYin_Spider](https://github.com/cv-cat/Douyin_Spider)（抖音数据采集 / 直播间监听 / 私信收发）基础上二次开发，保留原有爬虫能力的同时，新增了品牌管理、竞品发现、AI 视频分析、脚本生成、投流分析、竞品价格调研、意向客户分析、热点雷达、智能混剪（含 TTS 配音）等 AI 增值能力，并提供 Web 控制台（Flask + 原生 JS）。

---

## ✨ 核心功能

### 1. 抖音数据采集
- 关键词搜索（视频 / 用户 / 直播），支持排序、发布时间、时长、搜索范围筛选
- 用户信息、全部作品、粉丝 / 关注列表
- 作品详情（播放、点赞、评论、分享）与评论抓取
- 推荐流、系统通知、批量下载（视频 / 图片）并导出 Excel

### 2. 竞品分析
- **品牌管理**：创建品牌画像（品类 / 目标人群 / 产品描述 / 风格调性 / 卖点）
- **竞品发现**：同赛道三步评估（粉丝量级门槛 → 数据稳定向好 → 内容可复制性 AI 评分）+ 跨赛道推荐
- **竞品价格调研**：淘宝 / 1688 等平台按关键词抓取商品价格，多平台对比，导出 CSV
- **竞品广告分析**：竞品视频投流策略分析

### 3. 监听中心
- 博主监听列表管理，自动拉取监听博主最新视频
- 每日定时调度（10:00 扫描新博主，11:00 监听新视频），支持手动触发

### 4. AI 视频内容分析（多模态）
- 文本结构（钩子 / 正文 / CTA）、视频类型、画面场景、情绪基调
- 产品分析（品类 / 卖点 / 受众 / 痛点）、营销策略、分镜脚本（5–15 个核心分镜）
- 批量分析、历史记录、Excel 导出

### 5. AI 脚本生成
- 基于对标视频结构生成参考脚本（Hook / Body / CTA / 完整脚本）
- 按视频类型生成脚本模板，支持多版本对比与 Excel 导出

### 6. 投流分析
- 基于互动数据 + 内容结构，AI 输出投流建议、预算分配、受众定向、ROI 预测、风险提示

### 7. 数据看板
- 视频互动数据统计（总播放 / 点赞 / 互动率），按品牌 / 博主 / 类型 / 时间筛选
- 趋势折线图与对比柱状图（Chart.js）

### 8. 意向客户分析
- 输入视频链接，AI 抓取评论区并逐条判定「高 / 中 / 低 / 无」购买意向

### 9. 视频智能混剪（含 TTS 配音）
- **素材库**：视频上传、列表、删除
- **AI 智能分类**：标签分类 + 内容时间线片段标注（精确时间戳）
- **文案匹配混剪**：文案逐句语义匹配视频片段 → FFmpeg 按时间戳截取拼接
- **TTS 配音**：CosyVoice 预置多音色 + 上传音频克隆音色
- **镜头-台词对照**：自动生成镜头与台词对照，前端可视化预览

### 10. 热点雷达（TrendRadar）
- 多平台热点聚合（头条 / 百度 / 微博 / 抖音 / 知乎等）
- AI 智能筛选分析，生成 HTML 热点报告，支持定时运行

### 11. 直播间 & 私信管理
- 直播间实时监听（弹幕 / 礼物 / 进场 / 关注 / 点赞 / 热度），发弹幕、点赞
- 私信 WebSocket 实时接收 + 主动发送、会话管理

### 12. 账号与权限管理
- 注册 / 登录 / 登出，管理员按用户分配可用功能，数据按用户隔离

---

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 + Flask + APScheduler |
| 前端 | 原生 HTML / CSS / JavaScript + Chart.js（单页应用） |
| AI 引擎 | 火山方舟 Ark API（豆包 Seed 2.0 多模态 + 文本） |
| TTS | 阿里开源 CosyVoice-300M-SFT（本地部署，HTTP 端口 50000） |
| 数据库 | MySQL（默认，支持 JSON 文件后端切换） |
| 音视频处理 | FFmpeg / FFprobe |
| 爬虫 | 抖音 Web 接口（X-Bogus / A-B / msToken 签名）、Selenium |
| 热点雷达 | 独立子系统 trendradar（RSS 采集 + SQLite + AI 分析 + 通知推送） |

---

## 📁 目录结构

```
DouYin_Spider-master/
├── web_server.py            # Flask 主入口（Web 控制台，端口 5000）
├── main.py                  # 命令行爬虫入口
├── .env / .env.example      # 环境配置（Cookie / MySQL / AI Key 等）
├── templates/               # 前端页面（index.html 主控制台 / setup.html 登录）
├── static/                  # 静态资源（js / css / protobuf）
├── services/                # ★ AI 业务服务层（核心）
│   ├── storage.py           #   存储门面（JSON / MySQL 切换 + 用户隔离）
│   ├── video_analyzer.py    #   视频多模态分析
│   ├── video_classifier.py  #   素材视频分类 + 时间线
│   ├── video_mashup.py      #   智能混剪
│   ├── tts.py               #   CosyVoice TTS 合成 / 克隆
│   ├── script_generator.py  #   AI 脚本生成
│   ├── competitor_discovery.py  # 竞品发现（三步评估）
│   ├── data_collector.py    #   数据采集 + 看板
│   ├── ai_keyword.py        #   AI 关键词 + 跨赛道推荐
│   ├── ad_advisor.py        #   投流分析
│   ├── intent_analyzer.py   #   意向客户分析
│   ├── price_research.py    #   竞品价格调研
│   └── user_auth.py         #   用户认证与权限
├── dy_apis/                 # 抖音 API 封装（搜索 / 用户 / 作品 / 直播 / 私信）
├── dy_live/server.py        # 直播间 WebSocket 监听（独立脚本）
├── builder/                 # 请求签名（auth / header / params / proto）
├── utils/                   # 签名算法 + 工具函数（xbogus / ab / mstoken 等）
├── scheduler/               # APScheduler 定时任务
├── models/                  # dataclass 数据模型
├── trendradar/              # 热点雷达子系统
├── config/                  # AI 提示词 + 配置文件
├── 量化模型/                # 宠物趋势量化预测模型
└── datas/                   # 上传视频、混剪输出、历史 JSON 数据
```

---

## 🚀 快速开始

### 运行环境
- Python 3.11+
- MySQL 8.0+（或切换 JSON 文件后端）
- FFmpeg（混剪 / 视频处理依赖）
- 火山方舟 Ark API Key（AI 功能依赖）

### 安装依赖

```bash
pip install -r requirements.txt
pip install "volcengine-python-sdk[ark]"   # Ark Runtime SDK
```

### 配置环境变量

复制 `.env.example` 为 `.env`，填写以下关键配置：

```env
DY_COOKIES='...'            # 抖音 Cookie（采集认证）
DY_LIVE_COOKIES='...'       # 直播 Cookie（可选）
ARK_API_KEY='...'           # 火山方舟 API Key
AI_API_URL='https://ark.cn-beijing.volces.com/api/v3'
AI_MODEL='doubao-seed-2-0-pro-260215'
STORAGE_BACKEND='mysql'     # json | mysql
MYSQL_HOST='127.0.0.1'
MYSQL_PORT='3306'
MYSQL_USER='root'
MYSQL_PASSWORD=''
MYSQL_DB='douyin_spider'
```

### 启动

```bash
# 主 Web 服务（端口 5000）
python web_server.py
```

浏览器打开 http://127.0.0.1:5000

可选独立脚本：

```bash
# 命令行爬虫
python main.py

# 直播间实时监听（需在 dy_live/server.py 中指定 live_id）
python dy_live/server.py

# 私信实时接收
python dy_apis/douyin_recv_msg.py
```

### TTS 配音（可选）

智能混剪的配音依赖本地 CosyVoice 服务（WSL2，端口 50000），未启动时混剪配音不可用：

```bash
wsl -d Ubuntu-22.04 -u root -- bash -c \
  "cd /root/CosyVoice && /root/cosyvoice_env/bin/python custom_server.py \
   --model_dir /root/CosyVoice/pretrained_models/CosyVoice-300M-SFT --port 50000"
```

---

## 🔌 外部依赖服务

| 服务 | 说明 |
|------|------|
| 火山方舟 Ark | AI 大模型（豆包 Seed 2.0），需 `ARK_API_KEY` |
| CosyVoice | 本地 WSL2 部署，`http://127.0.0.1:50000`，提供预置音色与克隆 |
| MySQL | 数据存储，`127.0.0.1:3306`，库 `douyin_spider` |
| FFmpeg | 视频截取 / 拼接 / 音视频处理 |
| 抖音 Cookie | 采集认证（`DY_COOKIES` 等） |

---

## ⚠️ 免责声明

本项目仅供学习与技术研究使用，严禁用于发布不良信息、违法内容。请遵守相关平台的使用条款与法律法规，使用本项目产生的一切后果由使用者自行承担。

---

## 🙏 致谢

本项目基于开源项目 [DouYin_Spider](https://github.com/cv-cat/Douyin_Spider) 二次开发，感谢原作者的开源贡献。
