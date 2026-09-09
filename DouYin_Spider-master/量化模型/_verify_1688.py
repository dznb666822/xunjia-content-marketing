# -*- coding: utf-8 -*-
"""验证 1688 供应商数据质量：item_shop 提取 + 去重供应商数"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(BASE))

from pet_trend.sources import load_1688_suppliers, supplier_procurement

suppliers = load_1688_suppliers()
print('1688 供应商商品总数:', len(suppliers), flush=True)

shops = set()
for p in suppliers:
    name = (p.get('item_name') or '')[:30]
    shop = (p.get('item_shop') or '').strip()
    price = (p.get('item_price') or '').strip()
    if shop:
        shops.add(shop)
    if len(shops) <= 25 and shop:
        print(' - [{:<8}] {:<22} | {}'.format(price, shop[:20], name), flush=True)

print('\n去重供应商(公司)数:', len(shops), flush=True)
print('supplier_procurement 分:', supplier_procurement(suppliers), flush=True)
