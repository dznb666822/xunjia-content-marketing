"""
意向客户分析服务
- 获取视频评论区数据
- 通过 AI 分析每条评论的用户购买意向
- 分类：高意向 / 中意向 / 低意向 / 无
"""
import os
import json
import time
import uuid
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from loguru import logger
from services.storage import save_one, load_all, find_by_id

# 任务状态存储
_lock = threading.Lock()
_tasks = {}
_results = {}


def _get_ai_config():
    """动态读取 AI 配置（每次调用时读取，确保拿到 load_dotenv 后的值）"""
    return {
        'api_url': os.getenv('AI_API_URL', 'https://ark.cn-beijing.volces.com/api/v3'),
        'api_key': os.getenv('AI_API_KEY', ''),
        'model': os.getenv('AI_MODEL', 'doubao-seed-2-0-pro-260215'),
    }


def call_ai(prompt, timeout=120):
    """调用豆包 Seed 2.0 AI API，返回文本内容"""
    cfg = _get_ai_config()
    headers = {
        'Authorization': 'Bearer {}'.format(cfg['api_key']),
        'Content-Type': 'application/json'
    }
    payload = {
        'model': cfg['model'],
        'input': [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
    }
    logger.info('AI 请求: model={}, url={}'.format(cfg['model'], cfg['api_url']))
    resp = requests.post('{}/responses'.format(cfg['api_url']), json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # 解析响应
    output_list = data.get('output', [])
    for item in output_list:
        content_list = item.get('content', [])
        if content_list:
            for c in content_list:
                text = c.get('text', '')
                if text:
                    return text
    # 兜底：reasoning 模型的 summary
    for item in output_list:
        summary_list = item.get('summary', [])
        if summary_list:
            for s in summary_list:
                text = s.get('text', '')
                if text:
                    return text
    logger.warning('AI 返回为空: {}'.format(json.dumps(data, ensure_ascii=False)[:200]))
    return ''


def extract_json(text):
    """从 AI 响应中提取 JSON"""
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)


def _analyze_comments_batch(comments_batch, video_title):
    """AI 分析一批评论的购买意向"""
    if not comments_batch:
        return []

    # 构建评论列表文本
    comments_text = ''
    for i, c in enumerate(comments_batch):
        user = c.get('user', {}).get('nickname', '匿名用户')
        text = c.get('text', '')
        like_count = c.get('digg_count', 0)
        comments_text += f'[{i+1}] 用户:{user} | 点赞:{like_count} | 内容:{text}\n'

    prompt = f"""你是电商运营专家，快速判断每条抖音评论的购买意向。

视频主题：{video_title}

评论列表：
{comments_text}

只输出JSON（不要```标记），每个评论格式：{{"i":序号,"l":"高/中/低/无","r":"一句话理由"}}

标准：
- 高：明确想买、问价格/链接/渠道
- 中：感兴趣、询问效果、考虑入手
- 低：一般好评/提问、围观
- 无：无关、表情、广告"""

    try:
        response = call_ai(prompt, timeout=300)
        if not response:
            raise ValueError('AI 返回空内容')
        data = extract_json(response)
        
        # 兼容两种格式：新紧凑格式 {"i":序号,"l":"等级","r":"理由"} 和旧格式 {"results":[...]}
        if isinstance(data, list):
            raw_results = data
        else:
            raw_results = data.get('results', [])
        
        # 转换为标准结果格式
        results = []
        for item in raw_results:
            idx = item.get('i', item.get('index', len(results) + 1))
            level_map = {'高': '高', '中': '中', '低': '低', '无': '无'}
            level = item.get('l', item.get('intent_level', '低'))
            reason = item.get('r', item.get('reason', ''))
            user = item.get('user', '')
            comment = item.get('comment', '')
            intent_type = item.get('intent_type', '')
            key_points = item.get('key_points', [])
            
            # 如果是从列表索引找回原文
            if not user and isinstance(idx, int) and 1 <= idx <= len(comments_batch):
                orig = comments_batch[idx - 1]
                user = orig.get('user', {}).get('nickname', '匿名用户')
                comment = orig.get('text', '')
            
            results.append({
                'index': idx,
                'user': user,
                'comment': comment,
                'intent_level': level_map.get(level, level),
                'intent_type': intent_type,
                'reason': reason,
                'key_points': key_points
            })
        
        return results
    except Exception as e:
        logger.error(f'AI 批量分析失败: {e}')
        # 返回基础分类，避免全部丢失
        fallback = []
        for c in comments_batch:
            user = c.get('user', {}).get('nickname', '匿名用户')
            text = c.get('text', '')
            fallback.append({
                'index': len(fallback) + 1,
                'user': user,
                'comment': text,
                'intent_level': '未分析',
                'intent_type': 'AI错误',
                'reason': str(e)[:100],
                'key_points': []
            })
        return fallback


def _fetch_comments_with_retry(auth, work_url, max_retries=2, max_comments=100, task_id=None):
    """带重试的评论获取（仅获取一级评论，跳过二级回复以避免API限制）
    限制最大评论数以避免过长的处理时间"""
    from dy_apis.douyin_api import DouyinAPI

    last_error = None
    cursor = "0"
    comment_list = []
    
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.warning('评论获取重试 {}/{}'.format(attempt, max_retries))
                time.sleep(2)
                cursor = "0"
                comment_list = []
            
            while True:
                res_json = DouyinAPI.get_work_out_comment(auth, work_url, cursor)
                comments = res_json.get('comments')
                cursor = str(res_json.get('cursor', 0))
                
                if comments and len(comments) > 0:
                    comment_list.extend(comments)
                
                # 更新任务进度
                if task_id:
                    with _lock:
                        if task_id in _tasks:
                            _tasks[task_id]['message'] = '正在获取评论... {} 条'.format(len(comment_list))
                            _tasks[task_id]['total_comments'] = len(comment_list)
                
                if not comments or len(comments) == 0:
                    break
                if res_json.get('has_more', 0) != 1:
                    break
                if len(comment_list) >= max_comments:
                    logger.info('已达到最大评论数限制 {} 条，停止获取'.format(max_comments))
                    break
            
            logger.info('评论获取完成: 共 {} 条一级评论'.format(len(comment_list)))
            return comment_list
            
        except json.JSONDecodeError as e:
            last_error = e
            logger.error('抖音接口返回非JSON数据 (尝试 {}/{}): {}'.format(attempt + 1, max_retries + 1, str(e)[:100]))
        except Exception as e:
            last_error = e
            logger.error('获取评论异常 (尝试 {}/{}): {}'.format(attempt + 1, max_retries + 1, str(e)[:100]))

    raise Exception('抖音评论接口返回异常（已重试{}次），请检查 Cookie 是否过期。建议：在浏览器重新登录抖音并复制 Cookie 到 .env 的 DY_COOKIES'.format(max_retries))


def _resolve_short_url(url):
    """解析抖音短链接 v.douyin.com/xxx 为完整 douyin.com/video/xxx 格式"""
    if 'v.douyin.com' in url:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
            }
            resp = requests.get(url, headers=headers, allow_redirects=True, verify=False, timeout=15)
            resolved = resp.url
            logger.info('短链接已解析: {} -> {}'.format(url[:40], resolved[:80]))
            return resolved
        except Exception as e:
            logger.warning('短链接解析失败: {}'.format(str(e)))
    return url


