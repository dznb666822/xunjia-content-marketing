"""
淘宝搜索 — Headless Chrome 方案（无可见窗口，纯后台运行）
比原 MarketSpider 方案更轻量，无需 GUI 和交互
"""
import os
import json
import time
import re
import random
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions


class TaobaoSearcher:
    """淘宝商品搜索器（Headless Chrome 版）"""

    TIMEOUT = 20

    def __init__(self, cookie_dir: str = None):
        if cookie_dir is None:
            cookie_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "MarketSpider", "cookie"
            )
        self.cookie_dir = cookie_dir
        self.driver = None

    def _get_chromedriver_path(self):
        """获取 chromedriver 路径"""
        market_dir = os.path.dirname(self.cookie_dir)
        driver_path = os.path.join(market_dir, "chromedriver.exe")
        if os.path.exists(driver_path):
            return driver_path
        return None

    def _init_driver(self):
        """初始化 Headless Chrome（含反检测措施）"""
        options = ChromeOptions()
        options.add_argument("--headless=new")  # 无头模式
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # 反检测措施
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})  # 不加载图片加速

        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        options.add_argument("--user-agent={}".format(user_agent))

        driver_path = self._get_chromedriver_path()
        if driver_path:
            service = ChromeService(executable_path=driver_path)
        else:
            service = ChromeService()

        driver = webdriver.Chrome(service=service, options=options)

        # 隐藏 webdriver 属性
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});
            """}
        )

        return driver

    def _inject_cookies(self):
        """注入 Cookie"""
        cookie_file = os.path.join(self.cookie_dir, "taobao.cookie")
        if not os.path.exists(cookie_file):
            print("[TaobaoAPI] Cookie 文件不存在: {}".format(cookie_file))
            return False

        self.driver.get("https://www.taobao.com")
        time.sleep(1)

        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        injected = 0
        for c in cookies:
            try:
                # Selenium 要求 cookie 的 domain 必须以 . 开头
                cookie_dict = {
                    "name": c.get("name", ""),
                    "value": c.get("value", ""),
                }
                domain = c.get("domain", "")
                if domain and domain.startswith("."):
                    cookie_dict["domain"] = domain
                path = c.get("path", "/")
                if path:
                    cookie_dict["path"] = path
                if c.get("secure"):
                    cookie_dict["secure"] = True
                if c.get("httpOnly"):
                    cookie_dict["httpOnly"] = True
                self.driver.add_cookie(cookie_dict)
                injected += 1
            except Exception:
                pass

        print("[TaobaoAPI] 已注入 {}/{} 条 Cookie".format(injected, len(cookies)))
        return True

    def search(self, keyword: str, page: int = 1, page_size: int = 44) -> Dict:
        """
        搜索淘宝商品

        @param keyword: 搜索关键词
        @param page: 页码（从1开始）
        @param page_size: 每页数量
        @return: {"items": [...], "total_pages": int, "current_page": int, "success": bool}
        """
        try:
            if self.driver is None:
                self.driver = self._init_driver()
                self._inject_cookies()

            offset = (page - 1) * page_size
            url = "https://s.taobao.com/search?q={}&s={}&ie=utf8".format(keyword, offset)
            self.driver.get(url)

            # 等待商品列表渲染
            wait_time = random.uniform(2.5, 4.0)
            time.sleep(wait_time)

            # 检测登录跳转
            current_url = self.driver.current_url
            if "login.taobao.com" in current_url:
                return {
                    "items": [],
                    "total_pages": 0,
                    "current_page": page,
                    "success": False,
                    "error": "Cookie 已过期，需要重新登录"
                }

            # 提取总页数
            total_pages = 1
            try:
                page_text = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#sortBarWrap_right > div > div > div.next-pagination > div > span"
                ).text
                if "/" in page_text:
                    total_pages = int(page_text.split("/").pop())
            except Exception:
                pass

            # 滚动页面以确保全部内容加载
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3)")
            time.sleep(0.5)

            # 提取商品列表
            items = []
            try:
                goods = self.driver.find_elements(
                    By.CSS_SELECTOR, "#content_items_wrapper > div"
                )
                for good in goods:
                    try:
                        name = ""
                        price = ""
                        shop = ""
                        link = ""
                        image = ""
                        payment = ""

                        # 商品链接
                        try:
                            link_el = good.find_element(By.CSS_SELECTOR, "a")
                            link = link_el.get_attribute("href") or ""
                        except Exception:
                            pass

                        # 商品名称
                        try:
                            name_el = good.find_element(
                                By.CSS_SELECTOR,
                                "a > div > div.mainPicAndDesc--Q5PYrWux > div.descWrapper--Ta96FeyX > div > span"
                            )
                            name = name_el.text.strip()
                        except Exception:
                            pass

                        # 价格（合并所有子元素文本）
                        try:
                            price_el = good.find_element(
                                By.CSS_SELECTOR,
                                "a > div > div.mainPicAndDesc--Q5PYrWux > div.priceWrapper--dBtPZ2K1"
                            )
                            raw_price = price_el.text.strip()
                            price = raw_price.replace("\n", "").replace("\r", "")
                        except Exception:
                            pass

                        # 店铺名称（多选择器尝试）
                        shop_selectors = [
                            "a > div > div.shopInfo--Kmh31boz > div.TextAndPic--grkZAtsC > a > div > span.shopNameText--DmtlsDKm",
                            "[class*='shopNameText']",
                            "[class*='shopInfo'] span",
                            "[class*='shopInfo'] a",
                        ]
                        for sel in shop_selectors:
                            try:
                                shop_el = good.find_element(By.CSS_SELECTOR, sel)
                                shop = shop_el.text.strip()
                                if shop:
                                    break
                            except Exception:
                                continue

                        # 图片
                        try:
                            img_el = good.find_element(
                                By.CSS_SELECTOR,
                                "a > div > div.mainPicAndDesc--Q5PYrWux > div.mainPicAdaptWrapper--V_ayd2hD > img"
                            )
                            image = img_el.get_attribute("src") or ""
                        except Exception:
                            pass

                        # 付款人数
                        payment_selectors = [
                            "[class*='payWrapper'] span",
                            "[class*='realSales']",
                            "[class*='saleCount']",
                        ]
                        for sel in payment_selectors:
                            try:
                                pay_el = good.find_element(By.CSS_SELECTOR, sel)
                                payment = pay_el.text.strip()
                                if payment:
                                    break
                            except Exception:
                                continue

                        if name:
                            items.append({
                                "item_name": name[:150],
                                "item_price": price,
                                "item_shop": shop,
                                "item_link": link,
                                "shop_link": "",
                                "item_image": image,
                                "item_payment": payment,
                                "item_rates": "",
                                "page": page,
                            })
                    except Exception:
                        continue
            except Exception:
                pass

            return {
                "items": items,
                "total_pages": min(total_pages, 100),
                "current_page": page,
                "success": True,
            }

        except Exception as e:
            return {
                "items": [],
                "total_pages": 0,
                "current_page": page,
                "success": False,
                "error": str(e)
            }

    def search_multi_pages(
        self, keyword: str, start_page: int = 1, end_page: int = 3, delay: float = 2.0
    ) -> List[Dict]:
        """多页搜索"""
        all_items = []
        for page in range(start_page, end_page + 1):
            result = self.search(keyword, page)
            if not result["success"]:
                if page == start_page:
                    break
                continue
            all_items.extend(result["items"])
            if page < end_page and result["items"]:
                time.sleep(delay)
        return all_items

    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
