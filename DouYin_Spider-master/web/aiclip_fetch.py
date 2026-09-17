# -*- coding: utf-8 -*-
"""AI 剪辑 · 素材获取（外部资源 → 视频可消费素材）。

从旧 `web/ai_clip.py` 拆出来的**独立蓝图**，函数体未改动。
旧文件是 Smart-Clip MCP 的 web 壳，本次重构把 MCP 转发段全部删除，但下面这几个
端点是「素材获取」面板在用的，不能跟着一起消失：

    GET  /api/aiclip/test-material/sources   可抓取的站点清单
    POST /api/aiclip/test-material           imagedl 网络图片抓取
    POST /api/aiclip/test-policyprint        gov.cn 政策文件采集
    POST /api/aiclip/materialize             文本/政策 txt → 竖屏卡片图（Pillow 渲染）

渲染用的 PIL 助手另有一份在 `services/aiclip/card.py`（供 P2 参考脚本复用）。
"""
import json
import os
import re
import threading

import requests
from flask import Blueprint, request, jsonify
from loguru import logger

bp = Blueprint('aiclip_fetch', __name__)

@bp.route('/api/aiclip/test-material/sources', methods=['GET'])
def api_aiclip_test_material_sources():
    """返回支持的素材搜索源（给前端下拉框用）。"""
    return jsonify({'success': True, 'sources': IMAGEDL_SOURCES})


@bp.route('/api/aiclip/test-material', methods=['POST'])
def api_aiclip_test_material():
    """用 imagedl 搜索 + 下载图片素材，返回本地可访问的 URL。

    Body JSON:
        keyword: 必填，搜索关键词
        source: 选填，IMAGEDL_SOURCES 中的 key，默认 BingImageClient
        limit:  选填，下载张数，1-30，默认 6
    """
    data = request.get_json(silent=True) or {}
    keyword = (data.get('keyword') or '').strip()
    source = (data.get('source') or 'BingImageClient').strip()
    try:
        limit = max(1, min(30, int(data.get('limit') or 6)))
    except (TypeError, ValueError):
        limit = 6

    if not keyword:
        return jsonify({'success': False, 'error': '关键词不能为空'}), 400
    if source not in IMAGEDL_SOURCES:
        return jsonify({
            'success': False,
            'error': '不支持的 source: {}'.format(source),
            'available': list(IMAGEDL_SOURCES.keys()),
        }), 400

    # 懒加载 imagedl（避免没装时启动失败）
    try:
        from imagedl import imagedl as _imagedl
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'imagedl 未安装或导入失败: {}'.format(e),
            'hint': 'Dockerfile 已配 pip install pyimagedl，需 rebuild web 镜像',
        }), 500

    # 落盘目录：static/test-materials/（Flask 默认 static 路由可直接访问）
    import uuid as _uuid
    import time as _time
    from datetime import datetime
    safe_kw = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', keyword)[:30] or 'kw'
    sub = '{}_{}'.format(safe_kw, datetime.now().strftime('%H%M%S'))
    out_dir = os.path.join(os.getcwd(), 'static', 'test-materials', sub)
    os.makedirs(out_dir, exist_ok=True)

    started = _time.time()
    try:
        client = _imagedl.ImageClient(
            image_sources=[source],
            init_image_clients_cfg={source: {'work_dir': out_dir, 'max_retries': 2}},
        )
        # 搜 + 下载一气呵成（search_limits_per_source 是 search() 的参数）
        search_results = client.search(keyword=keyword, search_limits_per_source=limit)
        downloaded = client.download(image_infos=search_results)
    except Exception as e:
        logger.error('[imagedl] 搜索/下载失败: {}'.format(e))
        return jsonify({'success': False, 'error': 'imagedl 执行失败: {}'.format(e)}), 500

    # 收集下载结果（ImageInfo 列表）
    items = []
    if downloaded:
        try:
            # downloaded 可能是 list[ImageInfo] 或 dict{source: list}
            flat = downloaded if isinstance(downloaded, list) else []
            if not flat and isinstance(downloaded, dict):
                for v in downloaded.values():
                    if isinstance(v, list):
                        flat.extend(v)
            for it in flat[:limit]:
                # ImageInfo 真实字段：save_path / save_name / download_url / description
                sname = getattr(it, 'save_name', None) or ''
                spath = getattr(it, 'save_path', None) or ''
                if spath and not os.path.isabs(spath):
                    spath = os.path.join(getattr(it, 'work_dir', out_dir) or out_dir, sname)
                if not spath or not os.path.exists(spath):
                    continue
                # 相对 web 路径
                rel = os.path.relpath(spath, os.getcwd()).replace('\\', '/')
                if not rel.startswith('static/'):
                    continue
                items.append({
                    'web_path': '/' + rel,
                    'filename': sname or os.path.basename(spath),
                    'source': getattr(it, 'source', source) or source,
                    'caption': getattr(it, 'description', None) or '',
                    'download_url': getattr(it, 'download_url', None) or '',
                    'size': os.path.getsize(spath) if os.path.exists(spath) else 0,
                })
        except Exception as e:
            logger.warning('[imagedl] 解析下载结果失败: {}'.format(e))

    elapsed = round(_time.time() - started, 2)
    return jsonify({
        'success': True,
        'keyword': keyword,
        'source': source,
        'source_cn': IMAGEDL_SOURCES.get(source, source),
        'limit': limit,
        'count': len(items),
        'elapsed_s': elapsed,
        'items': items,
    })


