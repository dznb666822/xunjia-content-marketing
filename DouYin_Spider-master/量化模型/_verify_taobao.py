# -*- coding: utf-8 -*-
import sys, time, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import price_research

task_id = price_research.start_research('宠物衣服', 'taobao', 1, 1)
print('task_id:', task_id)

status = 'running'
for i in range(40):
    st = price_research.get_task_status(task_id)
    status = st.get('status')
    print('[%d] status=%s progress=%s msg=%s' % (i, status, st.get('progress'), st.get('message')))
    if status in ('completed', 'failed'):
        break
    time.sleep(5)

res = price_research.get_task_results(task_id)
products = res or []
print('products_count:', len(products))
with open('_verify_taobao.json', 'w', encoding='utf-8') as f:
    json.dump({'task_id': task_id, 'status': status, 'count': len(products), 'products': products[:5]}, f, ensure_ascii=False, indent=2)
print('done')
