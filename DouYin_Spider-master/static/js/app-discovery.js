// ==================== Discovery Section ====================
function searchCompetitors() {
    var keyword = getVal('disc-search-keyword');
    if (!keyword) { showToast('请输入搜索关键词', 'error'); return; }

    spinner('spinner-disc', true);
    fetch('/api/competitors/search?keyword=' + encodeURIComponent(keyword))
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-disc', false);
            if (json.success) {
                renderCompetitorResults(json.data || []);
                showToast('找到 ' + (json.count || 0) + ' 个竞品', 'success');
            } else {
                showToast('搜索失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-disc', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function discoverCompetitors() {
    var brandId = getVal('disc-brand');
    if (!brandId) { showToast('请先选择账号', 'error'); return; }

    var myFansRaw = getVal('disc-my-fans');
    var myFollowerCount = (myFansRaw === '' || myFansRaw === null || myFansRaw === undefined) ? -1 : (parseInt(myFansRaw) || 0);

    spinner('spinner-disc', true);
    fetch('/api/discovery/competitors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brand_id: brandId, my_follower_count: myFollowerCount })
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-disc', false);
            if (json.success) {
                var list = (json.data && json.data.competitors) ? json.data.competitors : [];
                renderCompetitorResults(list);
                var filterNotice = document.getElementById('disc-filter-notice');
                if (filterNotice && json.data && json.data.filter_summary) {
                    filterNotice.style.display = 'block';
                    filterNotice.textContent = json.data.filter_summary;
                }
                showToast('发现 ' + (json.data && json.data.total_found || list.length) + ' 个竞品', 'success');
                if (json.warnings && json.warnings.length) {
                    showToast('部分搜索失败: ' + json.warnings.join('; '), 'error');
                }
            } else {
                showToast('竞品发现失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-disc', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function discoverCrossCategory() {
    var brandId = getVal('disc-brand');
    if (!brandId) { showToast('请先选择账号', 'error'); return; }

    spinner('spinner-disc', true);
    fetch('/api/discovery/cross-category', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brand_id: brandId })
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-disc', false);
            if (json.success) {
                var list = (json.data && json.data.competitors) ? json.data.competitors : [];
                renderCompetitorResults(list);
                showToast('发现 ' + list.length + ' 个跨赛道灵感来源', 'success');
                if (json.warnings && json.warnings.length) {
                    showToast('部分搜索失败: ' + json.warnings.join('; '), 'error');
                }
            } else {
                showToast('跨赛道搜索失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-disc', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function addToMonitor(competitorId) {
    if (!competitorId) { showToast('缺少博主ID', 'error'); return; }

    spinner('spinner-disc', true);
    fetch('/api/competitors/' + competitorId + '/monitor', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'monitoring' })
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-disc', false);
            if (json.success) {
                showToast('已添加到监听列表', 'success');
            } else {
                showToast('添加失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-disc', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function renderCompetitorResults(list) {
    var container = document.getElementById('discovery-results');
    if (!container) return;

    var countEl = document.getElementById('disc-count');
    if (countEl) {
        countEl.style.display = list && list.length ? 'inline' : 'none';
        countEl.textContent = list ? list.length : 0;
    }

    if (!list || list.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">未发现竞品</div>';
        return;
    }

    var html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<thead><tr>';
    html += '<th style="text-align:left;padding:8px 12px;border-bottom:1px solid var(--border);font-size:12px;color:var(--text-dim);">博主</th>';
    html += '<th style="text-align:right;padding:8px 12px;border-bottom:1px solid var(--border);font-size:12px;color:var(--text-dim);">粉丝</th>';
    html += '<th style="text-align:center;padding:8px 12px;border-bottom:1px solid var(--border);font-size:12px;color:var(--text-dim);">操作</th>';
    html += '</tr></thead><tbody>';

    for (var i = 0; i < list.length; i++) {
        var c = list[i];
        var avatar = c.avatar || '';
        var nickname = escapeHtml(c.nickname || c.name || '未知');
        var followers = fmtCount(c.follower_count || 0);
        var cid = c.id || c.user_id || '';
        html += '<tr>';
        html += '<td style="padding:10px 12px;border-bottom:1px solid var(--border);">';
        html += '<div style="display:flex;align-items:center;gap:10px;">';
        if (avatar) {
            html += '<img src="' + avatar + '" style="width:36px;height:36px;border-radius:50%;object-fit:cover;" alt="">';
        } else {
            html += '<div style="width:36px;height:36px;border-radius:50%;background:var(--accent);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600;font-size:14px;">' + (nickname.charAt(0) || '?') + '</div>';
        }
        html += '<span style="font-weight:500;">' + nickname + '</span>';
        html += '</div></td>';
        html += '<td style="text-align:right;padding:10px 12px;border-bottom:1px solid var(--border);font-size:13px;">' + followers + '</td>';
        html += '<td style="text-align:center;padding:10px 12px;border-bottom:1px solid var(--border);">';
        html += '<button class="btn btn-primary btn-sm" onclick="addToMonitor(\'' + cid + '\')">&#10133; 监听</button>';
        html += '</td></tr>';
    }
    html += '</tbody></table>';
    container.innerHTML = html;
}