@bp.route('/api/aiclip/test-policyprint', methods=['POST'])
def api_aiclip_test_policyprint():
    """从 gov.cn 政策首页抓取政策文件（详情页 HTML → 正文 txt），返回本地可访问文件。

    这是 PolicyPrint 的轻量替代：绕开 Selenium/Edge/code-sign 三座大山，
    直接 requests 抓 gov.cn 政策列表页（服务端渲染）+ 详情页正文。

    Body JSON:
        keyword: 选填，标题关键词过滤（为空则不过滤，抓最新）
        limit:  选填，下载条数，1-20，默认 5
    """
    data = request.get_json(silent=True) or {}
    keyword = (data.get('keyword') or '').strip()
    try:
        limit = max(1, min(20, int(data.get('limit') or 5)))
    except (TypeError, ValueError):
        limit = 5

    import time as _time
    from datetime import datetime

    safe_kw = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', keyword)[:30] or 'latest'
    sub = 'pp_{}_{}'.format(safe_kw, datetime.now().strftime('%H%M%S'))
    out_dir = os.path.join(os.getcwd(), 'static', 'policy-docs', sub)
    os.makedirs(out_dir, exist_ok=True)

    started = _time.time()
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    }

    # 1. 抓政策列表页（服务端渲染，无需浏览器）
    list_url = 'https://www.gov.cn/zhengce/'
    try:
        resp = requests.get(list_url, headers=HEADERS, timeout=20)
        resp.encoding = 'utf-8'
        list_html = resp.text
    except Exception as e:
        logger.error('[policyprint] 抓列表页失败: {}'.format(e))
        return jsonify({'success': False, 'error': '抓取政策列表失败: {}'.format(e)}), 500

    # 2. 提取 content_xxx.htm 链接（处理相对路径 + 去重）
    seen = set()
    links = []
    for m in re.finditer(r'href="([^"]*content_\d+\.htm)"', list_html):
        href = m.group(1)
        if href.startswith('./'):
            href = 'https://www.gov.cn/zhengce/' + href[2:]
        elif href.startswith('/'):
            href = 'https://www.gov.cn' + href
        elif not href.startswith('http'):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append(href)

    # 3. 逐条抓详情页 → 标题 + 正文 → 保存 txt
    items = []
    for url in links:
        if len(items) >= limit:
            break
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.encoding = 'utf-8'
            detail = r.text
        except Exception:
            continue

        # 标题（去 _xxx_中国政府网 后缀）
        title = ''
        tm = re.search(r'<title>([^<]*)</title>', detail)
        if tm:
            title = re.sub(r'_[^_]*_中国政府网$', '', tm.group(1).strip())
        if not title:
            continue
        if keyword and keyword not in title:
            continue

        # 正文（pages_content 容器）
        body = ''
        bm = re.search(r'class="[^"]*pages_content[^"]*"[^>]*>(.*?)</div>', detail, re.S)
        if bm:
            body = re.sub(r'<[^>]+>', '', bm.group(1))
            body = body.replace('&nbsp;', ' ').replace('&amp;', '&')
            body = re.sub(r'[ \t]+', ' ', body)
            body = re.sub(r'\n\s*\n+', '\n', body).strip()
        if not body:
            continue

        # 保存为 txt
        safe_title = re.sub(r'[\\/*?:"<>|\n\r\t]', '_', title).strip()[:50] or 'doc'
        fname = '{}.txt'.format(safe_title)
        fpath = os.path.join(out_dir, fname)
        # 同名去重（标题可能重复）
        if os.path.exists(fpath):
            fname = '{}_{}.txt'.format(safe_title, datetime.now().strftime('%H%M%S%f'))
            fpath = os.path.join(out_dir, fname)
        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write('标题：{}\n来源：{}\n\n{}'.format(title, url, body))
        except Exception as e:
            logger.warning('[policyprint] 写文件失败 {}: {}'.format(fname, e))
            continue

        rel = os.path.relpath(fpath, os.getcwd()).replace('\\', '/')
        items.append({
            'title': title,
            'source_url': url,
            'web_path': '/' + rel,
            'filename': fname,
            'size': os.path.getsize(fpath),
            'preview': body[:120],
        })

    elapsed = round(_time.time() - started, 2)
    return jsonify({
        'success': True,
        'keyword': keyword,
        'limit': limit,
        'total_links': len(links),
        'count': len(items),
        'elapsed_s': elapsed,
        'items': items,
    })