def start_intent_analysis(work_url, auth):
    """启动意向分析任务"""
    task_id = 'intent_{}_{}'.format(datetime.now().strftime('%Y%m%d%H%M%S'), str(uuid.uuid4())[:4])

    with _lock:
        _tasks[task_id] = {
            'task_id': task_id,
            'work_url': work_url,
            'status': 'pending',
            'message': '任务已创建',
            'progress': 0,
            'created_at': datetime.now().isoformat(),
            'total_comments': 0,
            'analyzed_count': 0,
            'high_intent': 0,
            'mid_intent': 0,
            'low_intent': 0,
            'no_intent': 0,
            'video_title': '',
        }

    thread = threading.Thread(target=_run_analysis, args=(task_id, work_url, auth), daemon=True)
    thread.start()

    return task_id


def _run_analysis(task_id, work_url, auth):
    """后台执行意向分析"""
    try:
        with _lock:
            _tasks[task_id]['status'] = 'running'
            _tasks[task_id]['message'] = '正在获取评论数据...'

        # 导入 DouyinAPI
        from dy_apis.douyin_api import DouyinAPI

        # 验证 auth
        if auth is None or auth.cookie is None:
            with _lock:
                _tasks[task_id]['status'] = 'failed'
                _tasks[task_id]['message'] = '抖音认证未初始化，请检查 .env 中的 DY_COOKIES 配置'
            return

        # 解析短链接
        resolved_url = _resolve_short_url(work_url)
        if resolved_url != work_url:
            with _lock:
                _tasks[task_id]['work_url'] = resolved_url
                _tasks[task_id]['message'] = '已解析短链接，正在获取评论数据...'

        logger.info('意向分析: task_id={}, work_url={}, cookie_keys={}'.format(
            task_id, resolved_url[:60], list(auth.cookie.keys())[:5] if auth.cookie else 'NONE'))

        # 获取所有评论（带重试）
        try:
            all_comments = _fetch_comments_with_retry(auth, resolved_url, task_id=task_id)
        except Exception as e:
            with _lock:
                _tasks[task_id]['status'] = 'failed'
                _tasks[task_id]['message'] = '获取评论失败: {}'.format(str(e))
            return

        if not all_comments:
            with _lock:
                _tasks[task_id]['status'] = 'completed'
                _tasks[task_id]['message'] = '该视频暂无评论'
                _tasks[task_id]['progress'] = 100
            _results[task_id] = []
            _save_results(task_id, work_url, [], '抖音视频')
            return

        # 提取视频标题
        video_title = '抖音视频'
        try:
            work_info = DouyinAPI.get_work_info(auth, resolved_url)
            if work_info and isinstance(work_info, dict):
                aweme_detail = work_info.get('aweme_detail', work_info)
                video_title = aweme_detail.get('desc', aweme_detail.get('item_title', '抖音视频'))
        except Exception:
            pass

        # 使用一级评论作为分析数据
        flat_comments = all_comments
        total = len(flat_comments)
        logger.info('意向分析: task_id={}, 共{}条一级评论'.format(task_id, total))

        with _lock:
            _tasks[task_id]['total_comments'] = total
            _tasks[task_id]['video_title'] = video_title
            _tasks[task_id]['message'] = '共 {} 条评论，AI 分析中（豆包 Seed 2.0）...'.format(total)

        # 分批分析：每批 25 条（大batch响应慢，小batch效率低，25条最佳平衡）
        batch_size = 25
        all_results = []
        for i in range(0, total, batch_size):
            batch = flat_comments[i:i + batch_size]
            batch_results = _analyze_comments_batch(batch, video_title)
            all_results.extend(batch_results)

            # 更新进度
            analyzed = min(i + batch_size, total)
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size
            pct = int(analyzed / total * 100)
            with _lock:
                if task_id in _tasks:
                    _tasks[task_id]['message'] = 'AI 分析中... 批次{}/{} ({}/{})'.format(batch_num, total_batches, analyzed, total)
                    _tasks[task_id]['progress'] = pct
                    _tasks[task_id]['analyzed_count'] = analyzed

            logger.info('意向分析: task_id={}, 批次{}/{} 完成, 进度 {}/{} ({}%)'.format(
                task_id, batch_num, total_batches, analyzed, total, pct))

        # 统计
        high = sum(1 for r in all_results if r.get('intent_level') == '高')
        mid = sum(1 for r in all_results if r.get('intent_level') == '中')
        low = sum(1 for r in all_results if r.get('intent_level') == '低')
        no = sum(1 for r in all_results if r.get('intent_level') in ('无', '未分析'))

        logger.info('意向分析完成: task_id={}, 高:{}, 中:{}, 低:{}, 无:{}'.format(task_id, high, mid, low, no))

        with _lock:
            _tasks[task_id]['status'] = 'completed'
            _tasks[task_id]['progress'] = 100
            _tasks[task_id]['message'] = '分析完成！高意向:{} 中意向:{} 低意向:{} 无意向:{}'.format(high, mid, low, no)
            _tasks[task_id]['high_intent'] = high
            _tasks[task_id]['mid_intent'] = mid
            _tasks[task_id]['low_intent'] = low
            _tasks[task_id]['no_intent'] = no

        _results[task_id] = all_results
        _save_results(task_id, resolved_url, all_results, video_title)

    except Exception as e:
        logger.error('意向分析任务异常: {}'.format(e))
        import traceback
        traceback.print_exc()
        with _lock:
            _tasks[task_id]['status'] = 'failed'
            _tasks[task_id]['message'] = '分析失败: {}'.format(str(e))


