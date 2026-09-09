# -*- coding: utf-8 -*-
"""诊断 1688 搜索页：GBK 编码 + offer-list 结构"""
import os
import sys
import time
import urllib.parse

MARKET = r'c:\Users\33664\Desktop\监听\MarketSpider'
sys.path.insert(0, MARKET)
os.chdir(MARKET)

import Core

ilog = Core.Logger('diag1688')


class Gui:
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


gui = Gui()
driver = Core.BrowserControl('chrome', gui, ilog)
driver.browser.set_page_load_timeout(30)
driver.browser.set_script_timeout(30)

driver.navi_to('https://www.1688.com')
time.sleep(3)
try:
    driver.inject_cookie('1688')
    print('cookie injected ok', flush=True)
except Exception as e:
    print('inject cookie err:', e, flush=True)

kw = '宠物衣服'
kw_enc = urllib.parse.quote(kw, encoding='gbk')
print('GBK 编码:', kw_enc, flush=True)
url = 'https://s.1688.com/selloffer/offer_search.htm?keywords={}&beginPage=1'.format(kw_enc)
driver.browser.execute_script("window.location.href = '{}'".format(url))
time.sleep(15)

# 反爬滑块验证：若出现则等待手动完成
verify_js = """
var sels = ['#baxia-dialog-content','.baxia-dialog','.nc-container','.nc_scale','.nc_iconfont','#nc_1_n1z','[class*="captcha"]','[class*="verify"]','[class*="slider"]'];
for (var i=0;i<sels.length;i++){var els=document.querySelectorAll(sels[i]);for(var j=0;j<els.length;j++){var e=els[j];if(e.offsetParent!==null||e.getClientRects().length>0){return true;}}}
return false;
"""
for _ in range(40):
    try:
        if not driver.browser.execute_script(verify_js):
            break
    except Exception:
        pass
    print('检测到反爬验证滑块，请手动完成拖动...', flush=True)
    time.sleep(3)

print('=== title ===', flush=True)
print(driver.browser.title, flush=True)
print('=== search input value ===', flush=True)
print(driver.browser.execute_script(
    "var el = document.querySelector('input[name=\"keywords\"], input[type=\"text\"]'); return el ? el.value : 'NO INPUT';"), flush=True)
print('=== #sm-offer-list>div count ===', flush=True)
print(driver.browser.execute_script("return document.querySelectorAll('#sm-offer-list>div').length"), flush=True)
print('=== offer links (first 15) ===', flush=True)
print(driver.browser.execute_script("""
    var arr = [];
    var as = document.querySelectorAll('a[href*=\"1688.com\"]');
    for (var i=0;i<as.length;i++){
        var h = as[i].href || '';
        if (h.indexOf('offer') >= 0 || h.indexOf('detail') >= 0) arr.push(h);
        if (arr.length >= 15) break;
    }
    return arr;
"""), flush=True)
print('=== first offer card outerHTML (first 1500) ===', flush=True)
print(driver.browser.execute_script("""
    var el = document.querySelector('#sm-offer-list>div');
    return el ? el.outerHTML.substring(0, 1500) : 'NO #sm-offer-list>div';
"""), flush=True)

print('=== card structure (first 3 product links) ===', flush=True)
print(driver.browser.execute_script("""
var links = document.querySelectorAll('a[href*="detail.m.1688.com/page/index.html"]');
var out = [];
for (var i=0;i<Math.min(3, links.length);i++){
    var a = links[i];
    var chain = [];
    var el = a;
    for (var k=0;k<7;k++){
        chain.push({tag: el.tagName, cls: (typeof el.className==='string'?el.className:'').substring(0,60), len:(el.innerText||'').trim().length, text:(el.innerText||'').trim().substring(0,60)});
        if(!el.parentElement) break;
        el = el.parentElement;
    }
    out.push({href:a.href.substring(0,120), aText:(a.innerText||'').trim().substring(0,60), aTitle:(a.getAttribute('title')||'').substring(0,60), chain:chain});
}
return out;
"""), flush=True)

driver.exit()
print('DIAG_DONE', flush=True)
