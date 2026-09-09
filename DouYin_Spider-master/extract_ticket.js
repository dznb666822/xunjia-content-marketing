// ============================================================
// 抖音 bd_ticket_guard 提取脚本
// 使用方法:
//   1. Chrome 打开 https://www.douyin.com 并登录
//   2. F12 → Console
//   3. 粘贴本脚本全部内容，回车运行
//   4. 复制输出的 4 行内容到 .env 文件
// ============================================================

(function() {
    var result = {};

    // 方式1: 从 cookie 中提取 bd_ticket_guard_client_data_v2
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
        var c = cookies[i].trim();
        if (c.startsWith('bd_ticket_guard_client_data_v2=')) {
            try {
                var raw = decodeURIComponent(c.split('=').slice(1).join('='));
                var data = JSON.parse(raw);
                // 搜索深层嵌套中的数据
                function find(obj, key) {
                    if (!obj || typeof obj !== 'object') return null;
                    if (obj[key] !== undefined) return obj[key];
                    for (var k in obj) {
                        var r = find(obj[k], key);
                        if (r !== null) return r;
                    }
                    return null;
                }
                result.ticket = find(data, 'ticket');
                result.ts_sign = find(data, 'ts_sign');
                result.client_cert = find(data, 'client_cert');
                result.private_key = find(data, 'private_key') || find(data, 'ec_privateKey');
            } catch(e) {
                console.log('v2 parse error:', e.message);
            }
            break;
        }
    }

    // 方式2: 如果方式1没找到，尝试拦截 bd_ticket_guard SDK
    if (!result.ticket && window.bytedance && window.bytedance.bdTicketGuard) {
        try {
            var guard = window.bytedance.bdTicketGuard;
            var info = guard.getInfo && guard.getInfo();
            if (info) {
                result.ticket = info.ticket;
                result.ts_sign = info.ts_sign;
            }
        } catch(e) {}
    }

    // 方式3: 从 __security 相关 cookie 尝试
    if (!result.ticket) {
        for (var j = 0; j < cookies.length; j++) {
            var ck = cookies[j].trim();
            if (ck.startsWith('__security_mc_1_s_sdk_sign_data_key_web_protect=')) {
                try {
                    var securityData = decodeURIComponent(ck.split('=').slice(1).join('='));
                    var parsed = JSON.parse(securityData);
                    var deepFind = function(obj, key) {
                        if (!obj || typeof obj !== 'object') return null;
                        if (obj[key] !== undefined) return obj[key];
                        for (var k in obj) {
                            var r = deepFind(obj[k], key);
                            if (r !== null) return r;
                        }
                        return null;
                    };
                    result.ticket = result.ticket || deepFind(parsed, 'ticket');
                    result.private_key = result.private_key || deepFind(parsed, 'ec_privateKey') || deepFind(parsed, 'private_key');
                } catch(e) {}
            }
        }
    }

    // 输出结果
    console.log('\n========== 复制以下内容到 .env 文件 ==========\n');
    console.log('DY_COOKIES=' + document.cookie);
    console.log('');
    if (result.ticket) console.log('DY_TICKET=' + result.ticket);
    else console.log('# DY_TICKET=  (未提取到，可能需要手动从浏览器获取)');
    if (result.ts_sign) console.log('DY_TS_SIGN=' + result.ts_sign);
    else console.log('# DY_TS_SIGN=');
    if (result.client_cert) console.log('DY_CLIENT_CERT=' + result.client_cert);
    else console.log('# DY_CLIENT_CERT=');
    if (result.private_key) console.log('DY_PRIVATE_KEY=' + result.private_key);
    else console.log('# DY_PRIVATE_KEY=');
    console.log('\n================================================\n');

    return result;
})();