# =========================================================================
# 文本 → 图片素材（Materialize）：政策文档 txt → 竖屏卡片图 jpg/png
# =========================================================================

_CJK_FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',      # Debian fonts-wqy-zenhei（容器已装）
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    'C:/Windows/Fonts/msyh.ttc',                          # Windows 本地开发
    'C:/Windows/Fonts/simhei.ttf',
]

# 卡片配色：dark(抖音深色大字卡) / news(政务红) / light(浅色商务)
MATERIALIZE_STYLES = {
    'dark': {
        'bg_top': (15, 23, 42), 'bg_bottom': (30, 41, 59),
        'accent': (56, 189, 248), 'title': (241, 245, 249),
        'body': (203, 213, 225), 'muted': (148, 163, 184),
        'tag_bg': (56, 189, 248), 'tag_fg': (15, 23, 42),
    },
    'news': {
        'bg_top': (127, 29, 29), 'bg_bottom': (185, 28, 28),
        'accent': (253, 230, 138), 'title': (255, 255, 255),
        'body': (254, 226, 226), 'muted': (252, 165, 165),
        'tag_bg': (253, 230, 138), 'tag_fg': (127, 29, 29),
    },
    'light': {
        'bg_top': (248, 250, 252), 'bg_bottom': (226, 232, 240),
        'accent': (37, 99, 235), 'title': (15, 23, 42),
        'body': (51, 65, 85), 'muted': (100, 116, 139),
        'tag_bg': (37, 99, 235), 'tag_fg': (255, 255, 255),
    },
}


def _find_cjk_font():
    """返回第一个存在的中文字体路径；找不到返回 None。"""
    for p in _CJK_FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def _gradient_bg(width, height, c1, c2):
    """竖向上渐变背景（c1 顶部 → c2 底部）。"""
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (width, height))
    d = ImageDraw.Draw(img)
    denom = max(1, height - 1)
    for y in range(height):
        t = y / denom
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        d.line((0, y, width, y), fill=(r, g, b))
    return img


def _wrap_text(draw, text, font, max_width):
    """按字符累积测量宽度，自动换行（中文逐字、英文/数字连排）。"""
    lines = []
    for raw_line in (text or '').split('\n'):
        line = ''
        for ch in raw_line:
            test = line + ch
            if draw.textlength(test, font=font) <= max_width or not line:
                line = test
            else:
                lines.append(line)
                line = ch
        if line:
            lines.append(line)
    return lines


