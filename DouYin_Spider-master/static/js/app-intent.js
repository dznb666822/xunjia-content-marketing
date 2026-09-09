// ==================== Intent Analysis Section ====================
var currentIntentTaskId = null;
var intentPollingTimer = null;

// 意向等级颜色映射
var intentColors = {
    '高': '#f56c6c',
    '中': '#e6a23c',
    '低': '#909399',
    '无': '#c0c4cc',
    '未分析': '#dcdfe6'
};

// ==================== 启动意向分析 ====================
function startIntentAnalysis() {
    var workUrl = getVal('intent-work-url');

    if (!workUrl) { showToast('请输入视频链接', 'error'); return; }

    spinner('spinner-intent', true);
    fetch('/api/intent/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ work_url: workUrl })
    })
    .then(function(resp) { return resp.json(); })
    .then(function(json) {
        spinner('spinner-intent', false);
        if (json.success) {
            currentIntentTaskId = json.data.task_id;
            showToast('意向分析任务已启动', 'success');
            pollIntentTaskStatus();
        } else {
            showToast('启动失败: ' + (json.error || '未知错误'), 'error');
        }
    })
    .catch(function(e) {
        spinner('spinner-intent', false);
        showToast('请求失败: ' + e.message, 'error');
    });
}

// ==================== 轮询任务状态 ====================
function pollIntentTaskStatus() {
    if (!currentIntentTaskId) return;

    if (intentPollingTimer) clearInterval(intentPollingTimer);

    pollIntentTaskOnce();

    intentPollingTimer = setInterval(function() {
        pollIntentTaskOnce();
    }, 3000);
}

function pollIntentTaskOnce() {
    if (!currentIntentTaskId) return;

    fetch('/api/intent/status/' + currentIntentTaskId)
    .then(function(resp) { return resp.json(); })
    .then(function(json) {
        if (!json.success) return;
        var s = json.data;

        // 显示进度条容器
        var progContainer = document.getElementById('intent-progress-container');
        var progBar = document.getElementById('intent-progress-bar');
        var progText = document.getElementById('intent-progress-text');

        if (s.status === 'running' || s.status === 'pending') {
            if (progContainer) progContainer.style.display = 'block';
            if (progBar) progBar.style.width = (s.progress || 0) + '%';
            if (progText) progText.textContent = s.message || '';
        }

        if (s.status === 'completed' || s.status === 'failed') {
            if (intentPollingTimer) { clearInterval(intentPollingTimer); intentPollingTimer = null; }

            if (s.status === 'completed') {
                if (progBar) progBar.style.width = '100%';
                if (progText) progText.textContent = s.message || '';
                showToast(s.message, 'success');
                loadIntentResults();
                loadIntentStats(s);
            } else {
                if (progBar) progBar.style.width = '100%';
                if (progBar) progBar.style.background = 'var(--color-error)';
                if (progText) progText.textContent = s.message || '';
                showToast(s.message, 'error');
            }
        }
    })
    .catch(function(e) {
        console.error('轮询失败:', e);
    });
}

function loadIntentStats(s) {
    var statsEl = document.getElementById('intent-stats');
    if (!statsEl) return;
    var total = s.total_comments || 0;
    var high = s.high_intent || 0;
    var mid = s.mid_intent || 0;
    var low = s.low_intent || 0;
    var none = (s.no_intent || 0) + (total - high - mid - low);

    statsEl.innerHTML =
        '<div class="stat-badge" style="background:#fef0f0;color:#f56c6c"><b>高意向</b> ' + high + ' 人</div>' +
        '<div class="stat-badge" style="background:#fdf6ec;color:#e6a23c"><b>中意向</b> ' + mid + ' 人</div>' +
        '<div class="stat-badge" style="background:#f4f4f5;color:#909399"><b>低意向</b> ' + low + ' 人</div>' +
        '<div class="stat-badge" style="background:#fafafa;color:#c0c4cc"><b>无意向</b> ' + none + ' 人</div>';
}

