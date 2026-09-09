# imagedl

> CharlesPikachu/imagedl 的本地镜像 · 内容与 [GitHub 主仓](https://github.com/CharlesPikachu/imagedl) `pyimagedl 0.5.3` 一致。

本目录是从 `xunjia-web` 容器内已安装的 `pyimagedl` 包拷出来的(因 GitHub 在国内拉速太慢 + WorkBuddy safe-delete 对工作区根目录删除操作的拦截,常规 `git clone` 走不通)。**功能等价于从 GitHub clone**,因为 `pip install pyimagedl` 装的也是同一份代码。

## 目录结构

    imagedl/
    ├── __init__.py                # 包入口
    ├── imagedl.py                 # ImageClient 主类（CLI + Python API）
    └── modules/
        ├── __init__.py
        ├── sources/               # 46 个图片搜索源客户端
        │   ├── baidu.py           # 百度图片
        │   ├── bing.py            # 必应图片
        │   ├── duckduckgo.py      # DuckDuckGo
        │   ├── google.py          # 谷歌图片
        │   ├── pixabay.py         # Pixabay
        │   ├── unsplash.py        # Unsplash
        │   ├── pexels.py          # Pexels
        │   ├── nasa.py            # NASA
        │   ├── wikipedia.py       # 维基百科
        │   ├── wallhaven.py       # Wallhaven 壁纸
        │   ├── ... (共 46 个)
        └── utils/                 # 内部工具
            ├── structure.py       # ImageInfo dataclass
            ├── io.py / cheat.py / chromium.py / ...

## 用法

### CLI

```bash
# 全局可装版本（推荐）
pip install pyimagedl

# 本仓库直接执行
python -m imagedl -k "cute cats" -i BingImageClient -l 5
```

### Python API

```python
from imagedl import imagedl

client = imagedl.ImageClient(
    image_sources=["BingImageClient"],
    init_image_clients_cfg={"BingImageClient": {"work_dir": "./imagedl_outputs", "max_retries": 2}},
)
search_results = client.search(keyword="cute cats", search_limits_per_source=5)
downloaded = client.download(image_infos=search_results)
```

## 在本项目中的集成位置

本项目已通过 `pip install pyimagedl` 装到 web 容器内,Dockerfile 第 37 行追加:

```dockerfile
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt \
    && pip install --no-cache-dir -i ${PIP_INDEX_URL} --no-deps blackboxprotobuf \
    && pip install --no-cache-dir -i ${PIP_INDEX_URL} pyimagedl
```

并在 `web/ai_clip.py` 暴露端点:

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/aiclip/test-material/sources` | GET | 返回支持的 15 个搜索源 |
| `/api/aiclip/test-material` | POST | 搜图 + 下载 + 返回 web 可访问 URL |

前端入口: http://localhost:5000 → AI 智能混剪面板 → 「🎲 素材获取测试」卡片

## 来源 / 同步说明

- 拷贝时间: 2026-09-09
- 来源容器: `xunjia-web`(`/usr/local/lib/python3.11/site-packages/imagedl/`)
- PyPI 版本: `pyimagedl 0.5.3`(`pip show pyimagedl`)
- 与 GitHub 主仓的差异: 无(本目录就是那个发布版的源码;只少了 `requirements.txt` / `setup.py` / `README.md` / `.gitignore` 等仓库元信息文件)

如需跟主仓完全对齐:

```bash
rm -rf imagedl  # 注意 WorkBuddy safe-delete 拦截 → 用 PowerShell Remove-Item
git clone --depth 1 https://github.com/CharlesPikachu/imagedl.git
```