def _split_segments(text, max_chars):
    """把长文本按句子边界切段，每段不超过 max_chars 字。"""
    text = re.sub(r'[ \t]+', ' ', text or '')
    text = re.sub(r'\n\s*\n+', '\n', text).strip()
    sentences = re.split(r'(?<=[。！？!?；;])', text)
    segments = []
    cur = ''
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(cur) + len(s) <= max_chars:
            cur += s
        else:
            if cur:
                segments.append(cur)
            while len(s) > max_chars:
                segments.append(s[:max_chars])
                s = s[max_chars:]
            cur = s
    if cur:
        segments.append(cur)
    return segments or [text[:max_chars]]


def _render_material_card(seg_text, idx, total, title, tag, style, width, height, font_path):
    """渲染单张竖屏卡片图，返回 PIL Image（RGB）。"""
    from PIL import Image, ImageDraw, ImageFont
    cfg = MATERIALIZE_STYLES.get(style, MATERIALIZE_STYLES['dark'])
    img = _gradient_bg(width, height, cfg['bg_top'], cfg['bg_bottom'])
    draw = ImageDraw.Draw(img)

    margin = int(width * 0.09)
    content_w = width - 2 * margin

    # ---- 顶部标签胶囊 ----
    tag_text = (tag or '政策解读').strip() or '政策解读'
    tag_font = ImageFont.truetype(font_path, int(height * 0.026))
    tag_w = int(draw.textlength(tag_text, font=tag_font))
    tag_pad_x = int(height * 0.012)
    tag_h = int(height * 0.048)
    tag_box = (margin, margin, margin + tag_w + 2 * tag_pad_x, margin + tag_h)
    draw.rounded_rectangle(tag_box, radius=int(height * 0.024), fill=cfg['tag_bg'])
    draw.text((margin + tag_pad_x, margin + int(height * 0.008)),
              tag_text, font=tag_font, fill=cfg['tag_fg'])

    y = tag_box[3] + int(height * 0.028)

    # ---- 主标题（最多 2 行，超出省略） ----
    title_font = ImageFont.truetype(font_path, int(height * 0.042))
    title_line_h = int(height * 0.058)
    title_lines = _wrap_text(draw, (title or '').strip(), title_font, content_w)
    if len(title_lines) > 2:
        title_lines = title_lines[:2]
        title_lines[-1] = title_lines[-1].rstrip() + '…'
    for tl in title_lines:
        draw.text((margin, y), tl, font=title_font, fill=cfg['title'])
        y += title_line_h

    # 标题下装饰线
    y += int(height * 0.012)
    draw.line((margin, y, margin + int(width * 0.26), y), fill=cfg['accent'], width=int(height * 0.005))
    y += int(height * 0.036)

    # ---- 正文（自动换行 + 垂直居中，底部防溢出截断） ----
    body_font = ImageFont.truetype(font_path, int(height * 0.026))
    body_line_h = int(height * 0.05)
    body_lines = _wrap_text(draw, seg_text, body_font, content_w)
    bottom_limit = height - int(height * 0.12)
    body_top = y
    avail = bottom_limit - body_top
    body_h = len(body_lines) * body_line_h
    # 短文本时正文垂直居中，避免标题下方大片空白
    y = body_top + int(max(0, (avail - body_h) / 2))
    for bl in body_lines:
        if y + body_line_h > bottom_limit:
            break
        draw.text((margin, y), bl, font=body_font, fill=cfg['body'])
        y += body_line_h

    # ---- 底部页码 + 主色底条 ----
    foot_font = ImageFont.truetype(font_path, int(height * 0.02))
    foot_text = '{}/{}'.format(idx, total)
    fw = int(draw.textlength(foot_text, font=foot_font))
    draw.text((width - margin - fw, height - int(height * 0.07)),
              foot_text, font=foot_font, fill=cfg['muted'])
    draw.rectangle((0, height - int(height * 0.012), width, height), fill=cfg['accent'])

    return img


