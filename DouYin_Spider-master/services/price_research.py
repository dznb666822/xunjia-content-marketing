# coding=utf-8
"""
竞品价格调研服务
基于 MarketSpider 爬虫引擎，封装为 API 可调用的后台服务
支持平台: taobao / jd / 1688
"""
import os
import sys
import json
import time
import threading
import random
import urllib.parse
from datetime import datetime

# 将 MarketSpider 目录加入 sys.path，以便导入 Core
MARKET_SPIDER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'MarketSpider')
if MARKET_SPIDER_DIR not in sys.path:
    sys.path.insert(0, MARKET_SPIDER_DIR)

from loguru import logger
from services.storage import save_one, load_all, find_by_id

# 调研任务状态存储
_tasks = {}           # {task_id: {status, platform, keyword, created_at, ...}}
_results = {}         # {task_id: [products, ...]}
_lock = threading.Lock()

# 平台配置
PLATFORM_CONFIG = {
    'taobao': {
        'name': '淘宝',
        'search_url': 'https://s.taobao.com/search?page={page}&q={keyword}&tab=all',
        'cookies_file': 'taobao',
        'item_selector': '#content_items_wrapper>div',
        'encoding': 'utf-8',
    },
    'jd': {
        'name': '京东',
        'search_url': 'https://search.jd.com/Search?keyword={keyword}&page={page}',
        'cookies_file': 'jd',
        'item_selector': '#J_goodsList > ul > li',
        'encoding': 'utf-8',
    },
    '1688': {
        'name': '1688',
        'search_url': 'https://s.1688.com/selloffer/offer_search.htm?keywords={keyword}&beginPage={page}',
        'cookies_file': '1688',
        'item_selector': '#sm-offer-list>div',
        'encoding': 'gbk',
    },
}


def _get_config_path():
    """获取 MarketSpider config.json 路径"""
    return os.path.join(MARKET_SPIDER_DIR, 'config.json')


def _get_cookie_dir():
    """获取 MarketSpider cookie 目录路径"""
    return os.path.join(MARKET_SPIDER_DIR, 'cookie')


def _check_environment(platform):
    """检查运行环境：config.json 和 cookie 文件是否存在"""
    config_path = _get_config_path()
    if not os.path.exists(config_path):
        return False, 'MarketSpider config.json 不存在，请先运行 Starter.py 初始化配置'

    cookie_file = os.path.join(_get_cookie_dir(), '{}.cookie'.format(PLATFORM_CONFIG[platform]['cookies_file']))
    if not os.path.exists(cookie_file):
        return False, '平台 {} 的 Cookie 文件不存在，请先运行 GetCookie.py 获取登录凭据'.format(PLATFORM_CONFIG[platform]['name'])

    return True, ''