def _save_results(task_id, work_url, results, video_title):
    """保存分析结果到数据库"""
    try:
        summary = {
            'high': sum(1 for r in results if r.get('intent_level') == '高'),
            'mid': sum(1 for r in results if r.get('intent_level') == '中'),
            'low': sum(1 for r in results if r.get('intent_level') == '低'),
            'none': sum(1 for r in results if r.get('intent_level') in ('无', '未分析')),
        }
        now = datetime.now().isoformat()
        save_one('intent_analysis', {
            'id': task_id,
            'work_url': work_url,
            'video_title': video_title if isinstance(video_title, str) else '抖音视频',
            'analyzed_at': now,
            'total': len(results),
            'summary': summary,
            'results': results,
            'created_at': now,
        })
        logger.info('意向分析结果已保存到数据库: {}'.format(task_id))
    except Exception as e:
        logger.error('保存结果失败: {}'.format(e))


def get_task_status(task_id):
    """获取任务状态"""
    with _lock:
        return _tasks.get(task_id, {'status': 'not_found', 'message': '任务不存在'})


def get_task_results(task_id):
    """获取分析结果"""
    return _results.get(task_id, [])


def get_history():
    """获取历史分析记录"""
    records = []
    try:
        for item in load_all('intent_analysis'):
            records.append({
                'task_id': item.get('id', ''),
                'work_url': item.get('work_url', ''),
                'video_title': item.get('video_title', ''),
                'analyzed_at': item.get('analyzed_at', ''),
                'total': item.get('total', 0),
                'summary': item.get('summary', {}),
            })
        records.sort(key=lambda x: x.get('analyzed_at', ''), reverse=True)
    except Exception as e:
        logger.error('获取意向分析历史失败: {}'.format(e))
    return records


def get_history_detail(task_id):
    """获取历史分析详情"""
    try:
        item = find_by_id('intent_analysis', task_id)
        if item is None:
            return None
        return {
            'task_id': item.get('id', task_id),
            'work_url': item.get('work_url', ''),
            'video_title': item.get('video_title', ''),
            'analyzed_at': item.get('analyzed_at', ''),
            'total': item.get('total', 0),
            'summary': item.get('summary', {}),
            'results': item.get('results', []),
        }
    except Exception as e:
        logger.error('读取意向分析结果失败: {}'.format(e))
        return None
