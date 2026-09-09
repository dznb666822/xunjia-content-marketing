// ==================== Price Research Section ====================
var currentResearchTaskId = null;
var pollingTimer = null;

// 平台名称映射
var platformNames = {
    'taobao': '淘宝',
    'jd': '京东',
    '1688': '1688'
};

// ==================== 启动价格调研 ====================
function startPriceResearch() {
    var keyword = getVal('pr-keyword');
    var platform = getVal('pr-platform');
    var startPage = parseInt(getVal('pr-start-page')) || 1;
    var endPage = parseInt(getVal('pr-end-page')) || 3;

    if (!keyword) { showToast('请输入搜索关键词', 'error'); return; }
    if (!platform) { showToast('请选择平台', 'error'); return; }
    if (startPage < 1 || endPage < startPage) { showToast('页码范围无效', 'error'); return; }

    spinner('spinner-pr', true);
    fetch('/api/price-research/search', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            keyword: keyword,
            platform: platform,
            start_page: startPage,
            end_page: endPage
        })
    })
    .then(function(resp) { return resp.json(); })
    .then(function(json) {
        spinner('spinner-pr', false);
        if (json.success) {
            currentResearchTaskId = json.data.task_id;
            showToast('调研任务已启动: ' + json.data.message, 'success');
            pollTaskStatus();
        } else {
            showToast('启动失败: ' + (json.error || '未知错误'), 'error');
        }
    })
    .catch(function(e) {
        spinner('spinner-pr', false);
        showToast('请求失败: ' + e.message, 'error');
    });
}

// ==================== 轮询任务状态 ====================
function pollTaskStatus() {
    if (!currentResearchTaskId) return;

    // 清除之前的轮询
    if (pollingTimer) clearInterval(pollingTimer);

    pollTaskStatusOnce();

    pollingTimer = setInterval(function() {
        pollTaskStatusOnce();
    }, 3000);
}

function pollTaskStatusOnce() {
    if (!currentResearchTaskId) {
        if (pollingTimer) clearInterval(pollingTimer);
        return;
    }

    fetch('/api/price-research/status/' + currentResearchTaskId)
        .then(function(resp) { return resp.json(); })
        .then(function(json) {
            if (!json.success) return;

            var task = json.data;
            updateProgressUI(task);

            if (task.status === 'completed') {
                if (pollingTimer) clearInterval(pollingTimer);
                showToast('调研完成！共获取 ' + (task.products_count || 0) + ' 条商品', 'success');
                loadResearchResults(currentResearchTaskId);
                loadResearchHistory();
            } else if (task.status === 'failed') {
                if (pollingTimer) clearInterval(pollingTimer);
                showToast('调研失败: ' + (task.message || '未知错误'), 'error');
                updateProgressUI(task);
            }
        })
        .catch(function() {});
}

function updateProgressUI(task) {
    var progressContainer = document.getElementById('pr-progress');
    var progressBar = document.getElementById('pr-progress-bar');
    var progressText = document.getElementById('pr-progress-text');

    if (!progressContainer) return;

    if (task.status === 'running') {
        progressContainer.style.display = 'block';
        var pct = task.progress || 0;
        progressBar.style.width = pct + '%';
        progressText.textContent = (task.message || '正在爬取...') + ' (' + (task.completed_pages || 0) + '/' + (task.total_pages || 0) + ' 页)';
    } else if (task.status === 'completed') {
        progressBar.style.width = '100%';
        progressText.textContent = '完成 - 共 ' + (task.products_count || 0) + ' 条商品';
        setTimeout(function() {
            progressContainer.style.display = 'none';
        }, 3000);
    } else if (task.status === 'failed') {
        progressBar.style.width = '100%';
        progressBar.style.background = 'var(--color-error)';
        progressText.textContent = '失败: ' + (task.message || '');
    } else if (task.status === 'pending') {
        progressContainer.style.display = 'block';
        progressBar.style.width = '5%';
        progressText.textContent = task.message || '等待执行...';
    }
}

// ==================== 加载调研结果 ====================
function loadResearchResults(taskId) {
    var container = document.getElementById('pr-results');
    if (!container) return;

    container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-hint);">加载中...</div>';

    fetch('/api/price-research/results/' + taskId)
        .then(function(resp) { return resp.json(); })
        .then(function(json) {
            if (!json.success) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
                return;
            }
            var products = json.data.products || [];
            renderProductsTable(container, products);
        })
        .catch(function(e) {
            container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败: ' + e.message + '</div>';
        });
}