def _get_browser_type():
    """读取 config.json 中的浏览器类型"""
    try:
        with open(_get_config_path(), 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('browser', 'chrome')
    except Exception:
        return 'chrome'


def start_research(keyword, platform, start_page=1, end_page=3):
    """
    启动价格调研任务（异步执行）

    Args:
        keyword: 搜索关键词
        platform: 平台 (taobao/jd/1688)
        start_page: 起始页码
        end_page: 结束页码

    Returns:
        task_id: 任务ID，用于查询状态和结果
    """
    if platform not in PLATFORM_CONFIG:
        raise ValueError('不支持的平台: {}，可选: {}'.format(platform, list(PLATFORM_CONFIG.keys())))

    task_id = 'pr_{}_{}'.format(datetime.now().strftime('%Y%m%d%H%M%S'), random.randint(1000, 9999))

    with _lock:
        _tasks[task_id] = {
            'status': 'pending',
            'platform': platform,
            'platform_name': PLATFORM_CONFIG[platform]['name'],
            'keyword': keyword,
            'start_page': start_page,
            'end_page': end_page,
            'progress': 0,
            'total_pages': end_page - start_page + 1,
            'completed_pages': 0,
            'products_count': 0,
            'created_at': datetime.now().isoformat(),
            'message': '任务已创建，等待执行...',
        }

    # 在后台线程中执行爬虫
    thread = threading.Thread(
        target=_run_crawl,
        args=(task_id, keyword, platform, start_page, end_page),
        daemon=True
    )
    thread.start()

    return task_id


def _run_crawl(task_id, keyword, platform, start_page, end_page):
    """后台执行爬虫任务（统一使用 Selenium）"""
    # 保存并切换工作目录到 MarketSpider，确保 Core 能正确找到 cookie/ 和 chromedriver
    _prev_cwd = os.getcwd()
    os.chdir(MARKET_SPIDER_DIR)
    try:
        with _lock:
            _tasks[task_id]['status'] = 'running'
            _tasks[task_id]['message'] = '正在初始化浏览器...'

        # 检查环境
        ok, msg = _check_environment(platform)
        if not ok:
            with _lock:
                _tasks[task_id]['status'] = 'failed'
                _tasks[task_id]['message'] = msg
            return

        # 导入 MarketSpider Core
        import Core

        browser_type = _get_browser_type()

        # 创建无 GUI 的日志和浏览器控制
        ilog = Core.Logger(platform)

        class SimpleGui:
            def __init__(self, name):
                self.name = name

            def set_progress(self, done, total=100):
                pass

            def set_status(self, text):
                pass

            def set_text(self, text, color=''):
                pass

            def ui_start(self):
                pass

            def ui_loop(self):
                pass

            def ask_string(self, title, description):
                return ''

            def ask_output_formats(self, default_formats=None):
                return []

        gui = SimpleGui(PLATFORM_CONFIG[platform]['name'])

        try:
            driver = Core.BrowserControl(browser_type, gui, ilog)
            # 设置页面加载超时，防止卡死（淘宝页面较慢，给30秒）
            driver.browser.set_page_load_timeout(30)
            driver.browser.set_script_timeout(30)
        except Exception as e:
            logger.error('浏览器初始化失败: {}'.format(e))
            with _lock:
                _tasks[task_id]['status'] = 'failed'
                _tasks[task_id]['message'] = '浏览器初始化失败: {}'.format(str(e))
            return

        products = []
        try:
            with _lock:
                _tasks[task_id]['message'] = '正在注入 Cookie...'

            cookie_file = PLATFORM_CONFIG[platform]['cookies_file']
            driver.navi_to({
                'taobao': 'https://www.taobao.com',
                'jd': 'https://www.jd.com',
                '1688': 'https://www.1688.com',
            }[platform])

            try:
                driver.inject_cookie(cookie_file)
            except Exception:
                logger.warning('Cookie 注入失败，将尝试无登录状态爬取')

            total_pages = end_page - start_page + 1

            for page_num in range(start_page, end_page + 1):
                with _lock:
                    _tasks[task_id]['message'] = '正在爬取第 {}/{} 页...'.format(
                        page_num - start_page + 1, total_pages)
                    _tasks[task_id]['progress'] = int((page_num - start_page) / total_pages * 100)
                    _tasks[task_id]['completed_pages'] = page_num - start_page

                try:
                    page_products = _crawl_page(driver, platform, keyword, page_num, ilog)
                    products.extend(page_products)
                except Exception as e:
                    logger.error('爬取第{}页失败: {}'.format(page_num, e))
                    continue

                # 频控：加大页面间延时与随机幅度，避免被平台限流/验证码
                delay = random.uniform(8, 25)
                time.sleep(delay)

                with _lock:
                    _tasks[task_id]['completed_pages'] = page_num - start_page + 1
                    _tasks[task_id]['products_count'] = len(products)

            with _lock:
                _results[task_id] = products
                _tasks[task_id]['status'] = 'completed'
                _tasks[task_id]['progress'] = 100
                _tasks[task_id]['products_count'] = len(products)
                _tasks[task_id]['message'] = '爬取完成，共获取 {} 条商品信息'.format(len(products))

            _save_results(task_id, keyword, platform, products)

        finally:
            try:
                driver.exit()
            except Exception:
                pass

    except Exception as e:
        logger.error('爬取任务异常: {}'.format(e))
        import traceback
        traceback.print_exc()
        with _lock:
            _tasks[task_id]['status'] = 'failed'
            _tasks[task_id]['message'] = '爬取失败: {}'.format(str(e))
    finally:
        os.chdir(_prev_cwd)


def _wait_verification(driver, ilog, timeout=120):
    """检测反爬滑块验证，若出现则等待用户手动完成（1688 会弹滑动验证）。"""
    verify_js = """
var sels = ['#baxia-dialog-content','.baxia-dialog','.nc-container','.nc_scale','#nc_1_n1z'];
for (var i=0;i<sels.length;i++){var els=document.querySelectorAll(sels[i]);for(var j=0;j<els.length;j++){var e=els[j];if(e.offsetParent!==null||e.getClientRects().length>0){return true;}}}
var body = document.body;
if (body && (body.innerText.indexOf('拖动滑块') >= 0 || body.innerText.indexOf('请按住滑块') >= 0 || body.innerText.indexOf('滑动验证') >= 0 || body.innerText.indexOf('安全验证') >= 0)) return true;
return false;
"""
    start = time.time()
    warned = False
    while time.time() - start < timeout:
        try:
            found = driver.browser.execute_script(verify_js)
        except Exception:
            found = False
        if not found:
            if warned:
                logger.info('反爬验证已通过，继续采集')
            return
        if not warned:
            logger.warning('检测到反爬验证滑块，请在浏览器中手动完成拖动，脚本将等待...')
            warned = True
        time.sleep(3)
    logger.warning('等待反爬验证超时，继续采集（可能为空结果）')


def _crawl_page(driver, platform, keyword, page_num, ilog):
    """爬取单页商品数据"""
    config = PLATFORM_CONFIG[platform]
    kw_encoded = urllib.parse.quote(keyword, encoding=config.get('encoding', 'utf-8'))

    if platform == 'jd':
        # 京东每页需翻2次
        actual_page = 2 * page_num - 1
        url = config['search_url'].format(keyword=kw_encoded, page=actual_page)
    else:
        url = config['search_url'].format(keyword=kw_encoded, page=page_num)

    # 使用 execute_script 导航，绕过 page_load_timeout 限制
    driver.browser.execute_script("window.location.href = '{}'".format(url))
    # 等待页面开始渲染（不等待完全加载）；频控：加大跳转等待
    time.sleep(random.uniform(5, 12))

    if platform == '1688':
        _wait_verification(driver, ilog)

    products = []

    if platform == 'taobao':
        # 淘宝 SPA 页面渲染慢，多等一会再滚动（频控：加大等待与滚动间隔）
        time.sleep(random.uniform(8, 18))
        # 滚动页面触发懒加载
        for _ in range(12):
            driver.browser.execute_script("window.scrollBy(0, 500)")
            time.sleep(random.uniform(0.8, 2.5))
        time.sleep(random.uniform(1, 3))

        # 使用 JavaScript 提取数据，不依赖 CSS class 名
        raw_products = driver.browser.execute_script("""
            var results = [];
            // 先尝试标准选择器
            var items = document.querySelectorAll('#content_items_wrapper > div');
            // 如果标准选择器没找到，尝试从链接中找
            if (items.length === 0) {
                var allLinks = document.querySelectorAll('a[href*="item.taobao.com"], a[href*="detail.tmall.com"]');
                allLinks.forEach(function(a) {
                    var el = a.closest('div[class]') || a.parentElement;
                    if (el) {
                        var text = (el.innerText || '').trim();
                        if (text && text.length > 5) {
                            parseItem(a.href, text, el);
                        }
                    }
                });
            } else {
                items.forEach(function(el) {
                    var a = el.querySelector('a[href*="item"]') || el.querySelector('a');
                    if (!a) return;
                    var text = (el.innerText || '').trim();
                    if (text && text.length > 2) {
                        parseItem(a.href, text, el);
                    }
                });
            }

            function parseItem(link, text, el) {
                try {
                    var lines = text.split('\\n').filter(function(l) { return l.trim(); });
                    var name = lines[0] || '';
                    var price = '';
                    var payment = '';
                    var shop = '';
                    for (var i = 0; i < lines.length; i++) {
                        if (lines[i].indexOf('¥') >= 0 || lines[i].indexOf('\\uffe5') >= 0) {
                            // 价格可能分两行（¥在一行，数字在下一行）
                            var priceSplit = (lines[i] === '¥' || lines[i] === '\\uffe5');
                            price = lines[i];
                            if (priceSplit && i + 1 < lines.length) {
                                price += lines[i+1];
                            }
                        }
                        // 付款人数（含"人付款"或"人已买"）
                        if (lines[i].indexOf('人付款') >= 0 || lines[i].indexOf('人已买') >= 0 || lines[i].indexOf('人收货') >= 0) {
                            payment = lines[i];
                        }
                    }
                    if (lines.length > 1) shop = lines[lines.length - 1];
                    var img = el.querySelector('img');
                    var image = img ? (img.src || img.getAttribute('data-src') || '') : '';
                    if (name && name.length > 1) {
                        results.push({
                            name: name.substring(0, 100),
                            price: price,
                            payment: payment,
                            shop: shop,
                            link: link,
                            image: image
                        });
                    }
                } catch(e) {}
            }
            return results;
        """)

        for item in raw_products:
            products.append({
                'item_name': item.get('name', ''),
                'item_price': item.get('price', ''),
                'item_shop': item.get('shop', ''),
                'item_link': item.get('link', ''),
                'item_image': item.get('image', ''),
                'item_payment': item.get('payment', ''),
                'shop_link': '',
                'item_rates': '-',
                'page': page_num,
            })

    elif platform == 'jd':
        items = driver.browser.find_elements('css selector', config['item_selector'])
        for item in items:
            try:
                link_el = item.find_element('css selector', 'div > div.p-img > a')
                name_el = item.find_element('css selector', 'div > div.p-name > a > em')
                price_el = item.find_element('css selector', 'div > div.p-price > strong > i')
                shop_el = item.find_element('css selector', 'div > div.p-shop > span > a')
                rates_el = item.find_element('css selector', 'div > div.p-commit > strong > a')

                products.append({
                    'item_name': name_el.text.strip()[:100] if name_el else '',
                    'item_price': price_el.text.strip() if price_el else '',
                    'item_shop': shop_el.text.strip() if shop_el else '',
                    'item_link': link_el.get_attribute('href') if link_el else '',
                    'shop_link': shop_el.get_attribute('href') if shop_el else '',
                    'item_image': '',
                    'item_rates': rates_el.text.strip() if rates_el else '-',
                    'page': page_num,
                })
            except Exception:
                continue

    elif platform == '1688':
        # 1688 新版搜索页：商品卡片本身就是 <a class="offerCard">（href 含 detail.m.1688.com），
        # 直接取卡片自身 innerText；公司名从 air.1688.com 即时通讯链接的 uid 参数读取（UTF-8）。
        raw_products = driver.browser.execute_script("""
            var results = [];
            var seenOffer = {};
            function extractOfferId(link) {
                var m = link.match(/offerId=(\\d+)/);
                if (m) return m[1];
                var m2 = link.match(/offerdetail\\/(\\d+)\\.html/);
                if (m2) return m2[1];
                var m3 = link.match(/offer\\/(\\d+)\\.html/);
                if (m3) return m3[1];
                return link;
            }
            function getParam(link, key) {
                var m = link.match(new RegExp('[?&]' + key + '=([^&]+)'));
                return m ? m[1] : '';
            }
            function isPriceToken(s) {
                if (!s) return false;
                var hasDigit = false;
                for (var i = 0; i < s.length; i++) {
                    var c = s.charAt(i);
                    if (c >= '0' && c <= '9') { hasDigit = true; }
                    else if (c !== '.' && c !== ',') { return false; }
                }
                return hasDigit;
            }
            // 1) 建立 offerId -> 公司名 映射（来自 IM 链接 uid 参数）
            var companyMap = {};
            var imLinks = document.querySelectorAll('a[href*="air.1688.com"]');
            for (var i = 0; i < imLinks.length; i++) {
                var h = imLinks[i].href || '';
                var oid = extractOfferId(h);
                var uid = getParam(h, 'uid');
                if (oid && uid && !companyMap[oid]) {
                    try { uid = decodeURIComponent(uid); } catch(e) {}
                    companyMap[oid] = uid;
                }
            }
            // 2) 商品卡片：取卡片自身 innerText，避免向上走到整个列表容器
            var links = document.querySelectorAll('a[href*="detail.m.1688.com/page/index.html"]');
            for (var j = 0; j < links.length; j++) {
                var a = links[j];
                var href = a.href || '';
                var oid = extractOfferId(href);
                if (seenOffer[oid]) continue;
                seenOffer[oid] = 1;
                var text = (a.innerText || '').trim();
                if (!text || text.length < 2) continue;
                var lines = text.split('\\n').map(function(l){ return l.trim(); }).filter(function(l){ return l.length; });
                if (!lines.length) continue;
                var name = lines[0];
                if (name === '广告' || name.indexOf('广告') === 0) continue;
                var price = '';
                for (var k = 0; k < lines.length; k++) {
                    var lk = lines[k];
                    if (lk === '¥' || lk === '￥' || lk.indexOf('¥') === 0 || lk.indexOf('￥') === 0) {
                        var num = '';
                        for (var t = k + 1; t < lines.length && t < k + 5; t++) {
                            if (isPriceToken(lines[t])) { num += lines[t]; }
                            else { break; }
                        }
                        if (num) { price = '¥' + num; }
                        break;
                    }
                }
                var shop = companyMap[oid] || '';
                if (!shop) {
                    for (var m = 0; m < lines.length; m++) {
                        if (lines[m].indexOf('公司') >= 0 || lines[m].indexOf('厂') >= 0) { shop = lines[m]; break; }
                    }
                }
                if (!shop && lines.length > 1) { shop = lines[lines.length - 1]; }
                var img = a.querySelector('img');
                var image = img ? (img.src || img.getAttribute('data-src') || '') : '';
                results.push({name: name.substring(0, 100), price: price, shop: shop, link: href, image: image});
            }
            return results;
        """)
        for item in raw_products:
            products.append({
                'item_name': item.get('name', ''),
                'item_price': item.get('price', ''),
                'item_shop': item.get('shop', ''),
                'item_link': item.get('link', ''),
                'item_image': item.get('image', ''),
                'item_payment': '',
                'shop_link': '',
                'item_rates': '-',
                'page': page_num,
            })

    return products


def _save_results(task_id, keyword, platform, products):
    """将调研结果保存到数据库"""
    try:
        save_one('price_research', {
            'id': task_id,
            'keyword': keyword,
            'platform': platform,
            'platform_name': PLATFORM_CONFIG.get(platform, {}).get('name', platform),
            'products_count': len(products),
            'created_at': datetime.now().isoformat(),
            'products': products,
        })
        logger.info('调研结果已保存到数据库: {}'.format(task_id))
    except Exception as e:
        logger.error('保存结果失败: {}'.format(e))


def get_task_status(task_id):
    """获取调研任务状态"""
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            return None
        return dict(task)


def get_task_results(task_id):
    """获取调研结果"""
    with _lock:
        results = _results.get(task_id, [])
        return list(results)


def get_pending_tasks():
    """获取所有待执行/运行中的任务"""
    with _lock:
        return {
            tid: dict(t) for tid, t in _tasks.items()
            if t['status'] in ('pending', 'running')
        }


def get_history(limit=50):
    """获取历史调研记录"""
    history = []
    try:
        items = load_all('price_research')
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        for item in items[:limit]:
            history.append({
                'task_id': item.get('id', ''),
                'keyword': item.get('keyword', ''),
                'platform': item.get('platform', ''),
                'platform_name': item.get('platform_name', ''),
                'products_count': item.get('products_count', 0),
                'created_at': item.get('created_at', ''),
                'file': item.get('id', ''),
            })
    except Exception as e:
        logger.error('获取调研历史失败: {}'.format(e))

    return history


def get_history_result(task_id):
    """根据任务ID获取详细调研结果"""
    try:
        item = find_by_id('price_research', task_id)
        if item is None:
            return None
        return {
            'task_id': item.get('id', task_id),
            'keyword': item.get('keyword', ''),
            'platform': item.get('platform', ''),
            'platform_name': item.get('platform_name', ''),
            'products_count': item.get('products_count', 0),
            'created_at': item.get('created_at', ''),
            'products': item.get('products', []),
        }
    except Exception as e:
        logger.error('读取调研结果失败: {}'.format(e))
        return None