// ==================== 加载分析结果 ====================
function loadIntentResults() {
    if (!currentIntentTaskId) return;

    fetch('/api/intent/results/' + currentIntentTaskId)
    .then(function(resp) { return resp.json(); })
    .then(function(json) {
        if (!json.success) { showToast('获取结果失败', 'error'); return; }
        var items = json.data.products || [];

        // 按意向等级排序：高 > 中 > 低 > 无
        var levelOrder = {'高': 0, '中': 1, '低': 2, '无': 3, '未分析': 4};
        items.sort(function(a, b) {
            return (levelOrder[a.intent_level] || 5) - (levelOrder[b.intent_level] || 5);
        });

        renderIntentTable(items);
    });
}

// ==================== 渲染结果表格 ====================
function renderIntentTable(items) {
    var tbody = document.getElementById('intent-tbody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#999">暂无结果</td></tr>';
        return;
    }

    var html = '';
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var level = item.intent_level || '未分析';
        var color = intentColors[level] || intentColors['未分析'];
        var keyPoints = item.key_points || [];
        var pointsHtml = keyPoints.length ? keyPoints.map(function(p) { return '<span class="tag">' + p + '</span>'; }).join('') : '-';

        html += '<tr class="intent-row intent-' + level + '">';
        html += '<td style="width:40px;text-align:center">' + (i + 1) + '</td>';
        html += '<td><span style="background:' + color + ';color:#fff;padding:2px 8px;border-radius:3px;font-size:12px">' + level + '</span></td>';
        html += '<td><b>' + escapeHtml(item.user || '') + '</b><br><span style="color:#666;font-size:13px">' + escapeHtml(item.comment || '') + '</span></td>';
        html += '<td style="font-size:13px">' + (item.intent_type || '') + '</td>';
        html += '<td style="font-size:12px;color:#999">' + escapeHtml(item.reason || '') + '<br>' + pointsHtml + '</td>';
        html += '</tr>';
    }

    tbody.innerHTML = html;
}

// ==================== 历史记录 ====================
function loadIntentHistory() {
    var historyEl = document.getElementById('intent-history');
    if (!historyEl) return;

    historyEl.innerHTML = '<div style="text-align:center;color:#999;padding:10px">加载中...</div>';

    fetch('/api/intent/history')
    .then(function(resp) { return resp.json(); })
    .then(function(json) {
        if (!json.success || !json.data || json.data.length === 0) {
            historyEl.innerHTML = '<div style="text-align:center;color:#999;padding:10px">暂无历史记录</div>';
            return;
        }
        var html = '';
        for (var i = 0; i < json.data.length; i++) {
            var rec = json.data[i];
            var s = rec.summary || {};
            var ts = rec.analyzed_at ? rec.analyzed_at.slice(0, 19).replace('T', ' ') : '';
            html += '<div class="history-item" onclick="loadIntentHistoryDetail(\'' + rec.task_id + '\')" style="cursor:pointer;padding:8px 12px;margin:4px 0;background:#f8f9fa;border-radius:6px;border-left:3px solid #409eff">';
            html += '<div style="font-size:13px;color:#666">' + ts + '</div>';
            html += '<div><b>' + escapeHtml(rec.video_title || '抖音视频') + '</b></div>';
            html += '<div style="font-size:12px;margin-top:4px">';
            html += '<span style="color:#f56c6c">高意向:' + (s.high || 0) + '</span> ';
            html += '<span style="color:#e6a23c">中意向:' + (s.mid || 0) + '</span> ';
            html += '<span style="color:#909399">低意向:' + (s.low || 0) + '</span> ';
            html += '<span>总计:' + (rec.total || 0) + '条</span>';
            html += '</div></div>';
        }
        historyEl.innerHTML = html;
    });
}

function loadIntentHistoryDetail(taskId) {
    fetch('/api/intent/history-detail?task_id=' + taskId)
    .then(function(resp) { return resp.json(); })
    .then(function(json) {
        if (!json.success) { showToast('加载失败', 'error'); return; }
        var data = json.data;
        var items = data.results || [];
        var levelOrder = {'高': 0, '中': 1, '低': 2, '无': 3, '未分析': 4};
        items.sort(function(a, b) {
            return (levelOrder[a.intent_level] || 5) - (levelOrder[b.intent_level] || 5);
        });
        currentIntentTaskId = taskId;
        renderIntentTable(items);
        showToast('已加载: ' + (data.video_title || '历史记录'), 'info');
    });
}

// ==================== 工具函数 ====================
function escapeHtml(str) {
    if (!str) return '';
    str = String(str);
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
