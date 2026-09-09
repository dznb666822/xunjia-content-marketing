# -*- coding: utf-8 -*-
"""基于真实淘宝标题 + 豆包 AI，归纳宠物服装细分垂类词库"""
import os
import sys
import json
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from dotenv import load_dotenv
load_dotenv()

from services.storage import load_all

# 1. 读取淘宝商品标题
items = load_all('price_research')
titles = []
for it in items:
    for p in it.get('products', []) or []:
        t = (p.get('item_name') or '').strip()
        if t:
            titles.append(t)
titles = list(dict.fromkeys(titles))
print('去重后标题数:', len(titles), flush=True)

sample = [t[:80] for t in titles[:200]]

# 2. 调豆包
api_url = os.getenv('AI_API_URL', 'https://ark.cn-beijing.volces.com/api/v3')
api_key = os.getenv('AI_API_KEY', '')
model = os.getenv('AI_MODEL', 'doubao-seed-2-0-pro-260215')

prompt = '''你是高端宠物服装品牌"Z.paw"的趋势研究员（客单价1500元，高定宠物穿搭，强调"人类时尚元素→宠物"迁移）。
以下是淘宝真实在售宠物服装商品标题样本，请据此归纳"宠物服装细分垂类词库"。

真实标题样本：
{}

请严格输出一个 JSON 对象（不要 markdown 代码块、不要任何解释），结构：
{{
  "segments": [
    {{"dimension": "品类款式", "keywords": [{{"word": "宠物羽绒马甲", "trend_potential": "高"}}]}},
    {{"dimension": "风格", "keywords": [...]}},
    {{"dimension": "材质工艺", "keywords": [...]}},
    {{"dimension": "犬猫品种", "keywords": [...]}},
    {{"dimension": "场景功能", "keywords": [...]}}
  ]
}}
要求：
1. 每个维度 8~15 个词，词要"具体可搜索"（如"宠物四脚羽绒服""比熊衣服""费尔岛宠物毛衣"），不要"宠物衣服"这类宽泛词。
2. trend_potential 取 高/中/低，依据标题出现频率与高端化潜力判断。
3. 优先体现"人类时尚元素→宠物"的迁移（老钱风、费尔岛、马面裙、小香风、洛丽塔、JK 等）。
'''.format('\n'.join(sample[:120]))

headers = {'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
payload = {'model': model, 'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}]}
r = requests.post(api_url + '/responses', json=payload, headers=headers, timeout=180)
r.raise_for_status()
data = r.json()

text = ''
for item in data.get('output', []):
    for c in item.get('content', []):
        if c.get('text'):
            text += c['text']
if not text:
    for item in data.get('output', []):
        for s in item.get('summary', []):
            text += s.get('text', '')

print('\n=== AI 原始输出（前 2500 字）===', flush=True)
print(text[:2500], flush=True)

# 3. 解析 JSON 并落盘
try:
    t = text.strip()
    if t.startswith('```'):
        t = t.split('```')[1]
        if t.lstrip().startswith('json'):
            t = t.lstrip()[4:]
    parsed = json.loads(t)
    out_path = os.path.join(BASE, '_keyword_research.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    print('\n=== 已保存到', out_path, flush=True)
except Exception as e:
    print('\nJSON 解析失败:', e, flush=True)