@bp.route('/api/aiclip/materialize', methods=['POST'])
def api_aiclip_materialize():
    """把文本（政策文档等）渲染成视频剪辑可用的图片素材（jpg/png 竖屏卡片）。

    Body JSON:
        text:      选填，直接给文本内容
        file_path: 选填，容器内 txt 绝对路径 或 /static/... 开头的 web 路径（两者二选一，file_path 优先）
        title:     选填，卡片主标题（缺省从文本首句提取）
        tag:       选填，顶部小标签，默认「政策解读」
        style:     选填，dark / news / light，默认 dark
        width/height: 选填，默认 1080 x 1920（抖音竖屏）
        format:    选填，png / jpg，默认 png
        max_chars: 选填，每张卡最多字数，默认 180
        max_cards: 选填，最多生成张数，默认 12

    响应: success + count + items[{web_path, filename, index, snippet}]
    """
    data = request.get_json(silent=True) or {}

    text = (data.get('text') or '').strip()
    src = (data.get('file_path') or '').strip()
    if src:
        if src.startswith('/static/'):
            src = os.path.join(os.getcwd(), src.lstrip('/').replace('/', os.sep))
        if os.path.isfile(src):
            try:
                with open(src, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read().strip()
            except Exception as e:
                return jsonify({'success': False, 'error': '读取文件失败: {}'.format(e)}), 400
        else:
            return jsonify({'success': False, 'error': '文件不存在: {}'.format(src)}), 400

    if not text:
        return jsonify({'success': False, 'error': '缺少文本内容（text 或 file_path）'}), 400

    title = (data.get('title') or '').strip()
    if not title:
        title = re.split(r'[。！？!?；;\n]', text)[0].strip()[:24]
    tag = (data.get('tag') or '').strip()
    style = (data.get('style') or 'dark').strip()
    if style not in MATERIALIZE_STYLES:
        style = 'dark'
    fmt = (data.get('format') or 'png').strip().lower()
    if fmt not in ('png', 'jpg', 'jpeg'):
        fmt = 'png'
    try:
        width = max(320, min(4096, int(data.get('width') or 1080)))
        height = max(320, min(4096, int(data.get('height') or 1920)))
        max_chars = max(40, min(2000, int(data.get('max_chars') or 180)))
        max_cards = max(1, min(50, int(data.get('max_cards') or 12)))
    except (TypeError, ValueError):
        width, height, max_chars, max_cards = 1080, 1920, 180, 12

    # 懒加载 Pillow（与 imagedl 同理）
    try:
        from PIL import Image  # noqa: F401
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Pillow 未安装或导入失败: {}'.format(e),
            'hint': 'requirements.txt 已含 pillow，需确认容器内已安装',
        }), 500

    font_path = _find_cjk_font()
    if not font_path:
        return jsonify({
            'success': False,
            'error': '容器内未找到中文字体',
            'hint': 'Dockerfile 需 apt 安装 fonts-wqy-zenhei',
        }), 500

    import time as _time
    from datetime import datetime

    safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', title)[:20] or 'doc'
    sub = 'mt_{}_{}'.format(safe_title, datetime.now().strftime('%H%M%S'))
    out_dir = os.path.join(os.getcwd(), 'static', 'material', sub)
    os.makedirs(out_dir, exist_ok=True)

    segments = _split_segments(text, max_chars)[:max_cards]
    total = len(segments)
    started = _time.time()
    items = []
    ext = 'jpg' if fmt in ('jpg', 'jpeg') else 'png'
    save_fmt = 'JPEG' if ext == 'jpg' else 'PNG'
    for i, seg in enumerate(segments, start=1):
        img = _render_material_card(seg, i, total, title, tag, style, width, height, font_path)
        fname = 'card_{:03d}.{}'.format(i, ext)
        fpath = os.path.join(out_dir, fname)
        img.save(fpath, format=save_fmt, quality=95)
        rel = os.path.relpath(fpath, os.getcwd()).replace('\\', '/')
        items.append({
            'web_path': '/' + rel,
            'filename': fname,
            'index': i,
            'snippet': seg[:40],
        })

    elapsed = round(_time.time() - started, 2)
    return jsonify({
        'success': True,
        'title': title,
        'style': style,
        'width': width,
        'height': height,
        'format': ext,
        'count': len(items),
        'elapsed_s': elapsed,
        'items': items,
    })


