# -*- coding: utf-8 -*-
"""AI 剪辑 · 竖屏图文卡片渲染（PIL，零 LLM）。

从旧 `web/ai_clip.py` 的 materialize 段搬过来的，**函数体未改动**。
P1 不挂任何路由；它是 P2「参考脚本 · 人看版」需要的渲染能力：

    _split_segments() + _render_material_card()
        → 把一段文本切成若干张 1080×1920 竖屏卡片，用于素材建议 / 缺口的可视化

搬过来而不是删掉的理由：中文字体回退链、逐字换行测量、渐变底、垂直居中防溢出
这几件事都是踩过的坑，重写一遍不划算。
"""
import os
import re

CJK_FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',      # Debian fonts-wqy-zenhei（容器已装）
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    'C:/Windows/Fonts/msyh.ttc',                          # Windows 本地开发
    'C:/Windows/Fonts/simhei.ttf',
]

# 卡片配色：dark(抖音深色大字卡) / news(政务红) / light(浅色商务)
STYLES = {
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


def find_cjk_font():
    """返回第一个存在的中文字体路径；找不到返回 None。"""
    for p in CJK_FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def gradient_bg(width, height, c1, c2):
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


def wrap_text(draw, text, font, max_width):
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


def split_segments(text, max_chars):
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


def render_card(seg_text, idx, total, title, tag, style, width, height, font_path):
    """渲染单张竖屏卡片图，返回 PIL Image（RGB）。"""
    from PIL import ImageDraw, ImageFont  # noqa: F401
    cfg = STYLES.get(style, STYLES['dark'])
    img = gradient_bg(width, height, cfg['bg_top'], cfg['bg_bottom'])
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
    title_lines = wrap_text(draw, (title or '').strip(), title_font, content_w)
    if len(title_lines) > 2:
        title_lines = title_lines[:2]
        title_lines[-1] = title_lines[-1].rstrip() + '…'
    for tl in title_lines:
        draw.text((margin, y), tl, font=title_font, fill=cfg['title'])
        y += title_line_h

    # 标题下装饰线
    y += int(height * 0.012)
    draw.line((margin, y, margin + int(width * 0.26), y),
              fill=cfg['accent'], width=int(height * 0.005))
    y += int(height * 0.036)

    # ---- 正文（自动换行 + 垂直居中，底部防溢出截断） ----
    body_font = ImageFont.truetype(font_path, int(height * 0.026))
    body_line_h = int(height * 0.05)
    body_lines = wrap_text(draw, seg_text, body_font, content_w)
    bottom_limit = height - int(height * 0.12)
    body_top = y
    avail = bottom_limit - body_top
    body_h = len(body_lines) * body_line_h
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
