# -*- coding: utf-8 -*-
"""生成宠物趋势预测「算法详解」HTML：数据获取 + 每个子特征公式 + 归一化 + 聚合 + 判定。

读取 _trend_batch_result.json（23 词干净结果），算法讲解部分据 features.py / model.py / output.py 源码还原。
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, '_trend_batch_result.json')
OUT = os.path.join(BASE, '宠物趋势算法详解.html')

with open(SRC, encoding='utf-8') as f:
    results = json.load(f)['results']

WEIGHTS = [
    ('growth_momentum', '增长动能', 0.30, '+', '抖音 + B站'),
    ('audience_quality', '受众质量', 0.30, '+', '抖音 + 淘宝'),
    ('style_migration', '风格迁移', 0.20, '+', 'AI + 知识库'),
    ('feasibility', '可行性', 0.15, '+', '知识库 + 1688'),
    ('noise_decay', '噪声衰减', -0.05, '−', '淘宝 + AI'),
]


def fmt(x):
    return '{:.4f}'.format(x)


def contrib(r):
    gs = r['group_scores']
    return {k: w * float(gs.get(k, 0.5)) for k, _, w, _, _ in WEIGHTS}


# ---- 五因子子特征讲解（据源码硬编码） ----
FACTORS = [
    dict(
        key='growth_momentum', name='增长动能', weight='+0.30', source='抖音 + B站',
        agg='5 个子特征算术平均',
        desc='衡量趋势的“势能”：发布量是否在加速、互动是否超预期、新作者是否涌入、跨平台是否同步升温。',
        subs=[
            ('publish_volume_growth', '发布量环比增速',
             '(近7天发布量 − 前7天发布量) ÷ max(前7天, 1)',
             '抖音 create_time 按近7天 / 8~14天 / 15~30天分桶计数'),
            ('acceleration', '二阶差分加速度',
             '[(近7天 − 前7天) − (前7天 − 更早)] ÷ max(前7天 + 更早, 1)',
             '同上三个时间桶，做两次一阶差'),
            ('interaction_divergence', '互动-发布背离度',
             '互动增速 − 发布增速；互动增速 = (近7天互动 − 前7天互动) ÷ max(前7天互动, 1)',
             '抖音 赞+评+转+藏 四类互动量，按同款时间桶'),
            ('new_author_rate', '新达人入局率',
             '近7天出现的新作者数 ÷ 全部作者数',
             '抖音作者 sec_uid 去重，按作品时间归属'),
            ('cross_platform_heat', '跨平台热度',
             '0.5×数量分 + 0.5×播放分；数量分 = min(条数/20, 1)，播放分 = min(log10(均播放+1)/5, 1)',
             'B站搜索接口 play 字段，对数压平长尾'),
        ],
    ),
    dict(
        key='audience_quality', name='受众质量', weight='+0.30', source='抖音 + 淘宝',
        agg='5 个子特征算术平均',
        desc='衡量“谁在关注、愿不愿意付费”：作者粉丝层级、标题高端词、求购需求密度、淘宝价格带。',
        subs=[
            ('author_tier', '作者粉丝层级',
             '0.5×高粉占比 + 0.5×(均 log10(粉丝+1) ÷ 6)；高粉 = 粉丝 ≥ 1 万',
             '抖音 get_user_info 二次查询真实粉丝数（优先补头部作者，上限 20）'),
            ('high_end_note_ratio', '高客单笔记占比',
             '命中高端词的作品数 ÷ 总作品数',
             '抖音标题命中「高定/定制/轻奢/高端/奢华/重工/手工/原创设计」'),
            ('positive_demand_density', '正向需求密度',
             '命中需求词的作品数 ÷ 总作品数',
             '抖音标题命中「求/想要/哪里买/怎么买/链接/多少钱/蹲/推荐/种草」'),
            ('purchase_intent_density', '购买意向密度',
             '需求占比 × 0.8',
             '同上需求词，乘 0.8 折算为更“硬”的购买信号'),
            ('low_price_ratio_rev', '高价占比（低价反向）',
             '1 − 淘宝低价占比；低价 = 价格 < 100 元',
             '淘宝 item_price 解析为数值后统计 <100 占比'),
        ],
    ),
    dict(
        key='style_migration', name='风格迁移', weight='+0.20', source='AI + 知识库',
        agg='1 个子特征（直接取值）',
        desc='衡量“人类时尚元素能否迁移到高端宠物服饰”，冷启动阶段用 AI 打分 + 静态知识库兜底。',
        subs=[
            ('human_to_pet_score', '人→宠迁移适配度',
             'AI(豆包 Seed 2.0) 输出 0~1；失败时回退静态分 = clamp01(0.3 + 0.35 × min(命中数, 2))',
             'AI 读关键词 + 前5条作品标题打分；静态分用知识库 element_mapping 高适配元素命中数'),
        ],
    ),
    dict(
        key='feasibility', name='可行性', weight='+0.15', source='知识库 + 1688',
        agg='4 个子特征算术平均',
        desc='衡量“能不能做出来、成本扛不扛得住”：面料可采购、工艺难度、成本适配、版型改造。',
        subs=[
            ('fabric_procurement', '面料可采购性',
             '知识库 procurement 映射 {易:1.0, 中:0.7, 难:0.4} 取均值；有 1688 硬数据时覆盖为 0.4 + 0.6×min(去重店铺,30)÷30',
             '知识库面料卡 + 1688 供应商去重店铺数（供应链全局共享）'),
            ('craft_difficulty', '工艺难度',
             'craft 映射 {低:1.0, 中:0.7, 高:0.4} 取均值',
             '知识库面料卡的工艺难度标签'),
            ('cost_fit', '成本适配',
             '0.4 + 0.6 × 高端面料占比',
             '知识库面料卡的 high_end_fit 标记'),
            ('silhouette_adapt', '版型改造',
             '固定 0.7',
             '冷启动阶段静态给中等偏上（人→宠版型可改造性预判）'),
        ],
    ),
    dict(
        key='noise_decay', name='噪声衰减', weight='−0.05', source='淘宝 + AI',
        agg='3 个子特征算术平均',
        desc='负向扣分项：衡量“是不是伪趋势/红海/网红梗”，越吵杂分扣得越多。',
        subs=[
            ('seller_density', '卖家密度（内卷度）',
             '去重店铺数 ÷ 商品数',
             '淘宝 item_shop 去重后与商品数比值'),
            ('low_price_saturation', '低价铺货饱和',
             '价格 < 100 元的占比',
             '淘宝 item_price 解析统计'),
            ('hot_meme_risk', '网红梗/退货风险',
             'AI(豆包) 输出 0~1；失败回退 0.3',
             'AI 评估短期网红梗快速衰退/高退货概率'),
        ],
    ),
]


def render_factors():
    blocks = []
    for f in FACTORS:
        rows = []
        for name, title, formula, source in f['subs']:
            rows.append(
                '<tr><td class="sub-name">{}</td><td class="sub-formula">{}</td><td class="sub-src">{}</td></tr>'.format(
                    title, formula, source))
        blocks.append(
            '<div class="factor">'
            '<div class="f-head"><span class="f-name">{name}</span>'
            '<span class="f-weight">{weight}</span><span class="f-src">{source}</span></div>'
            '<p class="f-desc">{desc}</p>'
            '<div class="f-agg">聚合方式：<b>{agg}</b></div>'
            '<table class="subtable"><thead><tr><th>子特征</th><th>计算公式</th><th>数据来源</th></tr></thead>'
            '<tbody>{rows}</tbody></table></div>'.format(
                name=f['name'], weight=f['weight'], source=f['source'], desc=f['desc'],
                agg=f['agg'], rows=''.join(rows)))
    return ''.join(blocks)


def render_norm():
    return u"""
    <div class="norm-grid">
      <div class="norm"><div class="n-name">clamp01(x)</div><div class="n-f">max(0, min(1, x))</div>
        <div class="n-d">把任意数值截断到 0~1，用于占比、比率、AI 分数等天然有界量的兜底。</div></div>
      <div class="norm"><div class="n-name">growth_norm(g)</div><div class="n-f">clamp01((g + 1) / 2)</div>
        <div class="n-d">把增速 g∈(−∞,+∞) 映射到 0~1：g=0 → 0.5（持平），g>0 → >0.5（增长），g<0 → <0.5（下滑）。</div></div>
      <div class="norm"><div class="n-name">对数压平</div><div class="n-f">log10(x + 1)</div>
        <div class="n-d">播放量/粉丝数跨度极大（几十到几百万），先取对数再归一，避免头部霸榜。</div></div>
    </div>
    """


def render_top_demo():
    r = results[0]
    gs = r['group_scores']
    c = contrib(r)
    rows = []
    for k, name, w, sign, src in WEIGHTS:
        rows.append('<tr><td>{}</td><td class="mono">{:.4f}</td><td class="mono">{} × {:.4f}</td><td class="mono">{}{:.4f}</td></tr>'.format(
            name, float(gs.get(k, 0.5)), sign, w, sign, c[k]))
    total = sum(c.values())
    return r, ''.join(rows), fmt(total)


def render_table():
    rows = []
    for i, r in enumerate(results, 1):
        gs = r['group_scores']
        c = contrib(r)
        ds = r['data_summary']
        detail = ('<tr class="detail"><td colspan="10"><div class="dbox">'
                  '<div class="dgrid"><div><span class="dl">抖音</span>{}</div>'
                  '<div><span class="dl">淘宝</span>{}</div><div><span class="dl">B站</span>{}</div>'
                  '<div><span class="dl">1688</span>{}</div></div><div class="dcal">').format(
            ds.get('douyin_works', 0), ds.get('taobao_products', 0),
            ds.get('bilibili_works', 0), ds.get('suppliers', 0))
        for k, name, w, sign, src in WEIGHTS:
            detail += '<span class="cc">{} {}{:.4f}</span>'.format(name, sign, c[k])
        detail += '<span class="cc total">TrendScore = {}</span></div>'.format(fmt(r['trend_score']))
        risks = ''.join('<li>{}</li>'.format(x) for x in r.get('risks', [])) or '<li>无</li>'
        detail += ('<div class="dmeta"><div><span class="dl">爆发窗口</span>{}</div>'
                   '<div><span class="dl">素材关键词</span>{}</div>'
                   '<div class="risk"><span class="dl">风险</span><ul>{}</ul></div></div></div></td></tr>').format(
            r.get('burst_window', '—'), ' / '.join(r.get('material_keywords', [])[:5]), risks)
        pill = {'萌芽/高潜力早期': 'p-high', '观察期': 'p-watch', '成熟期': 'p-mature', '衰退/伪趋势': 'p-drop'}.get(r['lifecycle'], 'p-watch')
        rows.append('<tr class="main"><td>{}</td><td><b>{}</b></td>'
                    '<td class="mono">{}</td><td class="mono">{}</td><td class="mono">{}</td><td class="mono">{}</td>'
                    '<td class="mono">{}</td><td class="mono score">{}</td><td><span class="pill {}">{}</span></td>'
                    '<td>{}</td></tr>{}'.format(
            i, r['trend_name'], fmt(gs['growth_momentum']), fmt(gs['audience_quality']),
            fmt(gs['style_migration']), fmt(gs['feasibility']), fmt(gs['noise_decay']),
            fmt(r['trend_score']), pill, r['lifecycle'], r.get('action', ''), detail))
    return ''.join(rows)


top, demo_rows, demo_total = render_top_demo()
factor_html = render_factors()
norm_html = render_norm()
table_rows = render_table()

CSS = """
  :root{--bg:#faf6ef;--card:#fff;--ink:#2b2320;--muted:#7a6f66;--brand:#1f3d34;
  --brand-soft:#e8efe9;--gold:#b8860b;--gold-soft:#f5ecd8;--line:#ece4d8;--red:#b3472f;
  --green:#2e7d4f;--blue:#2f5f8f;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  background:var(--bg);color:var(--ink);line-height:1.7;-webkit-font-smoothing:antialiased;}
  .wrap{max-width:1180px;margin:0 auto;padding:40px 24px 90px;}
  .mono{font-family:"SF Mono","Cascadia Code",Consolas,monospace;}
  .hero{background:linear-gradient(135deg,#1f3d34,#2c5447 55%,#3a6a58);color:#fff;border-radius:18px;
  padding:46px 44px;position:relative;overflow:hidden;}
  .hero::after{content:"";position:absolute;right:-70px;top:-70px;width:270px;height:270px;
  background:radial-gradient(circle,rgba(184,134,11,.35),transparent 70%);border-radius:50%;}
  .hero .brand{display:inline-block;font-size:12px;letter-spacing:2px;text-transform:uppercase;
  color:#e8d6a8;border:1px solid rgba(232,214,168,.5);padding:4px 13px;border-radius:999px;margin-bottom:18px;}
  .hero h1{font-size:29px;font-weight:700;margin-bottom:10px;}
  .hero p{color:#d7e4dd;font-size:15px;max-width:700px;}
  section{margin-top:46px;}
  h2{font-size:21px;color:var(--brand);padding-bottom:10px;margin-bottom:20px;border-bottom:2px solid var(--line);
  display:flex;align-items:center;gap:10px;}
  h2 .no{background:var(--brand);color:#fff;width:27px;height:27px;border-radius:8px;display:inline-flex;
  align-items:center;justify-content:center;font-size:13px;flex:none;}
  h3{color:var(--brand);font-size:16px;margin-bottom:10px;}
  .flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;background:var(--card);border:1px solid var(--line);
  border-radius:13px;padding:18px;}
  .flow .box{background:var(--brand-soft);color:var(--brand);padding:8px 14px;border-radius:9px;font-size:13px;font-weight:600;}
  .flow .arrow{color:var(--gold);font-weight:700;}
  .card{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:20px 22px;}
  .plat{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;}
  .plat .p{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:18px;}
  .plat .p .pn{font-weight:700;color:var(--brand);font-size:15px;margin-bottom:6px;}
  .plat .p .pt{font-size:12px;color:var(--gold);font-weight:600;margin-bottom:6px;}
  .plat .p .pd{font-size:13px;color:var(--muted);}
  .plat .p .pf{font-size:12px;color:var(--brand);background:var(--brand-soft);padding:2px 7px;border-radius:5px;
  display:inline-block;margin-top:6px;}
  .norm-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
  .norm{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:16px;}
  .norm .n-name{font-weight:700;color:var(--brand);margin-bottom:6px;}
  .norm .n-f{font-family:Consolas,monospace;color:var(--gold);font-size:14px;margin-bottom:6px;}
  .norm .n-d{font-size:12.5px;color:var(--muted);}
  .factor{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:22px;margin-bottom:20px;}
  .f-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;}
  .f-name{font-size:18px;font-weight:700;color:var(--brand);}
  .f-weight{background:var(--gold-soft);color:var(--gold);font-weight:700;font-size:13px;padding:2px 9px;border-radius:7px;}
  .f-src{color:var(--muted);font-size:13px;}
  .f-desc{color:var(--ink);font-size:13.5px;margin-bottom:8px;}
  .f-agg{font-size:12.5px;color:var(--blue);margin-bottom:12px;}
  .subtable{width:100%;border-collapse:collapse;}
  .subtable th,.subtable td{padding:8px 10px;font-size:13px;border-bottom:1px solid var(--line);text-align:left;
  vertical-align:top;}
  .subtable th{background:var(--brand-soft);color:var(--brand);}
  .sub-name{font-weight:600;white-space:nowrap;}
  .sub-formula{font-family:Consolas,monospace;color:var(--ink);}
  .sub-src{color:var(--muted);}
  .formula-card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--gold);
  border-radius:13px;padding:22px 24px;margin-top:16px;}
  .formula{font-family:Consolas,monospace;font-size:16px;font-weight:600;color:var(--brand);}
  .formula .w{color:var(--gold);}
  .judge{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;}
  .judge .j{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;text-align:center;}
  .judge .j .js{font-family:Consolas,monospace;font-size:17px;font-weight:700;margin-bottom:4px;}
  .judge .j .jl{font-size:13px;font-weight:600;margin-bottom:2px;}
  .judge .j .ja{font-size:12px;color:var(--muted);}
  .demo table{width:100%;border-collapse:collapse;}
  .demo th,.demo td{padding:9px 12px;text-align:left;font-size:14px;border-bottom:1px solid var(--line);}
  .demo th{background:var(--brand-soft);color:var(--brand);}
  .demo .sum td{border-top:2px solid var(--gold);font-weight:700;color:var(--gold);}
  .tablescroll{overflow-x:auto;}
  table.main{width:100%;border-collapse:collapse;background:var(--card);border-radius:13px;overflow:hidden;
  box-shadow:0 4px 18px rgba(43,35,32,.05);}
  table.main th,table.main td{padding:10px 10px;text-align:center;font-size:13px;border-bottom:1px solid var(--line);
  white-space:nowrap;}
  table.main th{background:var(--brand-soft);color:var(--brand);font-weight:700;}
  table.main td:nth-child(2){text-align:left;}
  .score{color:var(--gold);font-weight:700;}
  .pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600;}
  .p-high{background:#e5f2ea;color:var(--green);}.p-watch{background:#f5ecd8;color:var(--gold);}
  .p-mature{background:#e7eef6;color:var(--blue);}.p-drop{background:#f6e4df;color:var(--red);}
  .dbox{text-align:left;background:#faf7f1;border-radius:10px;padding:14px 16px;}
  .dgrid{display:flex;gap:22px;margin-bottom:10px;}.dgrid div{font-size:13px;}
  .dl{color:var(--muted);font-size:12px;margin-right:6px;}
  .dcal{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;}
  .cc{background:var(--brand-soft);color:var(--brand);font-size:12px;padding:3px 8px;border-radius:6px;}
  .cc.total{background:var(--gold-soft);color:var(--gold);font-weight:700;}
  .dmeta{display:flex;flex-direction:column;gap:6px;font-size:13px;}
  .risk ul{margin:4px 0 0 18px;color:var(--red);}
  .footer{margin-top:50px;text-align:center;color:var(--muted);font-size:13px;}
  .note{font-size:12.5px;color:var(--muted);margin-top:8px;}
  @media(max-width:760px){.plat,.norm-grid,.judge{grid-template-columns:1fr;}}
"""

BODY = u"""
<body>
<div class="wrap">

  <div class="hero">
    <span class="brand">Z.paw · Trend Engine · 算法详解</span>
    <h1>宠物服饰趋势预测：从数据采集到分数的每一步</h1>
    <p>完整还原 23 个垂类词的算法链路：数据如何获取、子特征如何计算、如何归一化聚合、如何加权成 TrendScore、如何判定生命周期。所有公式与源码一一对应。</p>
  </div>

  <section>
    <h2><span class="no">1</span>总览：一条完整链路</h2>
    <div class="flow">
      <span class="box">数据采集（抖音/B站/淘宝/1688）</span><span class="arrow">→</span>
      <span class="box">五因子 × 子特征（18 个）</span><span class="arrow">→</span>
      <span class="box">子特征均值 = 分组得分</span><span class="arrow">→</span>
      <span class="box">加权求和 = TrendScore</span><span class="arrow">→</span>
      <span class="box">阈值判定 = 生命周期 + 动作</span>
    </div>
    <div class="formula-card">
      <div class="formula">TrendScore = <span class="w">0.30</span>·增长动能 + <span class="w">0.30</span>·受众质量 + <span class="w">0.20</span>·风格迁移 + <span class="w">0.15</span>·可行性 − <span class="w">0.05</span>·噪声衰减</div>
    </div>
  </section>

  <section>
    <h2><span class="no">2</span>数据如何获取（四平台）</h2>
    <div class="plat">
      <div class="p"><div class="pn">抖音 · 作品 + 作者</div><div class="pt">采集 · dy_apis.douyin_api</div>
        <div class="pd">search_general_work 搜作品，取 desc / create_time / 赞评转藏 / 作者 sec_uid；再对头部作者 get_user_info 补真实粉丝数（上限 20）。</div>
        <span class="pf">频控：单页 3 次退避重试（8/16/24s）+ 整词 0 条再等 30s 重跑</span></div>
      <div class="p"><div class="pn">B站 · 视频热度</div><div class="pt">公开接口 · api.bilibili.com</div>
        <div class="pd">search/type 视频搜索，匿名 + buvid cookie，取 play / danmaku / favorites / like / comment。</div>
        <span class="pf">频控：页间随机 3~6s 延时</span></div>
      <div class="p"><div class="pn">淘宝 · 商品 + 价格带</div><div class="pt">RPA · services.price_research</div>
        <div class="pd">Selenium 非无头浏览器采集，落库 price_research 表（platform=taobao），取 item_price / item_shop / item_name。</div>
        <span class="pf">读表时严格 platform=taobao 过滤（避免混入 1688）</span></div>
      <div class="p"><div class="pn">1688 · 供应商</div><div class="pt">RPA · services.price_research</div>
        <div class="pd">Selenium + 登录 cookie，搜索关键词需 GBK 编码；取商品卡片 innerText + IM 链接 uid 映射公司名。</div>
        <span class="pf">反爬：检测滑块验证（拖动滑块/滑动验证）等人工完成后继续</span></div>
    </div>
  </section>

  <section>
    <h2><span class="no">3</span>归一化工具（计算技巧基础）</h2>
    {norm_html}
  </section>

  <section>
    <h2><span class="no">4</span>五因子 × 子特征（18 个计算公式）</h2>
    {factor_html}
  </section>

  <section>
    <h2><span class="no">5</span>聚合与加权</h2>
    <div class="card">
      <h3>第一步：子特征 → 分组得分（组内算术平均）</h3>
      <div class="formula" style="font-size:14px;">group_score = mean(该因子下所有子特征)</div>
      <p class="note">增长动能/受众质量/可行性/噪声衰减取组内均值；风格迁移只有 1 个子特征，直接取值。这样每个因子得分都在 0~1。</p>
      <h3 style="margin-top:16px;">第二步：分组得分 → TrendScore（加权求和，噪声为负）</h3>
      <div class="formula" style="font-size:14px;">TrendScore = clamp01( Σ weight × group_score )</div>
      <p class="note">噪声衰减是唯一负权重（−0.05），因为它衡量的是内卷/低价/网红梗风险，分数越高反而要扣分。</p>
    </div>
  </section>

  <section>
    <h2><span class="no">6</span>阈值判定与七项输出</h2>
    <div class="judge">
      <div class="j"><div class="js" style="color:#2e7d4f;">&gt; 0.75</div><div class="jl">萌芽 / 高潜力早期</div><div class="ja">优先立项</div></div>
      <div class="j"><div class="js" style="color:#b8860b;">0.55 ~ 0.75</div><div class="jl">观察期</div><div class="ja">小成本素材测试</div></div>
      <div class="j"><div class="js" style="color:#2f5f8f;">0.35 ~ 0.55</div><div class="jl">成熟期</div><div class="ja">谨慎入场</div></div>
      <div class="j"><div class="js" style="color:#b3472f;">&lt; 0.35</div><div class="jl">衰退 / 伪趋势</div><div class="ja">放弃</div></div>
    </div>
    <div class="card" style="margin-top:16px;">
      <h3>爆发窗口（由加速度 + 互动背离度判定）</h3>
      <div class="formula" style="font-size:13px;">accel &gt; 0.6 且 divergence &gt; 0.6 → 未来30天；仅 accel &gt; 0.55 → 30~60天；否则 → 60~90天</div>
      <h3 style="margin-top:14px;">风险提示（噪声因子超阈值触发）</h3>
      <div class="formula" style="font-size:13px;">seller_density&gt;0.6 → 内卷；low_price_saturation&gt;0.6 → 低价；hot_meme_risk&gt;0.6 → 网红梗；douyin&lt;5 → 样本不足</div>
    </div>
  </section>

  <section>
    <h2><span class="no">7</span>完整计算演示（Top1：{top_name}）</h2>
    <div class="card demo">
      <table>
        <thead><tr><th>因子</th><th>分组得分</th><th>权重 × 得分</th><th>贡献值</th></tr></thead>
        <tbody>{demo_rows}<tr class="sum"><td>合计 TrendScore</td><td></td><td></td><td>{demo_total}</td></tr></tbody>
      </table>
      <p class="note">分组得分 = 该因子各子特征的算术平均（见第 4 节）；贡献值 = 权重 × 分组得分；TrendScore = 各贡献值之和（噪声为负）。</p>
    </div>
  </section>

  <section>
    <h2><span class="no">8</span>23 词完整数值表</h2>
    <div class="tablescroll">
      <table class="main">
        <thead><tr><th>#</th><th>关键词</th><th>增长动能</th><th>受众质量</th><th>风格迁移</th><th>可行性</th><th>噪声衰减</th><th>TrendScore</th><th>生命周期</th><th>动作</th></tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
    <p class="note">点击任意行展开该词的「数据源数量 + 加权贡献明细 + 爆发窗口 + 风险 + 素材关键词」。</p>
  </section>

  <div class="footer">Z.paw 宠物趋势预测量化模型 · 阶段一复合加权 · 数据时间 2026-08-16</div>
</div>
<script>
  document.querySelectorAll('table.main tr.main').forEach(function(tr){{
    tr.style.cursor = 'pointer';
    tr.addEventListener('click', function(){{
      var n = tr.nextElementSibling;
      if (n && n.classList.contains('detail')) n.style.display = n.style.display === 'none' ? '' : 'none';
    }});
  }});
  document.querySelectorAll('tr.detail').forEach(function(tr){{ tr.style.display = 'none'; }});
</script>
</body>
"""

body = BODY.format(top_name=top['trend_name'], demo_rows=demo_rows, demo_total=demo_total,
                   table_rows=table_rows, norm_html=norm_html, factor_html=factor_html)

html = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>宠物趋势预测 · 算法详解</title>\n<style>' + CSS + '</style>\n</head>\n' + body + '\n</html>')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print('已生成:', OUT)
print('关键词数:', len(results))