function renderProductsTable(container, products) {
    if (!products || products.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">暂无商品数据</div>';
        return;
    }

    var html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">';
    html += '<span style="font-size:12px;color:var(--text-hint);">共 <b style="color:var(--text-primary);">' + products.length + '</b> 条商品</span>';
    html += '<button class="btn btn-secondary btn-xs" onclick="exportPriceResults()">导出 CSV</button>';
    html += '</div>';

    html += '<div style="max-height:500px;overflow-y:auto;">';
    html += '<table style="width:100%;border-collapse:collapse;">';
    html += '<thead><tr>';
    html += '<th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);">商品名称</th>';
    html += '<th style="text-align:right;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);width:100px;">价格</th>';
    html += '<th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);width:120px;">店铺</th>';
    html += '<th style="text-align:center;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);width:60px;">操作</th>';
    html += '</tr></thead><tbody>';

    for (var i = 0; i < products.length; i++) {
        var p = products[i];
        var name = escapeHtml((p.item_name || '--').substring(0, 60));
        var price = escapeHtml(p.item_price || '--');
        var shop = escapeHtml((p.item_shop || '--').substring(0, 20));
        var link = p.item_link || '';

        html += '<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">';
        html += '<td style="padding:6px 10px;font-size:12px;">';
        if (link) {
            html += '<a href="' + escapeHtml(link) + '" target="_blank" style="color:var(--color-accent-text);text-decoration:none;" onmouseover="this.style.textDecoration=\'underline\'" onmouseout="this.style.textDecoration=\'none\'">' + name + '</a>';
        } else {
            html += name;
        }
        html += '</td>';
        html += '<td style="text-align:right;padding:6px 10px;font-size:12px;color:var(--color-error-text);font-weight:500;">' + price + '</td>';
        html += '<td style="padding:6px 10px;font-size:11px;color:var(--text-hint);">' + shop + '</td>';
        html += '<td style="text-align:center;padding:6px 10px;">';
        if (link) {
            html += '<a href="' + escapeHtml(link) + '" target="_blank" style="font-size:12px;color:var(--color-accent);">查看</a>';
        } else {
            html += '<span style="font-size:12px;color:var(--text-dim);">--</span>';
        }
        html += '</td>';
        html += '</tr>';
    }

    html += '</tbody></table></div>';
    container.innerHTML = html;

    // 保存当前结果供导出使用
    window._currentPriceResults = products;
    window._currentPriceKeyword = '';
}

function exportPriceResults() {
    var products = window._currentPriceResults || [];
    if (products.length === 0) {
        showToast('没有可导出的数据', 'error');
        return;
    }

    var csvContent = '\uFEFF商品名称,价格,店铺,商品链接\n';
    for (var i = 0; i < products.length; i++) {
        var p = products[i];
        var row = [
            '"' + (p.item_name || '').replace(/"/g, '""') + '"',
            '"' + (p.item_price || '').replace(/"/g, '""') + '"',
            '"' + (p.item_shop || '').replace(/"/g, '""') + '"',
            '"' + (p.item_link || '').replace(/"/g, '""') + '"'
        ].join(',');
        csvContent += row + '\n';
    }

    var blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = 'price_research_' + new Date().toISOString().slice(0, 10) + '.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast('CSV 导出成功', 'success');
}

// ==================== 加载调研历史 ====================
function loadResearchHistory() {
    var container = document.getElementById('pr-history-list');
    if (!container) return;

    container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-hint);">加载中...</div>';

    fetch('/api/price-research/history?limit=30')
        .then(function(resp) { return resp.json(); })
        .then(function(json) {
            if (!json.success) {
                container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-hint);">加载失败</div>';
                return;
            }

            var history = json.data || [];
            if (history.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-hint);">暂无调研记录</div>';
                return;
            }

            var html = '';
            for (var i = 0; i < history.length; i++) {
                var h = history[i];
                var time = (h.created_at || '').substring(0, 16);
                var platformLabel = platformNames[h.platform] || h.platform || '未知';

                html += '<div class="work-card" onclick="loadHistoryDetail(\'' + escapeHtml(h.file) + '\', \'' + escapeHtml(h.keyword) + '\')" style="cursor:pointer;display:flex;align-items:center;gap:10px;">';
                html += '<div style="width:32px;height:32px;border-radius:8px;background:rgba(99,102,241,0.15);display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">';
                if (h.platform === 'taobao') html += 'T';
                else if (h.platform === 'jd') html += 'J';
                else if (h.platform === '1688') html += '8';
                else html += '?';
                html += '</div>';
                html += '<div style="flex:1;min-width:0;">';
                html += '<div style="font-size:13px;font-weight:500;color:var(--text-primary);">' + escapeHtml(h.keyword) + '</div>';
                html += '<div style="font-size:11px;color:var(--text-hint);margin-top:2px;">' + platformLabel + ' · ' + (h.products_count || 0) + ' 条商品 · ' + time + '</div>';
                html += '</div></div>';
            }
            container.innerHTML = html;
        })
        .catch(function(e) {
            container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-hint);">加载失败</div>';
        });
}

function loadHistoryDetail(filename, keyword) {
    var container = document.getElementById('pr-results');
    if (!container) return;

    container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-hint);">加载中...</div>';

    fetch('/api/price-research/history-detail?file=' + encodeURIComponent(filename))
        .then(function(resp) { return resp.json(); })
        .then(function(json) {
            if (!json.success) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
                return;
            }
            var products = json.data.products || [];
            window._currentPriceResults = products;
            window._currentPriceKeyword = keyword || '';
            renderProductsTable(container, products);
        })
        .catch(function(e) {
            container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
        });
}
