// ==================== Panel Title Map ====================
var panelTitles = {
  discovery:'竞品发现', monitor:'监听中心', analysis:'内容分析',
  scripts:'脚本生成', 'price-research':'竞品价格调研', intent:'意向客户分析', dashboard:'数据看板',
  'tools-search':'搜索采集', 'tools-user':'用户抓取', 'tools-work':'作品详情',
  'tools-live':'直播间', 'tools-message':'私信管理', 'tools-feed':'推荐流', 'tools-notice':'通知中心',
  'profile':'个人信息', 'trendradar':'热点雷达', 'trend':'行业趋势报告', 'prompts':'AI提示词管理',
  'mashup':'智能混剪', 'comic':'AI漫剧设计中心', 'admin-users':'用户权限管理', 'ai-clip':'AI智能混剪', 'materials':'素材获取'
};

// 可授权给普通用户的功能（与后端 user_auth.ALL_FEATURES 保持一致）
var AUTHORIZABLE_FEATURES = [
  'discovery', 'monitor', 'analysis', 'scripts', 'price-research', 'intent', 'dashboard',
  'tools-search', 'tools-user', 'tools-work', 'tools-live', 'tools-message', 'tools-feed', 'tools-notice',
  'profile', 'trendradar', 'trend', 'prompts', 'mashup', 'comic', 'ai-clip', 'materials', 'campaign'
];

// ==================== Helper Functions ====================
function getVal(id) { var el=document.getElementById(id); return el?el.value.trim():''; }
function setVal(id, v) { var el=document.getElementById(id); if(el)el.value=v; }

function showResult(id, data) {
  var el = document.getElementById(id);
  if(!el)return;
  el.classList.add('show');
  el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}

function showToast(msg, type) {
  var t = document.createElement('div');
  t.className = 'toast ' + (type||'success');
  t.textContent = msg;
  document.getElementById('toast-container').appendChild(t);
  setTimeout(function(){ t.remove(); }, 3000);
}

function spinner(id, show) {
  var el = document.getElementById(id);
  if(el) el.classList.toggle('show', show);
}

function apiCall(url, data, resultId, spinnerId) {
  if (spinnerId) spinner(spinnerId, true);
  return fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data || {})
  }).then(function(resp){ return resp.json(); }).then(function(json){
    if (resultId) showResult(resultId, json);
    if (json.success) {
      showToast((json.message||'操作成功'), 'success');
      if (json.count !== undefined) showToast('获取到 ' + json.count + ' 条结果', 'success');
    } else {
      showToast('失败: ' + (json.error || '未知错误'), 'error');
    }
    return json;
  }).catch(function(e){
    showToast('请求错误: ' + e.message, 'error');
    return null;
  }).finally(function(){
    if (spinnerId) spinner(spinnerId, false);
  });
}

// ==================== Navigation ====================
function switchPanel(pid) {
  // deactivate all nav items + nav tags
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(function(i){ i.classList.remove('active'); });
  document.querySelectorAll('.sidebar-nav .nav-tag').forEach(function(t){ t.classList.remove('active'); });
  // activate the matching item/tag
  var navItem = document.querySelector('.sidebar-nav [data-panel="'+pid+'"]');
  if(navItem) navItem.classList.add('active');

  // deactivate all panels
  document.querySelectorAll('.panel').forEach(function(p){ p.classList.remove('active'); });
  // activate target panel
  var panel = document.getElementById('panel-' + pid);
  if(panel) panel.classList.add('active');

  // update topbar title
  document.getElementById('panel-title').textContent = panelTitles[pid] || pid;

  // auto-expand the group containing this nav item
  var group = navItem ? navItem.closest('.nav-group') : null;
  if (group && group.classList.contains('collapsed')) {
    group.classList.remove('collapsed');
  }

  // 切换面板时自动加载历史
  if (pid === 'analysis' && typeof loadAnalysisHistory === 'function') {
    loadAnalysisHistory();
  }
  if (pid === 'scripts' && typeof loadScriptsHistory === 'function') {
    loadScriptsHistory();
  }
  if (pid === 'price-research' && typeof loadResearchHistory === 'function') {
    loadResearchHistory();
  }
  if (pid === 'intent' && typeof loadIntentHistory === 'function') {
    loadIntentHistory();
  }
  if (pid === 'trendradar') {
    trendradarRefreshStatus();
    trendradarLoadConfig();
    trendradarLoadPromptVersions();
  }
  if (pid === 'admin-users' && typeof loadAdminUsers === 'function') {
    loadAdminUsers();
  }
  if (pid === 'comic' && typeof comicShowList === 'function') {
    comicShowList();
  }
  // 营销策略Agent（内嵌版）：首次切入时初始化
  if (pid === 'campaign' && window.cpCampaignInit) {
    window.cpCampaignInit();
  }
}

// bind nav items (backward compat)
document.querySelectorAll('.sidebar-nav .nav-item').forEach(function(item){
  item.addEventListener('click', function(){
    var pid = item.dataset.panel;
    switchPanel(pid);
  });
});

// bind nav tags
document.querySelectorAll('.sidebar-nav .nav-tag').forEach(function(tag){
  tag.addEventListener('click', function(){
    var pid = tag.dataset.panel;
    switchPanel(pid);
  });
});

// accordion: toggle nav groups
document.querySelectorAll('.sidebar-section-title').forEach(function(title){
  title.addEventListener('click', function(){
    var group = title.closest('.nav-group');
    if (group) group.classList.toggle('collapsed');
  });
});

// 禁用"待开发"导航项的点击（不切换面板）
document.querySelectorAll('.sidebar-nav .nav-item-disabled').forEach(function(item){
  item.addEventListener('click', function(e){
    e.stopPropagation();
    showToast('该功能正在开发中，敬请期待', 'warning');
  });
});

// ==================== Tabs ====================
function switchSearchTab(type) {
  document.querySelectorAll('#panel-tools-search .tab').forEach(function(t){ t.classList.remove('active'); });
  event.target.classList.add('active');
  document.getElementById('search-user-tab').style.display = type === 'user' ? 'block' : 'none';
  document.getElementById('search-live-tab').style.display = type === 'live' ? 'block' : 'none';
}

// ==================== Generic Checkbox Helpers ====================
function toggleCheckAll(className, masterCheckbox) {
  var checked = masterCheckbox.checked;
  document.querySelectorAll('.'+className).forEach(function(cb){ cb.checked = checked; });
}

function getCheckedIds(className) {
  var ids = [];
  document.querySelectorAll('.'+className+':checked').forEach(function(cb){
    if(cb.value) ids.push(cb.value);
  });
  return ids;
}

// ==================== Utility: Clipboard ====================
function escapeHtml(str) {
  return (str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

function copyToClipboard(text) {
  var decoded = text.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#039;/g,"'");
  if(navigator.clipboard) {
    navigator.clipboard.writeText(decoded).then(function(){ showToast('已复制到剪贴板', 'success'); });
  } else {
    var ta = document.createElement('textarea');
    ta.value = decoded; ta.style.position='fixed'; ta.style.left='-9999px';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    showToast('已复制到剪贴板', 'success');
  }
}

// ==================== Manual Tool Functions ====================
function toolsSearchWorks() {
  apiCall('/api/search_works', {
    query: getVal('s-query'), num: parseInt(getVal('s-num')),
    sort_type: getVal('s-sort'), publish_time: getVal('s-time'),
    content_type: getVal('s-content'), download: document.getElementById('s-download').checked
  }, 'result-search-works', 'spinner-search-works');
}
function toolsSearchUsers() {
  apiCall('/api/search_users', {
    query: getVal('su-query'), num: parseInt(getVal('su-num'))
  }, 'result-search-users', 'spinner-search-users');
}
function toolsSearchLives() {
  var query = getVal('sl-query');
  var num = parseInt(getVal('sl-num'));
  var resultEl = document.getElementById('result-search-lives');
  var spinnerEl = document.getElementById('spinner-search-lives');
  if (spinnerEl) spinnerEl.classList.add('show');
  fetch('/api/search_lives', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query: query, num: num})
  }).then(function(resp) { return resp.json(); }).then(function(json) {
    if (spinnerEl) spinnerEl.classList.remove('show');
    if (json.success && json.data) {
      renderLiveCards(json.data, resultEl);
      showToast('获取到 ' + json.count + ' 个直播间', 'success');
    } else {
      showToast('失败: ' + (json.error || '未知错误'), 'error');
    }
  }).catch(function(e) {
    if (spinnerEl) spinnerEl.classList.remove('show');
    showToast('请求错误: ' + e.message, 'error');
  });
}

function renderLiveCards(lives, container) {
  if (!container) return;
  container.innerHTML = '';
  container.classList.add('show');
  // 缓存搜索结果数据
  window._liveSearchCache = {};
  var html = '<div class="live-grid">';
  lives.forEach(function(l, idx) {
    var rid = l.room_id || '';
    var cacheKey = '_ls' + idx;
    window._liveSearchCache[cacheKey] = l;
    html += '<div class="live-card">'
      + '<div class="lc-cover">'
      + '<img src="' + (l.avatar || '') + '" alt="" loading="lazy" onerror="this.src=\'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 64 64%22><rect fill=%22%23e2e8f0%22 width=%2264%22 height=%2264%22/><text x=%2232%22 y=%2238%22 text-anchor=%22middle%22 fill=%22%2394a3b8%22 font-size=%2220%22>' + encodeURIComponent((l.nickname||'?')[0]) + '</text></svg>\'">'
      + '<span class="lc-live-badge">LIVE</span>'
      + '</div>'
      + '<div class="lc-body">'
      + '<div class="lc-name" title="' + l.nickname + '">' + (l.nickname || '--') + '</div>'
      + '<div class="lc-id-row">'
      + '<span class="lc-id" title="' + rid + '">Room: ' + rid + '</span>'
      + '<button class="lc-copy-btn" onclick="copyLiveId(\'' + rid + '\', this)" title="复制直播间ID">复制</button>'
      + '</div>'
      + '<div class="lc-id-row" style="margin-top:4px">'
      + '<button class="lc-detail-btn" onclick="goLiveDetail(\'' + cacheKey + '\')">查看详情</button>'
      + '</div>'
      + (l.uid ? '<div class="lc-meta">UID: ' + l.uid + '</div>' : '')
      + '</div>'
      + '</div>';
  });
  html += '</div>';
  container.innerHTML = html;
}

// 从搜索结果跳转到直播间详情
function goLiveDetail(cacheKey) {
  var liveData = (window._liveSearchCache || {})[cacheKey];
  if (!liveData) return;
  window._liveRoomCache = liveData;
  setVal('lv-id', liveData.room_id || '');
  switchPanel('tools-live');
  setTimeout(function() { toolsGetLiveInfo(); }, 300);
}

function copyLiveId(id, btn) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(id).then(function() {
      btn.textContent = '已复制';
      btn.classList.add('copied');
      setTimeout(function() { btn.textContent = '复制'; btn.classList.remove('copied'); }, 1500);
    });
  } else {
    var ta = document.createElement('textarea');
    ta.value = id; ta.style.position='fixed'; ta.style.left='-9999px';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    btn.textContent = '已复制';
    btn.classList.add('copied');
    setTimeout(function() { btn.textContent = '复制'; btn.classList.remove('copied'); }, 1500);
  }
}

function toolsGetUserInfo() {
  apiCall('/api/get_user_info', {user_url: getVal('u-url')}, 'result-user', 'spinner-user')
    .then(function(json){
      if (json && json.success && json.data && json.data.user) {
        setVal('uf-url', getVal('u-url'));
        setVal('uf-user-id', json.data.user.uid || '');
        setVal('uf-sec-id', json.data.user.sec_uid || '');
      }
    });
}
function toolsGetUserAllWorks() {
  apiCall('/api/get_user_all_works', {user_url: getVal('u-url')}, 'result-user', 'spinner-user');
}
function toolsGetFollowerList() {
  apiCall('/api/get_follower_list', {
    user_id: getVal('uf-user-id'), sec_id: getVal('uf-sec-id'), num: parseInt(getVal('uf-num'))
  }, 'result-uf', 'spinner-uf');
}
function toolsGetFollowingList() {
  apiCall('/api/get_following_list', {
    user_id: getVal('uf-user-id'), sec_id: getVal('uf-sec-id'), num: parseInt(getVal('uf-num'))
  }, 'result-uf', 'spinner-uf');
}

function toolsGetWorkInfo() {
  apiCall('/api/get_work_info', {work_url: getVal('w-url')}, 'result-work', 'spinner-work');
}
function toolsGetWorkComments() {
  apiCall('/api/get_work_comments', {work_url: getVal('w-url')}, 'result-work', 'spinner-work');
}

function toolsGetLiveInfo() {
  var liveId = getVal('lv-id');
  var resultEl = document.getElementById('result-live');
  var spinnerEl = document.getElementById('spinner-live');
  if (spinnerEl) spinnerEl.classList.add('show');
  fetch('/api/get_live_info', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({live_id: liveId})
  }).then(function(resp) { return resp.json(); }).then(function(json) {
    if (spinnerEl) spinnerEl.classList.remove('show');
    if (json.success && json.data) {
      renderLiveInfoCard(json.data, resultEl);
      if (json.data.room_id) {
        setVal('lv-room-id', json.data.room_id);
      }
    } else {
      showToast('失败: ' + (json.error || '未知错误'), 'error');
    }
  }).catch(function(e) {
    if (spinnerEl) spinnerEl.classList.remove('show');
    showToast('请求错误: ' + e.message, 'error');
  });
}

function renderLiveInfoCard(info, container) {
  if (!container) return;
  container.classList.add('show');
  var statusColors = {1: '#3b82f6', 2: '#22c55e', 3: '#94a3b8', 4: '#f59e0b'};
  var statusLabels = {1: '可访问', 2: '直播中', 3: '已结束', 4: '未知'};
  var color = statusColors[info.status] || '#94a3b8';
  var cached = window._liveRoomCache || {};
  var matchCache = (cached.room_id == info.room_id) ? cached : null;

  var html = '<div class="live-info-card">';

  // 作者信息区 (来自搜索结果缓存)
  if (matchCache) {
    html += '<div class="li-author-row">'
      + '<img class="li-author-avatar" src="' + (matchCache.avatar || '') + '" onerror="this.style.display=\'none\'">'
      + '<div class="li-author-info">'
      + '<div class="li-author-name">' + (matchCache.nickname || '--') + '</div>'
      + (matchCache.uid ? '<div class="li-author-uid">UID: ' + matchCache.uid + '</div>' : '')
      + (matchCache.short_id ? '<div class="li-author-uid">短ID: ' + matchCache.short_id + '</div>' : '')
      + '</div>'
      + '</div>';
  }

  // 房间信息
  html += '<div class="li-header">'
    + '<div class="li-room-id">' + (info.room_id || '--') + '</div>'
    + '<button class="li-copy-btn" onclick="copyLiveId(\'' + (info.room_id || '') + '\', this)">复制ID</button>'
    + '</div>'
    + '<div class="li-status" style="background:' + color + '">' + (info.status_str || '未知') + '</div>'
    + (info.title ? '<div class="li-title">' + info.title + '</div>' : '');

  // 页面组件状态
  html += '<div class="li-details">'
    + (info.has_player ? '<span class="li-tag ok">播放器已加载</span>' : '<span class="li-tag warn">播放器未加载</span>')
    + (info.has_chat ? '<span class="li-tag ok">聊天系统已加载</span>' : '<span class="li-tag warn">聊天系统未加载</span>')
    + '</div>';

  // 操作区
  html += '<div class="li-actions">'
    + '<a class="li-link" href="' + (info.url || '#') + '" target="_blank">在抖音中打开</a>'
    + (matchCache ? '<span class="li-hint">数据来自搜索结果</span>' : '<span class="li-hint">手动输入，建议从搜索结果跳转以获取更多信息</span>')
    + '</div>';

  html += '</div>';
  container.innerHTML = html;
}
function toolsSendLiveMsg() {
  apiCall('/api/live/send_msg', {
    room_id: getVal('lv-room-id'), content: getVal('lv-msg')
  }, 'result-live-op', 'spinner-live-op');
}
function toolsDiggLive() {
  apiCall('/api/live/digg', {
    room_id: getVal('lv-room-id'), count: '1'
  }, 'result-live-op', 'spinner-live-op');
}

function toolsCreateConversation() {
  apiCall('/api/create_conversation', {to_user_id: getVal('msg-uid')}, 'result-msg', 'spinner-msg')
    .then(function(json){
      if (json && json.success) {
        setVal('msg-cid', json.conversation_id);
        setVal('msg-sid', json.conversation_short_id);
        setVal('msg-ticket', json.ticket);
      }
    });
}
function toolsSendMsg() {
  apiCall('/api/send_msg', {
    conversation_id: getVal('msg-cid'),
    conversation_short_id: getVal('msg-sid'),
    ticket: getVal('msg-ticket'),
    content: getVal('msg-content')
  }, 'result-msg-send', 'spinner-msg-send');
}

function toolsGetFeed() {
  var count = getVal('feed-num');
  var resultEl = document.getElementById('result-feed');
  var spinnerEl = document.getElementById('spinner-feed');
  if (spinnerEl) spinnerEl.classList.add('show');
  fetch('/api/get_feed', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({count: count})
  }).then(function(resp) { return resp.json(); }).then(function(json) {
    if (spinnerEl) spinnerEl.classList.remove('show');
    if (json.success && json.data) {
      renderFeedCards(json.data, resultEl);
      showToast('获取到 ' + json.count + ' 条推荐视频', 'success');
    } else {
      showToast('失败: ' + (json.error || '未知错误'), 'error');
    }
  }).catch(function(e) {
    if (spinnerEl) spinnerEl.classList.remove('show');
    showToast('请求错误: ' + e.message, 'error');
  });
}

function renderFeedCards(videos, container) {
  if (!container) return;
  container.innerHTML = '';
  container.classList.add('show');
  var html = '<div class="feed-grid">';
  videos.forEach(function(v) {
    html += '<div class="feed-card">'
      + '<div class="fc-cover">'
      + '<img src="' + (v.cover_url || '') + '" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
      + '<span class="fc-duration">' + (v.duration || '') + '</span>'
      + '<span class="fc-plays">&#9654; ' + (v.play_count || '0') + '</span>'
      + '</div>'
      + '<div class="fc-body">'
      + '<div class="fc-desc" title="' + v.desc + '">' + (v.desc || '') + '</div>'
      + '<div class="fc-meta">'
      + '<img class="fc-avatar" src="' + (v.author_avatar || '') + '" onerror="this.style.display=\'none\'">'
      + '<span class="fc-author">' + (v.author_name || '') + '</span>'
      + '</div>'
      + '<div class="fc-stats">'
      + '<span title="点赞">&#10084; ' + (v.like_count || '0') + '</span>'
      + '<span title="评论">&#128172; ' + (v.comment_count || '0') + '</span>'
      + '<span title="分享">&#128257; ' + (v.share_count || '0') + '</span>'
      + '</div>'
      + '</div>'
      + '</div>';
  });
  html += '</div>';
  container.innerHTML = html;
}

function toolsGetNoticeList() {
  apiCall('/api/get_notice_list', {
    num: parseInt(getVal('nc-num')), notice_group: getVal('nc-group')
  }, 'result-notice', 'spinner-notice');
}

// ==================== Login / Register / Logout ====================
window.currentBrandId = null;
window.currentBrandName = '';
window.currentUser = null;

function switchLoginTab(type) {
  document.querySelectorAll('.login-tab').forEach(function(t){ t.classList.remove('active'); });
  document.querySelectorAll('.login-form').forEach(function(f){ f.classList.remove('active'); });
  event.target.classList.add('active');
  document.getElementById(type + '-form').classList.add('active');
}

function doLogin() {
  var name = getVal('login-name');
  var pwd = getVal('login-password');
  if (!name) { showToast('请输入账号名称', 'error'); return; }
  if (!pwd) { showToast('请输入密码', 'error'); return; }

  fetch('/api/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: name, password: pwd})
  }).then(function(r){ return r.json(); }).then(function(json){
    if (json.success && json.user) {
      enterApp(json.user);
    } else {
      showToast('登录失败: ' + (json.error || '账号或密码错误'), 'error');
    }
  }).catch(function(e){ showToast('登录失败: ' + e.message, 'error'); });
}

function doRegister() {
  var name = getVal('reg-name');
  var pwd = getVal('reg-password');
  var pwd2 = getVal('reg-password2');
  if (!name) { showToast('请输入账号名称', 'error'); return; }
  if (!pwd) { showToast('请输入密码', 'error'); return; }
  if (pwd !== pwd2) { showToast('两次输入的密码不一致', 'error'); return; }

  fetch('/api/auth/register', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: name, password: pwd})
  }).then(function(r){ return r.json(); }).then(function(json){
    if (json.success && json.user) {
      showToast('注册成功，正在进入平台...', 'success');
      setTimeout(function(){ enterApp(json.user); }, 400);
    } else {
      showToast('注册失败: ' + (json.error || '未知错误'), 'error');
    }
  }).catch(function(e){ showToast('注册失败: ' + e.message, 'error'); });
}

function applyFeatures(features) {
  var allowed = {};
  (features || []).forEach(function(f){ allowed[f] = true; });
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(function(item){
    var p = item.getAttribute('data-panel');
    if (!p) return;
    item.style.display = allowed[p] ? '' : 'none';
  });
  // 隐藏没有任何可见菜单项的一级分组（如普通用户看不到“账号权限”）
  document.querySelectorAll('.sidebar-nav .nav-group').forEach(function(group){
    var visible = false;
    group.querySelectorAll('.nav-item').forEach(function(item){
      if (item.style.display !== 'none') visible = true;
    });
    group.style.display = visible ? '' : 'none';
  });
}

function enterApp(user) {
  window.currentUser = user;
  window.currentBrandName = user.username;
  document.getElementById('login-page').classList.add('hidden');
  document.getElementById('app-shell').classList.add('active');
  document.getElementById('sidebar-account-name').textContent = user.username;
  applyFeatures(user.features);
  // 加载数据
  if (typeof fetchAndPopulateBrands === 'function') fetchAndPopulateBrands();
  // 默认展示竞品发现
  switchPanel('discovery');
  // 登录后侧边栏默认折叠，只显示一级标题（分组名），不展开二级功能项
  document.querySelectorAll('.sidebar-nav .nav-group').forEach(function(group){
    group.classList.add('collapsed');
  });
}

// ==================== 个人信息 (Profile) ====================
(function(){
  var code = [
    'javascript:(function(){',
    'var d={cookies:document.cookie,ticket:"",ts_sign:"",private_key:"",client_cert:""};',
    '(document.cookie.split(";")||[]).forEach(function(c){',
    '  c=c.trim();',
    '  if(c.indexOf("bd_ticket_guard_client_data_v2=")===0){',
    '    try{',
    '      var raw=decodeURIComponent(c.split("=").slice(1).join("=")),parsed=JSON.parse(raw);',
    '      function f(o,k){',
    '        if(!o||typeof o!=="object")return null;',
    '        if(o[k]!==undefined)return o[k];',
    '        for(var i in o){var r=f(o[i],k);if(r!==null)return r;}',
    '        return null;',
    '      };',
    '      d.ticket=f(parsed,"ticket")||"";',
    '      d.ts_sign=f(parsed,"ts_sign")||"";',
    '      d.client_cert=f(parsed,"client_cert")||"";',
    '      d.private_key=f(parsed,"private_key")||f(parsed,"ec_privateKey")||"";',
    '    }catch(e){}',
    '  }',
    '});',
    'fetch("http://127.0.0.1:5000/api/save_auth",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(d)})',
    '.then(function(r){return r.json()})',
    '.then(function(r){alert(r.success?"\\u2705 \\u914d\\u7f6e\\u5df2\\u4fdd\\u5b58\\uff01":"\\u274c \\u5931\\u8d25: "+(r.error||""))})',
    '.catch(function(e){alert("\\u8bf7\\u6c42\\u5931\\u8d25\\uff0c\\u786e\\u4fdd\\u670d\\u52a1\\u5df2\\u542f\\u52a8: "+e.message)});',
    '})();'
  ].join('');
  var el = document.getElementById('bm-link');
  if (el) el.href = code;
})();

function profileSaveCookie() {
  var cookies = (document.getElementById('profile-cookie')||{}).value||'';
  if (!cookies) { showToast('请先粘贴 Cookie', 'error'); return; }
  var statusEl = document.getElementById('profile-save-status');
  fetch('/api/save_auth', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({cookies: cookies, ticket: '', ts_sign: '', private_key: '', client_cert: ''})
  }).then(function(r){ return r.json(); }).then(function(j){
    if (j.success) {
      if (statusEl) { statusEl.style.display = 'inline'; setTimeout(function(){ statusEl.style.display = 'none'; }, 3000); }
      showToast('Cookie 已保存，请重启服务', 'success');
      checkProfileStatus();
    } else {
      showToast('保存失败: ' + (j.error || ''), 'error');
    }
  }).catch(function(e){ showToast('请求失败', 'error'); });
}

function checkProfileStatus() {
  var el = document.getElementById('profile-status');
  if (!el) return;
  fetch('/api/get_feed', {method:'POST',headers:{'Content-Type':'application/json'},body:'{"count":"1"}'})
    .then(function(r){ return r.json(); })
    .then(function(j){
      if (j.success) {
        el.innerHTML = '<span style="color:#22c55e;">&#9989; 已连接抖音 — Cookie 有效</span>';
      } else if (j.error && j.error.indexOf('登录') >= 0) {
        el.innerHTML = '<span style="color:#f59e0b;">&#9888; Cookie 已过期，请重新获取</span>';
      } else {
        el.innerHTML = '<span style="color:#ef4444;">&#10060; 连接失败: ' + (j.error || '未知') + '</span>';
      }
    }).catch(function(){
      el.innerHTML = '<span style="color:#ef4444;">&#10060; 服务不可达</span>';
    });
}

// Auto-check status when profile panel opens
setInterval(function(){
  var panel = document.getElementById('panel-profile');
  if (panel && panel.classList.contains('active')) checkProfileStatus();
}, 5000);

// ==================== 热点雷达 (TrendRadar) ====================

window._radarConfigPending = {};    // 待保存的配置变更
window._radarConfigData = null;     // 服务端加载的完整配置

function radarSetVal(key, val) {
  window._radarConfigPending[key] = val;
}

function radarSetChannel(channel, key, val) {
  if (!window._radarConfigPending['_channels']) window._radarConfigPending['_channels'] = {};
  if (!window._radarConfigPending['_channels'][channel]) window._radarConfigPending['_channels'][channel] = {};
  window._radarConfigPending['_channels'][channel][key] = val;
}

function trendradarLoadConfig() {
  showToast('正在加载配置...', 'info');
  fetch('/api/trendradar/config').then(function(r){ return r.json(); }).then(function(json){
    if (!json.success || !json.data) {
      showToast('加载配置失败: ' + (json.error || ''), 'error');
      return;
    }
    var d = json.data;
    window._radarConfigData = d;
    window._radarConfigPending = {};

    // 平台选择
    var platformsEl = document.getElementById('radar-platforms');
    if (platformsEl && d.platforms && d.platforms.sources) {
      var ph = '';
      d.platforms.sources.forEach(function(s) {
        var chk = s.enabled !== false ? ' checked' : '';
        ph += '<label class="radar-platform-chip" style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;background:rgba(248,249,255,0.7);border-radius:6px;cursor:pointer;border:1px solid ' + (s.enabled !== false ? '#6366f1' : '#e2e8f0') + ';font-size:11px;">'
          + '<input type="checkbox" data-radar-platform="' + s.id + '"' + chk + ' onchange="radarOnPlatformToggle(this)"> '
          + s.name
          + '</label>';
      });
      platformsEl.innerHTML = ph;
    }

    // 报告模式
    var modeRadio = document.querySelector('input[name="radar-mode"][value="' + (d.report.mode || 'current') + '"]');
    if (modeRadio) modeRadio.checked = true;
    var dm = document.getElementById('radar-display-mode');
    if (dm) dm.value = d.report.display_mode || 'keyword';

    // 筛选方式
    var filterRadio = document.querySelector('input[name="radar-filter"][value="' + (d.filter.method || 'keyword') + '"]');
    if (filterRadio) filterRadio.checked = true;

    // AI模型
    var aiModel = document.getElementById('radar-ai-model');
    if (aiModel) aiModel.value = d.ai.model || '';
    var aiTemp = document.getElementById('radar-ai-temp');
    if (aiTemp) aiTemp.value = d.ai.temperature || 1.0;
    var aiKey = document.getElementById('radar-ai-key');
    if (aiKey) aiKey.value = d.ai.api_key || '';
    var aiBase = document.getElementById('radar-ai-base');
    if (aiBase) aiBase.value = d.ai.api_base || '';

    // 通知渠道
    if (d.channels) {
      var feishu = document.getElementById('radar-feishu');
      if (feishu && d.channels.feishu) feishu.value = d.channels.feishu.webhook_url || '';
      var dt = document.getElementById('radar-dingtalk');
      if (dt && d.channels.dingtalk) dt.value = d.channels.dingtalk.webhook_url || '';
      var ww = document.getElementById('radar-wework');
      if (ww && d.channels.wework) ww.value = d.channels.wework.webhook_url || '';
      var tgToken = document.getElementById('radar-tg-token');
      if (tgToken && d.channels.telegram) tgToken.value = d.channels.telegram.bot_token || '';
      var tgChat = document.getElementById('radar-tg-chat');
      if (tgChat && d.channels.telegram) tgChat.value = d.channels.telegram.chat_id || '';
      var email = document.getElementById('radar-email');
      if (email && d.channels.email) email.value = d.channels.email.from || '';
    }

    // 推送控制
    var cbHotlist = document.getElementById('radar-disp-hotlist');
    if (cbHotlist) cbHotlist.checked = d.display.hotlist !== false;
    var cbRss = document.getElementById('radar-disp-rss');
    if (cbRss) cbRss.checked = d.display.rss !== false;
    var cbAi = document.getElementById('radar-disp-ai');
    if (cbAi) cbAi.checked = d.display.ai_analysis !== false;
    var cbNotify = document.getElementById('radar-notify');
    if (cbNotify) cbNotify.checked = d.notification.enabled !== false;
    var cbSchedule = document.getElementById('radar-schedule');
    if (cbSchedule) cbSchedule.checked = d.schedule.enabled === true;
    var cbAiFilter = document.getElementById('radar-aifilter');
    if (cbAiFilter) cbAiFilter.checked = d.ai_analysis.enabled !== false;
    var cbTranslate = document.getElementById('radar-translate');
    if (cbTranslate) cbTranslate.checked = d.ai_translation.enabled !== false;

    showToast('配置加载完成', 'success');
  }).catch(function(e){
    showToast('加载配置失败: ' + e.message, 'error');
  });
}

function radarOnPlatformToggle(cb) {
  var id = cb.getAttribute('data-radar-platform');
  var chip = cb.closest('.radar-platform-chip');
  if (chip) chip.style.borderColor = cb.checked ? '#6366f1' : '#e2e8f0';
  if (!window._radarConfigPending['_platforms']) window._radarConfigPending['_platforms'] = [];
  window._radarConfigPending['_platforms'].push({id: id, enabled: cb.checked});
}

function trendradarSaveConfig() {
  var p = window._radarConfigPending;
  var payload = { flat: {}, platforms: { sources: [] }, rss: { feeds: [] }, display: {}, channels: {} };

  // 扁平字段
  for (var k in p) {
    if (k.indexOf('_') === 0) continue;
    if (k.indexOf('.') > -1) payload.flat[k] = p[k];
  }

  // 平台开关
  if (p['_platforms']) {
    payload.platforms.sources = p['_platforms'];
  }

  // 频道
  if (p['_channels']) {
    payload.channels = p['_channels'];
  }

  // display
  ['display.hotlist','display.rss','display.ai_analysis'].forEach(function(k){
    if (p[k] !== undefined) {
      var dk = k.split('.')[1];
      payload.display[dk] = p[k];
    }
  });

  var btn = document.getElementById('radar-save-btn');
  if (btn) { btn.disabled = true; btn.textContent = '保存中...'; }

  fetch('/api/trendradar/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  }).then(function(r){ return r.json(); }).then(function(json){
    if (json.success) {
      showToast(json.message || '配置已保存', 'success');
      window._radarConfigPending = {};
    } else {
      showToast('保存失败: ' + (json.error || ''), 'error');
    }
    if (btn) { btn.disabled = false; btn.textContent = '💾 保存配置'; }
  }).catch(function(e){
    showToast('保存失败: ' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '💾 保存配置'; }
  });
}

function trendradarLoadLog() {
  fetch('/api/trendradar/log').then(function(r) { return r.json(); }).then(function(json) {
    var el = document.getElementById('radar-log');
    if (!el) return;
    if (json.success && json.data && json.data.length > 0) {
      el.textContent = json.data.join('\n');
      el.scrollTop = el.scrollHeight;
    } else if (json.running) {
      el.textContent = '正在启动...';
    } else {
      el.innerHTML = '<span style="color:#64748b;">暂无日志，点击"运行分析"后此处实时显示进度</span>';
    }
  }).catch(function() {});
}

function trendradarRefreshStatus() {
  fetch('/api/trendradar/status').then(function(r) { return r.json(); }).then(function(json) {
    var el = document.getElementById('radar-status');
    if (!el) return;
    if (json.success && json.data) {
      var d = json.data;
      var statusHtml = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;">';
      statusHtml += '<span>监控平台: <b style="color:#e2e8f0;">' + d.platforms + ' 个</b></span>';
      statusHtml += '<span>报告模式: <b style="color:#e2e8f0;">' + d.mode + '</b></span>';
      statusHtml += '<span>RSS: <b style="color:' + (d.rss_enabled ? '#4ade80' : '#64748b') + ';">' + (d.rss_enabled ? '已启用' : '未启用') + '</b></span>';
      statusHtml += '<span>AI分析: <b style="color:' + (d.ai_enabled ? '#4ade80' : '#64748b') + ';">' + (d.ai_enabled ? '已启用' : '未启用') + '</b></span>';
      statusHtml += '<span>通知: <b style="color:' + (d.notification_enabled ? '#4ade80' : '#64748b') + ';">' + (d.notification_enabled ? '已启用' : '未启用') + '</b></span>';
      if (d.running) statusHtml += '<span style="color:#f59e0b;">&#128260; 分析运行中...</span>';
      else if (d.last_run) statusHtml += '<span>上次运行: ' + d.last_run + '</span>';
      else statusHtml += '<span>尚未运行</span>';
      statusHtml += '</div>';
      el.innerHTML = statusHtml;
    } else {
      el.innerHTML = '<span style="color:#f87171;">状态加载失败: ' + (json.error || '未知') + '</span>';
    }
    trendradarLoadReports();
    trendradarLoadLog();
  }).catch(function(e) {
    var el = document.getElementById('radar-status');
    if (el) el.innerHTML = '<span style="color:#f87171;">连接失败: ' + e.message + '</span>';
  });
}

function trendradarRun() {
  var btn = document.querySelector('#panel-trendradar .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = '运行中...'; }
  showToast('热点分析任务已启动，请稍候...', 'info');
  var body = {};
  if (window._radarPromptVersionId) body.prompt_version_id = window._radarPromptVersionId;
  fetch('/api/trendradar/run', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) }).then(function(r) { return r.json(); }).then(function(json) {
    if (json.success) {
      showToast(json.message, 'success');
      var poll = setInterval(function() {
        trendradarLoadLog();
        fetch('/api/trendradar/status').then(function(r) { return r.json(); }).then(function(s) {
          if (s.success && s.data && !s.data.running) {
            clearInterval(poll);
            trendradarLoadLog();
            trendradarRefreshStatus();
            showToast('热点分析完成!', 'success');
          }
        });
      }, 3000);
    } else {
      showToast('启动失败: ' + (json.error || '未知错误'), 'error');
      if (btn) { btn.disabled = false; btn.textContent = '▶ 运行分析'; }
    }
  }).catch(function(e) {
    showToast('请求失败: ' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '▶ 运行分析'; }
  });
}

function trendradarLoadReports() {
  fetch('/api/trendradar/reports').then(function(r) { return r.json(); }).then(function(json) {
    var el = document.getElementById('radar-reports');
    if (!el) return;
    if (json.success && json.data && json.data.length > 0) {
      var html = '<div style="display:flex;flex-direction:column;gap:6px;">';
      json.data.forEach(function(r) {
        html += '<div class="radar-report-row" style="display:flex;align-items:center;gap:12px;padding:8px 12px;background:rgba(248,249,255,0.5);border-radius:8px;font-size:12px;">'
          + '<span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#1e293b;">' + r.name + '</span>'
          + '<span style="color:#94a3b8;white-space:nowrap;">' + r.mtime + '</span>'
          + '<span style="color:#94a3b8;white-space:nowrap;">' + (Math.round(r.size/1024)) + ' KB</span>'
          + '<button class="lc-copy-btn" onclick="trendradarViewReport(\'' + r.path + '\')" style="white-space:nowrap;">查看</button>'
          + '</div>';
      });
      html += '</div>';
      el.innerHTML = html;
    } else {
      el.innerHTML = '<span style="color:#94a3b8;font-size:12px;">暂无报告，点击上方"运行分析"开始</span>';
    }
  });
}

function trendradarViewReport(path) {
  var card = document.getElementById('radar-preview-card');
  var iframe = document.getElementById('radar-preview-iframe');
  if (card && iframe) {
    card.style.display = 'block';
    iframe.src = '/trendradar/report/' + encodeURI(path);
  }
}

function trendradarLoadPromptVersions() {
  fetch('/api/trendradar/prompts').then(function(r) { return r.json(); }).then(function(json) {
    var el = document.getElementById('radar-prompt-versions');
    if (!el) return;
    if (!json.success) {
      el.innerHTML = '<span style="color:#f87171;">加载失败: ' + (json.error || '未知') + '</span>';
      return;
    }
    var list = json.data || [];
    if (list.length === 0) {
      el.innerHTML = '<span style="color:#94a3b8;">暂无版本</span>';
      return;
    }
    // 默认选中最新一个版本（列表末尾）；只有原版时自然选中原版
    var selected = window._radarPromptVersionId;
    var exists = list.some(function(v) { return v.id === selected; });
    if (!exists) {
      selected = list[list.length - 1].id;
      window._radarPromptVersionId = selected;
    }
    var html = '';
    list.forEach(function(v) {
      var isDefault = !!v.is_default;
      var checked = (selected === v.id) ? ' checked' : '';
      var kw = v.keyword_count || 0;
      var src = v.rss_source_count || 0;
      var metaTxt = (kw || src) ? ('<span style="color:#64748b;font-size:11px;">关键词 ' + kw + ' · RSS 源 ' + src + '</span>') : '';
      html += '<div style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:rgba(248,249,255,0.5);border-radius:8px;border:1px solid #e2e8f0;">'
        + '<input type="radio" name="radar-prompt-version" value="' + v.id + '"' + checked + ' onchange="window._radarPromptVersionId=this.value" style="cursor:pointer;">'
        + '<span style="flex:1;display:flex;flex-direction:column;gap:2px;min-width:0;">'
        + '<span style="color:#1e293b;">' + (v.name || '未命名') + '</span>'
        + metaTxt
        + '</span>'
        + (isDefault ? '<span style="color:#6366f1;font-size:11px;">原版</span>' : '')
        + (isDefault ? '' : '<button onclick="trendradarDeletePrompt(\'' + v.id + '\')" style="background:none;border:none;color:#f87171;cursor:pointer;font-size:12px;">删除</button>')
        + '</div>';
    });
    el.innerHTML = html;
  }).catch(function(e) {
    var el = document.getElementById('radar-prompt-versions');
    if (el) el.innerHTML = '<span style="color:#f87171;">连接失败: ' + e.message + '</span>';
  });
}

function trendradarRewritePrompt() {
  var theme = (document.getElementById('radar-prompt-theme').value || '').trim();
  if (!theme) { showToast('请先输入调研主题', 'warning'); return; }
  var btn = document.getElementById('radar-rewrite-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'AI 重写中...'; }
  fetch('/api/trendradar/prompts/rewrite', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({theme: theme})
  }).then(function(r) { return r.json(); }).then(function(json) {
    if (json.success) {
      var nm = (json.data && json.data.name) ? json.data.name : theme;
      showToast('已生成定制版: ' + nm, 'success');
      if (json.data && json.data.id) window._radarPromptVersionId = json.data.id;
      document.getElementById('radar-prompt-theme').value = '';
      trendradarLoadPromptVersions();
    } else {
      showToast('生成失败: ' + (json.error || '未知错误'), 'error');
    }
  }).catch(function(e) {
    showToast('请求失败: ' + e.message, 'error');
  }).finally(function() {
    if (btn) { btn.disabled = false; btn.textContent = '🤖 AI 生成定制版'; }
  });
}

function trendradarDeletePrompt(id) {
  if (!confirm('确定删除该定制版提示词吗？')) return;
  fetch('/api/trendradar/prompts/' + id, { method: 'DELETE' }).then(function(r) { return r.json(); }).then(function(json) {
    if (json.success) {
      showToast('已删除', 'success');
      if (window._radarPromptVersionId === id) window._radarPromptVersionId = null;
      trendradarLoadPromptVersions();
    } else {
      showToast('删除失败: ' + (json.error || '未知错误'), 'error');
    }
  }).catch(function(e) {
    showToast('请求失败: ' + e.message, 'error');
  });
}

function doLogout() {
  fetch('/api/auth/logout', {method: 'POST'}).catch(function(){});
  window.currentBrandId = null;
  window.currentBrandName = '';
  window.currentUser = null;
  document.getElementById('login-page').classList.remove('hidden');
  document.getElementById('app-shell').classList.remove('active');
  document.getElementById('login-name').value = '';
  document.getElementById('login-password').value = '';
  showToast('已退出登录', 'warning');
}

// ==================== 用户权限管理（管理员） ====================
function loadAdminUsers() {
  var container = document.getElementById('admin-users-list');
  if (!container) return;
  container.innerHTML = '<div style="color:#94a3b8;font-size:12px;">加载中...</div>';
  fetch('/api/admin/users').then(function(r){ return r.json(); }).then(function(json){
    if (!json.success) {
      container.innerHTML = '<div style="color:#ef4444;font-size:12px;">' + (json.error || '加载失败') + '</div>';
      return;
    }
    var users = json.data || [];
    if (!users.length) {
      container.innerHTML = '<div style="color:#94a3b8;font-size:12px;">暂无用户</div>';
      return;
    }
    var html = '';
    users.forEach(function(u){
      var isAdmin = u.role === 'admin';
      html += '<div style="border:1px solid #e5e7eb;border-radius:10px;padding:14px;">';
      html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">';
      html += '<span style="font-weight:600;font-size:14px;">' + escapeHtml(u.username) + '</span>';
      html += '<span style="font-size:11px;padding:2px 10px;border-radius:20px;background:' + (isAdmin ? '#fef3c7' : '#e0e7ff') + ';color:' + (isAdmin ? '#92400e' : '#3730a3') + ';">' + (isAdmin ? '管理员' : '普通用户') + '</span>';
      html += '</div>';
      if (isAdmin) {
        html += '<div style="color:#94a3b8;font-size:12px;">管理员拥有全部功能权限，无需单独配置</div>';
      } else {
        html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
        AUTHORIZABLE_FEATURES.forEach(function(f){
          var on = (u.features || []).indexOf(f) >= 0;
          var label = panelTitles[f] || f;
          var st = 'display:inline-block;padding:5px 12px;border-radius:999px;border:1px solid;cursor:pointer;font-size:12px;transition:all .15s;';
          st += on ? 'background:#dcfce7;color:#166534;border-color:#86efac;' : 'background:#f1f5f9;color:#64748b;border-color:#e2e8f0;';
          html += '<button style="' + st + '" data-user="' + u.id + '" data-feature="' + f + '" data-on="' + (on ? '1' : '0') + '" onclick="toggleUserFeature(this)">' + escapeHtml(label) + '</button>';
        });
        html += '</div>';
      }
      html += '</div>';
    });
    container.innerHTML = html;
  }).catch(function(e){
    container.innerHTML = '<div style="color:#ef4444;font-size:12px;">加载失败: ' + escapeHtml(e.message) + '</div>';
  });
}

function toggleUserFeature(btn) {
  var userId = btn.getAttribute('data-user');
  var feature = btn.getAttribute('data-feature');
  var enabled = btn.getAttribute('data-on') === '1';
  fetch('/api/admin/users/' + userId + '/features', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({feature: feature, enabled: !enabled})
  }).then(function(r){ return r.json(); }).then(function(json){
    if (json.success) {
      var nowOn = !enabled;
      btn.setAttribute('data-on', nowOn ? '1' : '0');
      if (nowOn) {
        btn.style.background = '#dcfce7'; btn.style.color = '#166534'; btn.style.borderColor = '#86efac';
      } else {
        btn.style.background = '#f1f5f9'; btn.style.color = '#64748b'; btn.style.borderColor = '#e2e8f0';
      }
      showToast((nowOn ? '已开启' : '已取消') + '「' + (panelTitles[feature] || feature) + '」', 'success');
    } else {
      showToast('操作失败: ' + (json.error || '未知错误'), 'error');
    }
  }).catch(function(e){ showToast('请求错误: ' + e.message, 'error'); });
}

// 回车键登录支持
document.addEventListener('keydown', function(e){
  if (e.key === 'Enter' && !document.getElementById('app-shell').classList.contains('active')) {
    if (document.getElementById('login-form').classList.contains('active')) {
      doLogin();
    } else {
      doRegister();
    }
  }
});


// ==================== 视频混剪 ====================

var _mashupVideos = [];
var _mashupClassified = 0;
var _mashupBrand = null;       // 当前用户品牌（品牌=账户，一一对应）
var _mashupCurrentSkuId = '';

// ==================== SKU 选择 ====================
function mashupLoadSkus(afterLoad) {
  fetch('/api/brands')
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (!json.success) return;
      var brands = json.data || [];
      _mashupBrand = brands.length > 0 ? brands[0] : null;
      mashupRenderSkuGallery();
      if (typeof afterLoad === 'function') afterLoad();
    })
    .catch(function(e) {
      showToast('加载 SKU 失败: ' + e.message, 'error');
    });
}

function _mashupCurrentSku() {
  if (!_mashupBrand) return null;
  var skus = _mashupBrand.skus || [];
  for (var i = 0; i < skus.length; i++) {
    if (skus[i].id === _mashupCurrentSkuId) return skus[i];
  }
  return null;
}

// 渲染 SKU 封面画廊（每个 SKU 显示首帧封面 + 素材数量）
function mashupRenderSkuGallery() {
  var container = document.getElementById('mashup-sku-gallery');
  if (!container) return;

  if (!_mashupBrand) {
    container.innerHTML = '<div class="mashup-empty">暂无品牌，请先注册账号</div>';
    return;
  }
  var skus = _mashupBrand.skus || [];
  if (skus.length === 0) {
    container.innerHTML = '<div class="mashup-empty">暂无 SKU，点击右上角「新增 SKU」开始创建</div>';
    return;
  }

  var html = '<div class="mashup-sku-card mashup-sku-new" onclick="mashupAddSku()">'
    + '<div class="mashup-sku-new-icon">+</div>'
    + '<div class="mashup-sku-new-text">新增 SKU</div>'
    + '</div>';

  skus.forEach(function(s) {
    html += '<div class="mashup-sku-card" onclick="mashupOpenSku(\'' + s.id + '\')">'
      + '<div class="mashup-sku-cover" id="mashup-sku-cover-' + s.id + '">'
      +   '<div class="mashup-cover-loading">加载中…</div>'
      + '</div>'
      + '<div class="mashup-sku-meta">'
      +   '<span class="mashup-sku-name">' + escapeHtml(s.name) + '</span>'
      +   '<span class="mashup-sku-count" id="mashup-sku-count-' + s.id + '">…</span>'
      + '</div>'
      + '<div class="mashup-sku-actions">'
      +   '<button onclick="event.stopPropagation();mashupRenameSku(\'' + s.id + '\')" title="重命名">&#9998;</button>'
      +   '<button onclick="event.stopPropagation();mashupDeleteSku(\'' + s.id + '\')" title="删除">&times;</button>'
      + '</div>'
      + '</div>';
  });
  container.innerHTML = html;

  // 拉取每个 SKU 的视频，填充首帧封面与素材数量
  skus.forEach(function(s) {
    fetch('/api/videos/list?sku_id=' + encodeURIComponent(s.id))
      .then(function(r) { return r.json(); })
      .then(function(json) {
        var videos = (json.success && json.data) ? json.data : [];
        var countEl = document.getElementById('mashup-sku-count-' + s.id);
        var coverEl = document.getElementById('mashup-sku-cover-' + s.id);
        if (countEl) countEl.textContent = videos.length + ' 个素材';
        if (coverEl) {
          if (videos.length > 0) {
            coverEl.innerHTML = '<video src="/api/videos/stream/' + videos[0].id + '" muted preload="metadata" onloadedmetadata="this.currentTime=0.01"></video>';
          } else {
            coverEl.innerHTML = '<div class="mashup-cover-empty"><span class="mashup-cover-ic">&#127909;</span>暂无素材</div>';
          }
        }
      })
      .catch(function() {});
  });
}

// 打开 SKU 剪辑工作台
function mashupOpenSku(skuId) {
  _mashupCurrentSkuId = skuId;
  var gallery = document.getElementById('mashup-gallery-view');
  var detail = document.getElementById('mashup-detail-view');
  if (gallery) gallery.style.display = 'none';
  if (detail) detail.style.display = 'block';
  mashupApplySkuContext();
}

// 返回 SKU 封面画廊
function mashupBackToGallery() {
  var gallery = document.getElementById('mashup-gallery-view');
  var detail = document.getElementById('mashup-detail-view');
  if (detail) detail.style.display = 'none';
  if (gallery) gallery.style.display = 'block';
  mashupRenderSkuGallery();
}

function mashupSelectSku(skuId) {
  mashupOpenSku(skuId);
}

function mashupApplySkuContext() {
  var sku = _mashupCurrentSku();
  var nameEl = document.getElementById('mashup-detail-sku-name');
  if (nameEl) nameEl.textContent = sku ? sku.name : '—';
  mashupRefreshVideos();
  mashupRefreshResults();
}

function mashupAddSku() {
  var brandId = _mashupBrand ? _mashupBrand.id : '';
  if (!brandId) { showToast('暂无品牌，请先注册账号', 'warning'); return; }
  var name = prompt('请输入 SKU 名称');
  if (!name || !name.trim()) return;
  fetch('/api/brands/' + brandId + '/skus', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name.trim() })
  })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success) {
        showToast('SKU 已创建', 'success');
        _mashupCurrentSkuId = json.data.id;
        mashupLoadSkus(function() { mashupOpenSku(_mashupCurrentSkuId); });
      } else {
        showToast('创建失败: ' + (json.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) { showToast('请求失败: ' + e.message, 'error'); });
}

function mashupRenameSku(skuId) {
  if (!_mashupBrand) return;
  var sku = null;
  (_mashupBrand.skus || []).forEach(function(s) { if (s.id === skuId) sku = s; });
  if (!sku) return;
  var name = prompt('修改 SKU 名称', sku.name || '');
  if (!name || !name.trim()) return;
  fetch('/api/brands/' + _mashupBrand.id + '/skus/' + skuId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name.trim() })
  })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success) { showToast('已更新', 'success'); mashupLoadSkus(); }
      else showToast('更新失败: ' + (json.error || ''), 'error');
    })
    .catch(function(e) { showToast('请求失败: ' + e.message, 'error'); });
}

function mashupDeleteSku(skuId) {
  if (!_mashupBrand) return;
  if (!confirm('确定删除该 SKU 吗？其素材不会被删除。')) return;
  fetch('/api/brands/' + _mashupBrand.id + '/skus/' + skuId, { method: 'DELETE' })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success) {
        if (_mashupCurrentSkuId === skuId) _mashupCurrentSkuId = '';
        showToast('SKU 已删除', 'success');
        mashupLoadSkus();
      } else showToast('删除失败: ' + (json.error || ''), 'error');
    })
    .catch(function(e) { showToast('请求失败: ' + e.message, 'error'); });
}

// 打开文案弹窗
function mashupOpenScriptModal() {
  if (!_mashupCurrentSkuId) { showToast('请先选择 SKU', 'warning'); return; }
  if (_mashupClassified === 0) { showToast('请先上传素材并点击「AI 智能分类」', 'warning'); return; }
  var sku = _mashupCurrentSku();
  document.getElementById('mashup-modal-sku-label').textContent = sku ? ('· ' + sku.name) : '';
  document.getElementById('mashup-script').value = sku ? (sku.script || '') : '';
  mashupLoadVoices();
  document.getElementById('mashup-script-modal').style.display = 'flex';
}

function mashupCloseScriptModal() {
  document.getElementById('mashup-script-modal').style.display = 'none';
}

var _mashupVoicesLoaded = false;
var _mashupCloneAudio = '';
function mashupLoadVoices() {
  if (_mashupVoicesLoaded) return;
  fetch('/api/videos/tts/voices')
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (!json.success) return;
      var sel = document.getElementById('mashup-voice');
      if (!sel) return;
      var html = '<option value="auto">智能推荐（根据品牌调性自动匹配）</option>';
      (json.data || []).forEach(function(v) {
        html += '<option value="' + v.id + '">' + v.name + ' · ' + v.desc + '</option>';
      });
      sel.innerHTML = html;
      _mashupVoicesLoaded = true;
    })
    .catch(function() {});
}

function mashupUploadCloneAudio(file) {
  if (!file) return;
  var statusEl = document.getElementById('mashup-clone-status');
  if (statusEl) statusEl.textContent = '上传中...';
  var fd = new FormData();
  fd.append('file', file);
  var promptText = (document.getElementById('mashup-clone-prompt-text') || {}).value || '';
  fd.append('prompt_text', promptText);
  fetch('/api/videos/tts/clone-audio', { method: 'POST', body: fd })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success) {
        _mashupCloneAudio = json.path || '';
        if (statusEl) statusEl.textContent = '已上传：' + (json.filename || '');
        showToast('参考音频已上传，将用克隆音色配音', 'success');
      } else {
        _mashupCloneAudio = '';
        if (statusEl) statusEl.textContent = '上传失败';
        showToast('参考音频上传失败: ' + (json.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      _mashupCloneAudio = '';
      if (statusEl) statusEl.textContent = '上传失败';
      showToast('参考音频上传失败: ' + e.message, 'error');
    });
}

function mashupBatchStart() {
  var brandId = _mashupBrand ? _mashupBrand.id : '';
  if (!brandId) { showToast('暂无品牌', 'warning'); return; }
  var btn = document.getElementById('mashup-batch-btn');
  btn.textContent = '⏳ 批量提交中...';
  fetch('/api/videos/mashup-batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brand_id: brandId })
  })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      btn.textContent = '📦 批量混剪';
      if (json.success) {
        var msg = '已启动 ' + json.count + ' 个 SKU 混剪任务';
        if (json.skipped && json.skipped.length > 0) {
          msg += '，跳过 ' + json.skipped.length + ' 个';
          json.skipped.forEach(function(s) {
            showToast('跳过 ' + s.name + '：' + s.reason, 'warning');
          });
        }
        showToast(msg, 'success');
      } else {
        showToast('批量混剪失败: ' + (json.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      btn.textContent = '📦 批量混剪';
      showToast('请求失败: ' + e.message, 'error');
    });
}

// 设置混剪按钮启用/禁用样式（不用 disabled 属性，保证 onclick 始终触发以提供反馈）
function setMashupStartBtnEnabled(enabled) {
  var btn = document.getElementById('mashup-start-btn');
  if (enabled) {
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
    btn.style.pointerEvents = 'auto';
  } else {
    btn.style.opacity = '0.5';
    btn.style.cursor = 'not-allowed';
    btn.style.pointerEvents = 'auto';  // 保持可点击，以便触发 toast
  }
}

// 拖拽上传
function mashupHandleDrop(e) {
  e.preventDefault();
  var files = e.dataTransfer.files;
  if (files && files.length > 0) {
    mashupUploadFiles(files);
  }
}

// 上传视频文件
function mashupUploadFiles(files) {
  if (!files || files.length === 0) return;
  
  var skuId = _mashupCurrentSkuId;
  if (!skuId) {
    showToast('请先选择 SKU', 'warning');
    return;
  }
  
  var formData = new FormData();
  formData.append('sku_id', skuId);
  var count = 0;
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var ext = f.name.split('.').pop().toLowerCase();
    if (['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv'].indexOf(ext) >= 0) {
      formData.append('files', f);
      count++;
    }
  }
  
  if (count === 0) {
    showToast('请选择有效的视频文件', 'warning');
    return;
  }
  
  var progressEl = document.getElementById('mashup-status-text');
  progressEl.textContent = '正在上传 ' + count + ' 个视频...';
  
  fetch('/api/videos/upload', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      progressEl.textContent = '';
      if (json.success) {
        showToast('成功上传 ' + json.count + ' 个视频', 'success');
        document.getElementById('mashup-classify-btn').disabled = false;
        mashupRefreshVideos();
      } else {
        showToast('上传失败: ' + (json.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      progressEl.textContent = '';
      showToast('上传出错: ' + e.message, 'error');
    });
}

// 刷新视频列表（从后端拉取后交给渲染函数）
function mashupRefreshVideos() {
  var listEl = document.getElementById('mashup-video-list');
  var countEl = document.getElementById('mashup-video-count');
  var classifyBtn = document.getElementById('mashup-classify-btn');

  if (!_mashupCurrentSkuId) {
    _mashupVideos = [];
    _mashupClassified = 0;
    listEl.innerHTML = '<div class="mashup-empty">请先选择 SKU</div>';
    countEl.textContent = '';
    if (classifyBtn) classifyBtn.disabled = true;
    setMashupStartBtnEnabled(false);
    mashupUpdateDetailStats();
    return;
  }
  fetch('/api/videos/list?sku_id=' + encodeURIComponent(_mashupCurrentSkuId))
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (!json.success) return;
      _mashupVideos = json.data || [];
      _mashupClassified = 0;
      _mashupVideos.forEach(function(v) { if (v.classified) _mashupClassified++; });

      if (classifyBtn) classifyBtn.disabled = (_mashupVideos.length === 0);
      setMashupStartBtnEnabled(_mashupClassified > 0);
      mashupUpdateDetailStats();
      mashupRenderVideoList();
    });
}

// 更新详情页头部统计
function mashupUpdateDetailStats() {
  var vc = document.getElementById('mashup-detail-video-count');
  var cc = document.getElementById('mashup-detail-classified-count');
  if (vc) vc.textContent = _mashupVideos.length + ' 素材';
  if (cc) cc.textContent = _mashupClassified + ' 已分类';
}

// 渲染素材库（按搜索词过滤）
function mashupRenderVideoList() {
  var listEl = document.getElementById('mashup-video-list');
  var countEl = document.getElementById('mashup-video-count');
  if (!listEl) return;

  var kw = (document.getElementById('mashup-search-input').value || '').trim().toLowerCase();
  var aspect = (document.getElementById('mashup-aspect-filter').value || '').trim();

  if (!_mashupCurrentSkuId) {
    listEl.innerHTML = '<div class="mashup-empty">请先选择 SKU</div>';
    countEl.textContent = '';
    return;
  }

  var videos = _mashupVideos;
  if (kw) {
    videos = videos.filter(function(v) {
      var hay = [v.filename, v.topic, v.scene, v.style, v.mood, v.summary, v.error].join(' ').toLowerCase();
      return hay.indexOf(kw) >= 0;
    });
  }
  if (aspect) {
    videos = videos.filter(function(v) { return v.aspect_ratio === aspect; });
  }

  countEl.textContent = '(' + videos.length + '/' + _mashupVideos.length + ')';
  if (videos.length === 0) {
    listEl.innerHTML = '<div class="mashup-empty">' + (kw ? '没有匹配「' + escapeHtml(kw) + '」的素材' : '当前 SKU 暂无素材，请点击「上传素材」') + '</div>';
    return;
  }

  var html = '';
  videos.forEach(function(v) {
    var badgeCls = v.classified ? 'ok' : (v.error ? 'fail' : 'pending');
    var badgeText = v.classified ? '已分类' : (v.error ? '分类失败' : '待分类');

    var tagsHtml = '';
    if (v.classified) {
      var tags = [];
      if (v.topic) tags.push('<span class="mashup-tag" style="background:rgba(99,102,241,0.1);color:#6366f1;">' + escapeHtml(v.topic) + '</span>');
      if (v.scene) tags.push('<span class="mashup-tag" style="background:rgba(245,158,11,0.12);color:#d97706;">' + escapeHtml(v.scene) + '</span>');
      if (v.style) tags.push('<span class="mashup-tag" style="background:rgba(14,165,233,0.1);color:#0ea5e9;">' + escapeHtml(v.style) + '</span>');
      if (v.mood) tags.push('<span class="mashup-tag" style="background:rgba(236,72,153,0.1);color:#db2777;">' + escapeHtml(v.mood) + '</span>');
      tagsHtml = '<div class="mashup-video-tags">' + tags.join('') + '</div>';
    }

    html += '<div class="mashup-video-card">'
      + '<div class="mashup-video-thumb">'
      +   '<video src="/api/videos/stream/' + v.id + '" muted preload="metadata" onloadedmetadata="this.currentTime=0.01" onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0.01"></video>'
      +   '<span class="mashup-video-badge ' + badgeCls + '">' + badgeText + '</span>'
      +   '<button class="mashup-video-del" onclick="mashupDeleteVideo(\'' + v.id + '\')" title="删除">&times;</button>'
      +   (v.aspect_ratio ? '<span class="mashup-video-aspect">' + escapeHtml(v.aspect_ratio) + '</span>' : '')
      + '</div>'
      + '<div class="mashup-video-info">'
      +   '<div class="mashup-video-name" title="' + escapeHtml(v.filename) + '">' + escapeHtml(v.filename) + '</div>'
      +   (v.summary ? '<div class="mashup-video-summary">' + escapeHtml(v.summary) + '</div>' : '')
      +   (v.error ? '<div class="mashup-video-error">' + escapeHtml(v.error) + '</div>' : '')
      +   tagsHtml
      + '</div>'
      + '</div>';
  });
  listEl.innerHTML = html;
}

// 刷新当前 SKU 的混剪成品列表
function mashupRefreshResults() {
  var listEl = document.getElementById('mashup-result-list');
  var countEl = document.getElementById('mashup-result-count');
  if (!listEl) return;

  var skuId = _mashupCurrentSkuId;
  if (!skuId) {
    listEl.innerHTML = '<div class="mashup-empty">请先选择 SKU</div>';
    countEl.textContent = '';
    return;
  }

  fetch('/api/mashup/results?sku_id=' + encodeURIComponent(skuId))
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (!json.success) {
        listEl.innerHTML = '<div class="mashup-empty" style="color:#ef4444;">加载失败</div>';
        countEl.textContent = '';
        return;
      }
      var results = json.data || [];
      countEl.textContent = results.length > 0 ? '(' + results.length + ' 个成片)' : '';
      if (results.length === 0) {
        listEl.innerHTML = '<div class="mashup-empty">暂无成片，上传素材并完成剪辑后这里会展示</div>';
        return;
      }
      var html = '';
      results.forEach(function(r) {
        var dur = r.duration ? Math.round(r.duration) + ' 秒' : '';
        var time = (r.created_at || '').replace('T', ' ').slice(0, 16);
        html += '<div class="mashup-result-card">'
          + '<div class="mashup-result-thumb"><video src="/api/videos/mashup/play/' + r.task_id + '" muted preload="metadata" onloadedmetadata="this.currentTime=0.01" onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0.01"></video></div>'
          + '<div class="mashup-result-info">'
          +   '<div class="mashup-result-name">' + escapeHtml(r.sku_name || '成品') + (r.voice_name ? ' <span style="color:#0ea5e9;font-weight:400;">· ' + escapeHtml(r.voice_name) + '配音</span>' : '') + '</div>'
          +   '<div class="mashup-result-meta">' + escapeHtml(time) + (dur ? ' · ' + dur : '') + '</div>'
          +   (r.script ? '<div class="mashup-result-script">' + escapeHtml(r.script) + '</div>' : '')
          +   '<a class="btn btn-primary btn-xs" href="/api/videos/mashup/download/' + r.task_id + '" download>下载</a>'
          + '</div>'
          + '</div>';
      });
      listEl.innerHTML = html;
    })
    .catch(function(e) {
      listEl.innerHTML = '<div class="mashup-empty" style="color:#ef4444;">加载失败: ' + escapeHtml(e.message) + '</div>';
      countEl.textContent = '';
    });
}

// AI 智能分类（标签 + 时间线）
function mashupClassifyAll() {
  var btn = document.getElementById('mashup-classify-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 标签分析中...';
  
  fetch('/api/videos/classify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sku_id: _mashupCurrentSkuId || '' })
  })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      btn.disabled = false;
      btn.textContent = '🔍 AI 智能分类';
      
      if (json.success) {
        if (json.count > 0) {
          showToast('完成！标签分类 + 内容时间线分析完毕，共 ' + json.summary.success + ' 个视频', 'success');
        } else {
          showToast(json.message || '没有待分类的视频', 'warning');
        }
        mashupRefreshVideos();
      } else {
        showToast('分类失败: ' + (json.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      btn.disabled = false;
      btn.textContent = '🔍 AI 智能分类';
      showToast('分类出错: ' + e.message, 'error');
    });
}

// 开始混剪
var _mashupPollTimer = null;
var _mashupTaskId = null;
function mashupStart() {
  var skuId = _mashupCurrentSkuId;
  if (!skuId) {
    showToast('请先选择 SKU', 'warning');
    return;
  }
  var script = document.getElementById('mashup-script').value.trim();
  if (!script || script.length < 10) {
    showToast('请输入至少10个字的文案', 'warning');
    return;
  }
  var voice = (document.getElementById('mashup-voice') || {}).value || 'auto';
  var clonePromptText = (document.getElementById('mashup-clone-prompt-text') || {}).value || '';
  mashupCloseScriptModal();
  // 先保存文案到 SKU，再发起混剪
  var brandId = _mashupBrand ? _mashupBrand.id : '';
  fetch('/api/brands/' + brandId + '/skus/' + skuId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script: script })
  })
    .then(function() { _mashupStartTask(skuId, script, voice, _mashupCloneAudio, clonePromptText); })
    .catch(function() { _mashupStartTask(skuId, script, voice, _mashupCloneAudio, clonePromptText); });
}

function _mashupStartTask(skuId, script, voice, cloneAudio, clonePromptText) {
  if (_mashupClassified === 0) {
    showToast('请先上传素材并点击「AI 智能分类」', 'warning');
    return;
  }
  if (_mashupTaskId) {
    showToast('混剪任务正在进行中，请等待完成', 'warning');
    return;
  }

  // 停止之前的轮询
  if (_mashupPollTimer) { clearInterval(_mashupPollTimer); _mashupPollTimer = null; }

  var btn = document.getElementById('mashup-start-btn');
  var statusText = document.getElementById('mashup-status-text');
  setMashupStartBtnEnabled(false);
  btn.textContent = '⏳ 提交中...';
  statusText.textContent = '';

  fetch('/api/videos/mashup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script: script, sku_id: skuId, voice: voice || 'auto', clone_audio: cloneAudio || '', clone_prompt_text: clonePromptText || '' })
  })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success) {
        _mashupTaskId = json.task_id;

        // 保持按钮为 loading 状态
        btn.textContent = '🔄 混剪中...';
        btn.disabled = true;

        // 显示进度卡片并滚动到视口
        var card = document.getElementById('mashup-progress-card');
        card.style.display = 'block';
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // 重置进度条
        var bar = document.getElementById('mashup-progress-bar');
        bar.style.width = '0%';
        bar.style.background = 'linear-gradient(90deg,#6366f1,#8b5cf6)';
        document.getElementById('mashup-progress-text').textContent = '正在分析文案并匹配视频片段...';
        document.getElementById('mashup-segments-preview').innerHTML = '';
        document.getElementById('mashup-download-area').style.display = 'none';

        statusText.textContent = '';
        showToast('混剪任务已启动，正在处理中...', 'success');

        mashupPollStatus(json.task_id);
      } else {
        setMashupStartBtnEnabled(true);
        btn.textContent = '🎬 开始剪辑';
        showToast('启动失败: ' + (json.error || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      setMashupStartBtnEnabled(true);
      btn.textContent = '🎬 开始剪辑';
      showToast('请求失败: ' + e.message, 'error');
    });
}

// 轮询混剪状态
function mashupPollStatus(taskId) {
  if (_mashupPollTimer) clearInterval(_mashupPollTimer);
  
  _mashupPollTimer = setInterval(function() {
    fetch('/api/videos/mashup/status/' + taskId)
      .then(function(r) { return r.json(); })
      .then(function(json) {
        if (!json.success) return;
        var data = json.data;
        
        var bar = document.getElementById('mashup-progress-bar');
        var txt = document.getElementById('mashup-progress-text');
        var btn = document.getElementById('mashup-start-btn');
        bar.style.width = data.progress + '%';
        
        if (data.status === 'completed') {
          clearInterval(_mashupPollTimer);
          _mashupPollTimer = null;
          _mashupTaskId = null;
          
          txt.innerHTML = '✅ <b>混剪完成！</b>共 ' + data.result.segment_count + ' 个片段，总时长 ' + data.result.total_duration + 's'
            + (data.result.voice_name ? ' · 配音：' + data.result.voice_name : '');
          bar.style.width = '100%';
          bar.style.background = '#16a34a';
          
          setMashupStartBtnEnabled(true);
          btn.textContent = '🎬 开始剪辑';
          btn.disabled = false;
          document.getElementById('mashup-status-text').textContent = '';
          
          // 显示片段详情 - 视频预览 + 台词对照
          var segHtml = '<div style="display:flex;flex-direction:column;gap:12px;margin-top:12px;">';
          (data.result.segments || []).forEach(function(seg, i) {
            var segFile = seg.file.split('\\').pop().split('/').pop();  // seg_000.mp4
            var videoUrl = '/api/videos/mashup/segment/' + taskId + '/' + segFile;
            segHtml += '<div class="mashup-seg-card" style="display:flex;gap:12px;padding:10px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;align-items:flex-start;">'
              // 视频播放器
              + '<div style="flex-shrink:0;width:200px;min-height:112px;background:#000;border-radius:6px;overflow:hidden;">'
              +   '<video src="' + videoUrl + '" controls preload="metadata"'
              +     ' style="width:100%;height:auto;display:block;max-height:150px;"'
              +     ' onmouseenter="if(this.paused)this.play()" onmouseleave="this.pause()"'
              +     ' onloadedmetadata="this.currentTime=0.5">'
              +   '</video>'
              + '</div>'
              // 右侧信息
              + '<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:4px;font-size:12px;">'
              +   '<div style="display:flex;align-items:center;gap:6px;">'
              +     '<span style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border-radius:10px;padding:1px 8px;font-size:11px;font-weight:600;">镜头 ' + (i + 1) + '/' + data.result.segment_count + '</span>'
              +     '<span style="color:#94a3b8;">' + seg.duration + 's</span>'
              +   '</div>'
              +   '<div style="color:#1e293b;font-weight:600;font-size:13px;line-height:1.5;word-break:break-all;">' + seg.text + '</div>'
              +   '<div style="color:#94a3b8;font-size:11px;">来源: ' + seg.source_video + ' [' + seg.start_time + 's - ' + (seg.start_time + seg.duration).toFixed(1) + 's]</div>'
              +   (seg.voice_name ? '<div style="color:#0ea5e9;font-size:11px;">配音: ' + seg.voice_name + (seg.narration_duration ? ' · ' + seg.narration_duration + 's' : '') + '</div>' : '')
              +   (seg.reason ? '<div style="color:#6366f1;font-size:11px;">AI匹配: ' + seg.reason + '</div>' : '')
              +   (seg.timeline_desc ? '<div style="color:#64748b;font-size:11px;line-height:1.4;">' + seg.timeline_desc + '</div>' : '')
              + '</div>'
              + '</div>';
          });
          segHtml += '</div>';
          document.getElementById('mashup-segments-preview').innerHTML = segHtml;
          
          // 显示下载按钮
          var dlArea = document.getElementById('mashup-download-area');
          dlArea.style.display = 'block';
          var dlLink = document.getElementById('mashup-download-link');
          dlLink.href = '/api/videos/mashup/download/' + taskId;
          
          // 滚动到进度卡片
          document.getElementById('mashup-progress-card').scrollIntoView({ behavior: 'smooth', block: 'center' });
          showToast('混剪完成！点击下载按钮获取视频', 'success');
          // 刷新成品列表（后端入库略有延迟，稍后刷新）
          setTimeout(function(){ mashupRefreshResults(); }, 1200);
          
        } else if (data.status === 'failed') {
          clearInterval(_mashupPollTimer);
          _mashupPollTimer = null;
          _mashupTaskId = null;
          
          txt.innerHTML = '<span style="color:#ef4444;">❌ 混剪失败: ' + (data.error || '未知错误') + '</span>';
          bar.style.background = '#ef4444';
          bar.style.width = '100%';
          
          setMashupStartBtnEnabled(true);
          btn.textContent = '🎬 开始剪辑';
          btn.disabled = false;
          document.getElementById('mashup-status-text').textContent = '';
          showToast('混剪失败: ' + (data.error || '未知错误'), 'error');
          
        } else {
          // 动态进度文案
          var statusMsgs = {
            10: '正在拆分文案...',
            20: '正在构建视频库索引...',
            30: 'AI 正在分析语义匹配...',
            50: 'FFmpeg 正在截取视频片段...',
            80: '正在拼接最终视频...'
          };
          var msg = '处理中...';
          Object.keys(statusMsgs).sort(function(a,b){return b-a}).forEach(function(k) {
            if (data.progress >= parseInt(k) && msg === '处理中...') msg = statusMsgs[k];
          });
          txt.textContent = '⏳ ' + msg + ' (' + data.progress + '%)';
        }
      })
      .catch(function() {
        // 网络错误静默重试
      });
  }, 2000);
}

// 删除视频
function mashupDeleteVideo(videoId) {
  if (!confirm('确定删除该视频吗？')) return;
  
  fetch('/api/videos/delete/' + videoId, { method: 'DELETE' })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success) {
        showToast('已删除', 'success');
        mashupRefreshVideos();
      } else {
        showToast('删除失败: ' + (json.error || ''), 'error');
      }
    });
}

// 面板打开时自动刷新
(function() {
  var origSwitch = window.switchPanel;
  if (typeof origSwitch === 'function') {
    window.switchPanel = function(name) {
      origSwitch(name);
      if (name === 'mashup') {
        setTimeout(function() {
          var g = document.getElementById('mashup-gallery-view');
          var d = document.getElementById('mashup-detail-view');
          if (g) g.style.display = 'block';
          if (d) d.style.display = 'none';
          mashupLoadSkus();
        }, 200);
      }
      if (name === 'prompts') {
        setTimeout(promptLoadList, 200);
      }
      if (name === 'ai-clip') {
        setTimeout(aiClipCheckStatus, 200);
      }
    };
  }
})();


// ==================== AI 智能混剪 ====================
function aiClipCheckStatus() {
  var el = document.getElementById('aiclip-status');
  if (!el) return;
  fetch('/api/aiclip/status')
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.running) {
        el.innerHTML = '<span style="color:#16a34a;">&#9679; 服务已启动 · Smart-Clip MCP</span>';
        el.className = 'aiclip-status aiclip-on';
      } else {
        el.innerHTML = '<span style="color:#dc2626;">&#9679; 服务未启动</span>';
        el.className = 'aiclip-status aiclip-off';
      }
    })
    .catch(function() {
      el.innerHTML = '<span style="color:#dc2626;">&#9679; 服务未启动</span>';
      el.className = 'aiclip-status aiclip-off';
    });
}

function aiClipUpload(files) {
  if (!files || files.length === 0) return;
  var f = files[0];
  var fd = new FormData();
  fd.append('file', f);
  var status = document.getElementById('aiclip-upload-status');
  status.textContent = '上传中...';
  fetch('/api/aiclip/upload', { method: 'POST', body: fd })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success) {
        document.getElementById('aiclip-video-input').value = json.path || '';
        status.textContent = '已上传：' + (json.filename || '');
        showToast('视频已上传到剪辑服务', 'success');
      } else {
        status.textContent = '';
        showToast('上传失败: ' + (json.error || ''), 'error');
      }
    })
    .catch(function(e) { status.textContent = ''; showToast('上传出错: ' + e.message, 'error'); });
}

function aiClipStart() {
  var videoInput = (document.getElementById('aiclip-video-input').value || '').trim();
  if (!videoInput) { showToast('请先上传视频或填写视频路径/URL', 'warning'); return; }
  var btn = document.getElementById('aiclip-start-btn');
  var status = document.getElementById('aiclip-status-text');
  var resultCard = document.getElementById('aiclip-result-card');
  btn.disabled = true; btn.textContent = '⏳ 剪辑中...';
  status.textContent = '正在分析并剪辑，请稍候...';
  resultCard.style.display = 'none';
  document.getElementById('aiclip-result').innerHTML = '';

  var body = {
    video_input: videoInput,
    intent: (document.getElementById('aiclip-intent').value || '').trim(),
    clip_count: parseInt(document.getElementById('aiclip-count').value || '5', 10),
    clip_duration_min: parseInt(document.getElementById('aiclip-min').value || '15', 10),
    clip_duration_max: parseInt(document.getElementById('aiclip-max').value || '90', 10),
    platform: document.getElementById('aiclip-platform').value
  };

  fetch('/api/aiclip/clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      btn.disabled = false; btn.textContent = '🎬 开始智能剪辑';
      status.textContent = '';
      resultCard.style.display = 'block';
      if (json.success) {
        document.getElementById('aiclip-result').innerHTML = aiClipRenderResult(json.data);
        showToast('剪辑完成', 'success');
      } else {
        document.getElementById('aiclip-result').innerHTML = '<div style="color:#dc2626;font-size:13px;">' + escapeHtml(json.error || '剪辑失败') + '</div>';
        showToast('剪辑失败: ' + (json.error || ''), 'error');
      }
    })
    .catch(function(e) {
      btn.disabled = false; btn.textContent = '🎬 开始智能剪辑';
      status.textContent = '';
      resultCard.style.display = 'block';
      document.getElementById('aiclip-result').innerHTML = '<div style="color:#dc2626;font-size:13px;">请求失败: ' + escapeHtml(e.message) + '</div>';
    });
}

function aiClipRenderResult(data) {
  var obj = (typeof data === 'string') ? (function() { try { return JSON.parse(data); } catch(e) { return null; } })() : data;
  if (!obj) return '<pre style="font-size:12px;white-space:pre-wrap;">' + escapeHtml(String(data)) + '</pre>';

  var html = '';
  if (obj.analysis) {
    var a = obj.analysis;
    html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">'
      + '<span class="mashup-stat">总时长 ' + (a.total_duration || 0) + 's</span>'
      + '<span class="mashup-stat">语言 ' + escapeHtml(a.language || 'zh') + '</span>'
      + '<span class="mashup-stat accent">找到高光 ' + (a.highlights_found || 0) + '</span>'
      + '<span class="mashup-stat accent">已选 ' + (a.highlights_selected || 0) + '</span>'
      + '</div>';
  }
  var clips = obj.clips || [];
  if (clips.length) {
    html += '<div style="display:flex;flex-direction:column;gap:10px;">';
    clips.forEach(function(c) {
      var name = (c.output_path || '').split('\\').pop().split('/').pop();
      html += '<div style="display:flex;align-items:center;gap:12px;padding:10px 12px;border:1px solid var(--border);border-radius:10px;font-size:12px;">'
        + '<div style="flex:1;min-width:0;">'
        +   '<div style="font-weight:600;color:#1e293b;">片段 ' + ((c.index != null ? c.index : 0) + 1) + '</div>'
        +   '<div style="color:#94a3b8;">' + (c.start != null ? c.start.toFixed(1) : '0') + 's - ' + (c.end != null ? c.end.toFixed(1) : '0') + 's · ' + (c.duration != null ? c.duration.toFixed(1) + 's' : '') + '</div>'
        +   (c.reason ? '<div style="color:#94a3b8;margin-top:2px;">' + escapeHtml(c.reason) + '</div>' : '')
        + '</div>'
        + (name ? '<a class="btn btn-primary btn-xs" href="http://127.0.0.1:8000/output/' + encodeURIComponent(name) + '" target="_blank">下载</a>' : '')
        + '</div>';
    });
    html += '</div>';
  } else {
    html += '<div style="color:#94a3b8;font-size:13px;">' + escapeHtml(obj.error || '未生成片段') + '</div>';
  }
  return html;
}

// ==================== 生成剪辑方案（VideoPlan · V2.0） ====================
function aiClipGeneratePlan(opts) {
  opts = opts || {};
  var videoInput = (document.getElementById('aiclip-video-input').value || '').trim();
  if (!videoInput) { showToast('请先上传视频或填写视频路径/URL', 'warning'); return; }
  var btn = document.getElementById('aiclip-plan-btn');
  var status = document.getElementById('aiclip-status-text');
  var planCard = document.getElementById('aiclip-plan-card');
  btn.disabled = true; btn.textContent = '⏳ 生成中...';
  status.textContent = '正在分析并生成剪辑方案，请稍候...';
  planCard.style.display = 'block';
  document.getElementById('aiclip-plan-meta').style.display = 'none';
  document.getElementById('aiclip-plan-result').innerHTML = '<div style="color:#94a3b8;font-size:13px;padding:8px 0;">方案生成中，可能需要 30-90 秒...</div>';

  var body = {
    video_path: videoInput,
    intent: (document.getElementById('aiclip-intent').value || '').trim(),
    clip_count: parseInt(document.getElementById('aiclip-count').value || '5', 10),
    clip_duration_min: parseInt(document.getElementById('aiclip-min').value || '15', 10),
    clip_duration_max: parseInt(document.getElementById('aiclip-max').value || '90', 10)
  };
  if (opts.style) body.style = opts.style;
  if (opts.custom_style_config) body.custom_style_config = opts.custom_style_config;

  fetch('/api/aiclip/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      btn.disabled = false; btn.textContent = '⚡ 生成剪辑方案';
      status.textContent = '';
      if (json.success) {
        aiClipRenderPlan(json.video_plan, { video_plan_id: json.video_plan_id });
        if (!json.persist && json.persist_error) {
          showToast('方案已生成（未落库: ' + json.persist_error + '）', 'warning');
        } else {
          showToast('剪辑方案已生成并落库', 'success');
        }
      } else {
        document.getElementById('aiclip-plan-result').innerHTML = '<div style="color:#dc2626;font-size:13px;">' + escapeHtml(json.error || '方案生成失败') + '</div>';
        showToast('方案生成失败: ' + (json.error || ''), 'error');
      }
    })
    .catch(function(e) {
      btn.disabled = false; btn.textContent = '⚡ 生成剪辑方案';
      status.textContent = '';
      document.getElementById('aiclip-plan-result').innerHTML = '<div style="color:#dc2626;font-size:13px;">请求失败: ' + escapeHtml(e.message) + '</div>';
    });
}

function aiClipPlanRefresh() {
  aiClipGeneratePlan({});
}

function aiClipRenderPlan(plan, meta) {
  plan = plan || {};
  meta = meta || {};
  var resultEl = document.getElementById('aiclip-plan-result');
  var metaEl = document.getElementById('aiclip-plan-meta');

  // 元信息
  if (meta.video_plan_id) {
    metaEl.innerHTML = '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
      + '<span class="mashup-stat">方案ID ' + escapeHtml(meta.video_plan_id) + '</span>'
      + '</div>';
    metaEl.style.display = 'block';
  }

  var style = plan.style || {};
  var clips = plan.clips || [];
  var packaging = plan.packaging || {};
  var overview = plan.overview || {};
  var ma = plan.material_assets || {};
  var timeline = plan.timeline || [];
  var subSys = plan.subtitle_system || {};
  var effects = plan.effects || [];
  var rhythm = plan.rhythm_design || [];

  var SUB_COLOR = { '白字': '#e2e8f0', '黄字': '#f0d060', '蓝公式字': '#bfe3f2' };
  function subTag(s) {
    var c = SUB_COLOR[s] || '#e2e8f0';
    return '<span style="color:' + c + ';font-weight:600;">' + escapeHtml(s || '白字') + '</span>';
  }
  function secTitle(t) {
    return '<div style="font-weight:600;font-size:13px;color:#1e293b;margin:16px 0 8px;padding-left:8px;border-left:3px solid #7c3aed;">' + t + '</div>';
  }
  function kv(k, v) {
    if (v == null || v === '') return '';
    return '<div style="margin-bottom:4px;"><span style="color:#94a3b8;">' + k + '：</span><span style="color:#1e293b;">' + escapeHtml(String(v)) + '</span></div>';
  }

  var html = '';
  // 顶部概览
  html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">'
    + '<span class="mashup-stat accent">Style ' + escapeHtml(style.display_name || style.name || 'auto') + '</span>'
    + (timeline.length ? '<span class="mashup-stat">逐秒脚本 ' + timeline.length + ' 段</span>' : '')
    + '<span class="mashup-stat">高光片段 ' + clips.length + '</span>'
    + '</div>';

  // 一、整体分析 overview
  if (overview.video_type || overview.core_structure || overview.main_asset_desc || overview.duration_sec) {
    html += secTitle('一、整体分析');
    html += '<div style="padding:10px 12px;border:1px solid var(--border);border-radius:10px;font-size:12px;background:var(--bg);">'
      + kv('类型', overview.video_type)
      + kv('时长', overview.duration_sec != null ? overview.duration_sec + 's' : '')
      + kv('画幅', overview.aspect_ratio)
      + kv('核心结构', overview.core_structure)
      + kv('整体节奏', overview.rhythm_curve)
      + kv('主轴画面', overview.main_asset_desc)
      + '</div>';
  }

  // 二、素材清单 material_assets（A/B/C/D/E）
  var maGroups = [
    ['A_main', 'A 主口播（主轴）'],
    ['B_demo', 'B 动作演示插播'],
    ['C_contrast', 'C 前后对比佐证'],
    ['D_ui', 'D UI/截图素材'],
    ['E_sticker', 'E 贴纸/特效'],
  ];
  var hasMa = maGroups.some(function(g) { return (ma[g[0]] || []).length; });
  if (hasMa) {
    html += secTitle('二、素材清单（剪辑前需准备）');
    maGroups.forEach(function(g) {
      var items = ma[g[0]] || [];
      if (!items.length) return;
      html += '<div style="font-weight:600;font-size:12px;color:#7c3aed;margin:8px 0 4px;">' + g[1] + '</div>';
      html += '<div style="display:flex;flex-direction:column;gap:6px;">';
      items.forEach(function(it) {
        html += '<div style="padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:12px;background:var(--bg);">'
          + '<div style="color:#1e293b;"><b>' + escapeHtml(it.id || '') + '</b> ' + escapeHtml(it.desc || it.name || '') + '</div>'
          + kv('视角/机位', it.shot || it.camera)
          + kv('时长', it.duration)
          + kv('版式', it.layout)
          + kv('用途', it.usage)
          + kv('注意', it.notes)
          + '</div>';
      });
      html += '</div>';
    });
  }

  // 三、逐秒时间轴 timeline（核心）
  if (timeline.length) {
    html += secTitle('三、逐秒剪辑时间轴（' + timeline.length + ' 段）');
    html += '<div style="border:1px solid var(--border);border-radius:10px;overflow:hidden;">';
    timeline.forEach(function(t, i) {
      var sub = t.subtitle || {};
      html += '<div style="display:flex;gap:10px;padding:7px 10px;border-bottom:1px dashed var(--border);font-size:12px;'
        + (i === timeline.length - 1 ? '' : '')
        + (i % 2 === 1 ? 'background:rgba(148,163,184,0.06);' : '') + '">'
        + '<div style="width:64px;flex-shrink:0;color:#7c3aed;font-weight:600;font-variant-numeric:tabular-nums;">'
        +   (t.start != null ? t.start : '') + '-' + (t.end != null ? t.end : '') + 's'
        + '</div>'
        + '<div style="flex:1;min-width:0;">'
        +   '<div><b style="color:#1e293b;">' + escapeHtml(t.asset || '') + '</b>'
        +   (t.edit ? '<span style="color:#64748b;"> · ' + escapeHtml(t.edit) + '</span>' : '') + '</div>'
        +   (sub.text ? '<div style="color:#334155;margin-top:2px;">字幕：' + escapeHtml(sub.text) + ' <span style="font-size:11px;">(' + subTag(sub.style) + (sub.position ? '·' + escapeHtml(sub.position) : '') + ')</span></div>' : '')
        +   (t.audio ? '<div style="color:#94a3b8;font-size:11px;margin-top:1px;">音频：' + escapeHtml(t.audio) + '</div>' : '')
        + '</div>'
        + '</div>';
    });
    html += '</div>';
  }

  // 四、节奏设计 rhythm_design
  if (rhythm.length) {
    html += secTitle('四、节奏设计');
    html += '<div style="display:flex;flex-direction:column;gap:6px;">';
    rhythm.forEach(function(r) {
      html += '<div style="padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:12px;background:var(--bg);">'
        + '<b style="color:#1e293b;">' + escapeHtml(r.segment || '') + '</b> ' + escapeHtml(r.name || '')
        + kv('镜头节奏', r.pace) + kv('字幕策略', r.subtitle) + kv('音频策略', r.audio)
        + '</div>';
    });
    html += '</div>';
  }

  // 五、字幕规范 subtitle_system
  if (subSys.font_main || subSys.colors || subSys.position) {
    html += secTitle('五、字幕系统规范');
    var sc2 = subSys.colors || {};
    html += '<div style="padding:10px 12px;border:1px solid var(--border);border-radius:10px;font-size:12px;background:var(--bg);">'
      + kv('主字幕字体', subSys.font_main)
      + kv('公式字体', subSys.font_formula)
      + kv('普通配色', sc2.normal)
      + kv('重点配色', sc2.emphasis)
      + kv('公式配色', sc2.formula)
      + kv('位置', subSys.position)
      + kv('动画', subSys.animation)
      + kv('字号', subSys.font_size)
      + '</div>';
  }

  // 六、特效清单 effects
  if (effects.length) {
    html += secTitle('六、特效清单');
    html += '<div style="display:flex;flex-direction:column;gap:6px;">';
    effects.forEach(function(e) {
      html += '<div style="padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:12px;background:var(--bg);">'
        + '<b style="color:#1e293b;">' + escapeHtml(e.name || '') + '</b>'
        + (e.time ? '<span style="color:#7c3aed;"> · ' + escapeHtml(e.time) + '</span>' : '')
        + (e.desc ? '<div style="color:#64748b;margin-top:2px;">' + escapeHtml(e.desc) + '</div>' : '')
        + '</div>';
    });
    html += '</div>';
  }

  // 七、高光片段 clips（保留）
  if (clips.length) {
    html += secTitle('七、高光片段');
    html += '<div style="display:flex;flex-direction:column;gap:10px;">';
    clips.forEach(function(c, i) {
      var sc = c.scores || {};
      html += '<div style="padding:10px 12px;border:1px solid var(--border);border-radius:10px;font-size:12px;background:var(--bg);">'
        + '<div style="font-weight:600;color:#1e293b;">片段 ' + (i + 1) + ' · ' + escapeHtml(c.title || '') + '</div>'
        + '<div style="color:#94a3b8;">' + (c.start != null ? c.start.toFixed(1) : '0') + 's - ' + (c.end != null ? c.end.toFixed(1) : '0') + 's</div>'
        + (c.reason ? '<div style="color:#94a3b8;margin-top:2px;">' + escapeHtml(c.reason) + '</div>' : '')
        + (c.quote_text ? '<div style="color:#334155;margin-top:2px;">「' + escapeHtml(c.quote_text) + '」</div>' : '')
        + (c.suggested_hook ? '<div style="color:#7c3aed;margin-top:2px;">\uD83D\uDD17 Hook: ' + escapeHtml(c.suggested_hook) + '</div>' : '')
        + '<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;">'
        +   '<span class="mashup-stat">信息 ' + (sc.information_density || 0).toFixed(2) + '</span>'
        +   '<span class="mashup-stat">情绪 ' + (sc.emotional_tension || 0).toFixed(2) + '</span>'
        +   '<span class="mashup-stat">传播 ' + (sc.virality || 0).toFixed(2) + '</span>'
        +   '<span class="mashup-stat">节奏 ' + (sc.rhythm_fit || 0).toFixed(2) + '</span>'
        + '</div>'
        + '</div>';
    });
    html += '</div>';
  } else {
    html += '<div style="color:#94a3b8;font-size:13px;margin-bottom:12px;">未识别到高光片段</div>';
  }

  // 八、包装层 packaging（保留）
  var subs = packaging.subtitle_styles || [];
  if (subs.length) {
    html += secTitle('八、字幕样式（包装层）');
    html += '<div style="display:flex;flex-direction:column;gap:8px;">';
    subs.forEach(function(s) {
      var cfg = s.style || {};
      html += '<div style="padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:12px;background:var(--bg);">'
        + '<div style="color:#1e293b;font-weight:600;">' + escapeHtml(s.text || '') + '</div>'
        + '<div style="color:#94a3b8;margin-top:2px;">' + escapeHtml(cfg.font || '') + ' · ' + (cfg.size || '') + ' · ' + escapeHtml(cfg.color || '') + (cfg.effect ? ' · ' + escapeHtml(cfg.effect) : '') + (cfg.keywords && cfg.keywords.length ? ' · 高亮: ' + cfg.keywords.join(', ') : '') + '</div>'
        + '</div>';
    });
    html += '</div>';
  }

  if (packaging.bgm && packaging.bgm.track) {
    html += secTitle('BGM');
    html += '<div style="padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:12px;background:var(--bg);">'
      + '<div style="color:#1e293b;">' + escapeHtml(packaging.bgm.track) + ' · ' + escapeHtml(packaging.bgm.genre || '') + '</div>'
      + '</div>';
  }

  var sfx = packaging.sfx_events || [];
  if (sfx.length) {
    html += secTitle('音效触发');
    html += '<div style="display:flex;gap:6px;flex-wrap:wrap;">';
    sfx.forEach(function(e) {
      html += '<span class="mashup-stat">' + (e.time != null ? e.time.toFixed(1) + 's ' : '') + escapeHtml(e.category || e.type || 'sfx') + '·' + escapeHtml(e.intensity || e.strength || '') + '</span>';
    });
    html += '</div>';
  }

  var fx = packaging.effect_events || [];
  if (fx.length) {
    html += secTitle('画面特效');
    html += '<div style="display:flex;gap:6px;flex-wrap:wrap;">';
    fx.forEach(function(e) {
      html += '<span class="mashup-stat">' + (e.time != null ? e.time.toFixed(1) + 's ' : '') + escapeHtml(e.type || 'fx') + '</span>';
    });
    html += '</div>';
  }

  // 完整 JSON（可折叠）
  html += '<details style="margin-top:16px;"><summary style="cursor:pointer;font-size:13px;color:#334155;font-weight:600;">查看完整 VideoPlan JSON</summary>';
  html += '<pre style="font-size:11px;white-space:pre-wrap;background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;margin-top:8px;max-height:420px;overflow:auto;">' + escapeHtml(JSON.stringify(plan, null, 2)) + '</pre>';
  html += '</details>';

  resultEl.innerHTML = html;
}

// ==================== 素材获取（外部资源 → 视频可消费素材） ====================
// materialFetchBing / materialFetchPolicy / materialRenderText 三个端点：
//   - /api/aiclip/test-material  (imagedl · 46 个站点网络图片抓取)
//   - /api/aiclip/test-policyprint (gov.cn 政策文件采集, requests 版)
//   - /api/aiclip/materialize (文本/政策 txt → 竖屏卡片图 jpg/png, Pillow 渲染)

function materialFetchBing() {
  var btn = document.getElementById('aiclip-mat-btn');
  var statusEl = document.getElementById('aiclip-mat-status');
  var resultEl = document.getElementById('aiclip-mat-result');
  var kw = (document.getElementById('aiclip-mat-kw').value || '').trim();
  var source = document.getElementById('aiclip-mat-source').value || 'BingImageClient';
  var limit = parseInt(document.getElementById('aiclip-mat-limit').value, 10) || 6;

  if (!kw) {
    statusEl.innerHTML = '<span style="color:#ef4444;">请输入关键词</span>';
    return;
  }

  btn.disabled = true;
  btn.textContent = '搜索中…';
  statusEl.innerHTML = '<span style="color:#94a3b8;">通过 ' + escapeHtml(source) + ' 搜索 <b>' + escapeHtml(kw) + '</b>（' + limit + ' 张）…</span>';
  resultEl.innerHTML = '';

  fetch('/api/aiclip/test-material', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword: kw, source: source, limit: limit })
  })
  .then(function(r) { return r.json(); })
  .then(function(json) {
    btn.disabled = false;
    btn.innerHTML = '&#128300; 获取素材';
    if (!json.success) {
      statusEl.innerHTML = '<span style="color:#ef4444;">✗ ' + escapeHtml(json.error || '失败') + '</span>';
      resultEl.innerHTML = '';
      return;
    }
    statusEl.innerHTML = '<span style="color:#10b981;">✓ 命中 ' + json.count + ' / ' + json.limit +
      ' 张（' + json.elapsed_s + 's，' + escapeHtml(json.source_cn) + '）</span>';
    var items = json.items || [];
    if (!items.length) {
      resultEl.innerHTML = '<div style="grid-column:1/-1;color:#94a3b8;font-size:13px;">未下载到任何图片，请换关键词或换搜索源</div>';
      return;
    }
    var html = '';
    items.forEach(function(it) {
      html += '<a href="' + escapeHtml(it.web_path) + '" target="_blank" '
        + 'style="display:block;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:var(--bg);text-decoration:none;color:inherit;">'
        + '<img src="' + escapeHtml(it.web_path) + '" loading="lazy" '
        + 'style="width:100%;height:110px;object-fit:cover;display:block;background:#0f172a;" '
        + 'onerror="this.style.opacity=0.2" />'
        + '<div style="padding:4px 6px;font-size:10px;color:#94a3b8;line-height:1.3;">'
        +   escapeHtml((it.filename || '').slice(0, 18)) + '<br>'
        +   '<span style="color:#64748b;">' + Math.round((it.size || 0) / 1024) + ' KB</span>'
        + '</div>'
        + '</a>';
    });
    resultEl.innerHTML = html;
  })
  .catch(function(err) {
    btn.disabled = false;
    btn.innerHTML = '&#128300; 获取素材';
    statusEl.innerHTML = '<span style="color:#ef4444;">✗ 网络错误: ' + escapeHtml(String(err)) + '</span>';
  });
}

function materialFetchPolicy() {
  var btn = document.getElementById('aiclip-pp-btn');
  var statusEl = document.getElementById('aiclip-pp-status');
  var resultEl = document.getElementById('aiclip-pp-result');
  var kw = (document.getElementById('aiclip-pp-kw').value || '').trim();
  var limit = parseInt(document.getElementById('aiclip-pp-limit').value, 10) || 5;

  btn.disabled = true;
  btn.textContent = '抓取中…';
  statusEl.innerHTML = '<span style="color:#94a3b8;">从 gov.cn 政策首页抓取' + (kw ? '（关键词：<b>' + escapeHtml(kw) + '</b>）' : '（最新）') + '，最多 ' + limit + ' 条…</span>';
  resultEl.innerHTML = '';

  fetch('/api/aiclip/test-policyprint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword: kw, limit: limit })
  })
  .then(function(r) { return r.json(); })
  .then(function(json) {
    btn.disabled = false;
    btn.innerHTML = '&#128240; 获取政策文件';
    if (!json.success) {
      statusEl.innerHTML = '<span style="color:#ef4444;">✗ ' + escapeHtml(json.error || '失败') + '</span>';
      resultEl.innerHTML = '';
      return;
    }
    statusEl.innerHTML = '<span style="color:#10b981;">✓ 抓到 ' + json.count + ' / ' + json.limit +
      ' 份（共扫到 ' + json.total_links + ' 条链接，' + json.elapsed_s + 's）</span>';
    var items = json.items || [];
    if (!items.length) {
      resultEl.innerHTML = '<div style="color:#94a3b8;font-size:13px;">未抓到匹配文件，换关键词重试</div>';
      return;
    }
    var html = '';
    items.forEach(function(it) {
      html += '<div style="padding:10px 12px;border:1px solid var(--border);border-radius:10px;font-size:12px;">'
        + '<div style="font-weight:600;color:#1e293b;margin-bottom:4px;">' + escapeHtml(it.title || '(无标题)') + '</div>'
        + '<div style="color:#94a3b8;font-size:11px;margin-bottom:6px;word-break:break-all;">'
        +   escapeHtml(it.source_url || '') + '</div>'
        + '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">'
        +   '<a class="btn btn-primary btn-xs" href="' + escapeHtml(it.web_path) + '" target="_blank">&#128196; 打开正文</a>'
        +   '<span style="color:#64748b;font-size:11px;">' + Math.round((it.size || 0) / 1024) + ' KB</span>'
        + '</div>'
        + (it.preview ? '<div style="color:#64748b;font-size:11px;margin-top:6px;line-height:1.4;max-height:36px;overflow:hidden;">' + escapeHtml(it.preview) + '…</div>' : '')
        + '</div>';
    });
    resultEl.innerHTML = html;
  })
  .catch(function(err) {
    btn.disabled = false;
    btn.innerHTML = '&#128240; 获取政策文件';
    statusEl.innerHTML = '<span style="color:#ef4444;">✗ 网络错误: ' + escapeHtml(String(err)) + '</span>';
  });
}

function materialRenderText() {
  var btn = document.getElementById('aiclip-mt-btn');
  var statusEl = document.getElementById('aiclip-mt-status');
  var resultEl = document.getElementById('aiclip-mt-result');
  var text = (document.getElementById('aiclip-mt-text').value || '').trim();
  var file = (document.getElementById('aiclip-mt-file').value || '').trim();
  var title = (document.getElementById('aiclip-mt-title').value || '').trim();
  var tag = (document.getElementById('aiclip-mt-tag').value || '').trim();
  var style = document.getElementById('aiclip-mt-style').value || 'dark';
  var format = document.getElementById('aiclip-mt-format').value || 'png';
  var maxCards = parseInt(document.getElementById('aiclip-mt-max').value, 10) || 8;

  if (!text && !file) {
    statusEl.innerHTML = '<span style="color:#ef4444;">请粘贴文本或填写 txt 路径</span>';
    return;
  }

  btn.disabled = true;
  btn.textContent = '生成中…';
  statusEl.innerHTML = '<span style="color:#94a3b8;">正在渲染卡片图（' + escapeHtml(style) + ' / ' + escapeHtml(format) + '）…</span>';
  resultEl.innerHTML = '';

  var body = { style: style, format: format, max_cards: maxCards };
  if (text) body.text = text;
  if (file) body.file_path = file;
  if (title) body.title = title;
  if (tag) body.tag = tag;

  fetch('/api/aiclip/materialize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  .then(function(r) { return r.json(); })
  .then(function(json) {
    btn.disabled = false;
    btn.innerHTML = '&#128444; 生成图片素材';
    if (!json.success) {
      statusEl.innerHTML = '<span style="color:#ef4444;">✗ ' + escapeHtml(json.error || '失败') + '</span>';
      resultEl.innerHTML = '';
      return;
    }
    statusEl.innerHTML = '<span style="color:#10b981;">✓ 生成 ' + json.count + ' 张 ' +
      json.width + '×' + json.height + ' ' + escapeHtml((json.format || '').toUpperCase()) +
      '（' + json.elapsed_s + 's）</span>';
    var items = json.items || [];
    if (!items.length) {
      resultEl.innerHTML = '<div style="grid-column:1/-1;color:#94a3b8;font-size:13px;">未生成任何图片</div>';
      return;
    }
    var html = '';
    items.forEach(function(it) {
      html += '<a href="' + escapeHtml(it.web_path) + '" target="_blank" '
        + 'style="display:block;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:var(--bg);text-decoration:none;color:inherit;">'
        + '<img src="' + escapeHtml(it.web_path) + '" loading="lazy" '
        + 'style="width:100%;aspect-ratio:9/16;object-fit:cover;display:block;background:#0f172a;" '
        + 'onerror="this.style.opacity=0.2" />'
        + '<div style="padding:4px 6px;font-size:10px;color:#94a3b8;line-height:1.3;">'
        +   '#' + it.index + ' ' + escapeHtml((it.snippet || '').slice(0, 14))
        + '</div>'
        + '</a>';
    });
    resultEl.innerHTML = html;
  })
  .catch(function(err) {
    btn.disabled = false;
    btn.innerHTML = '&#128444; 生成图片素材';
    statusEl.innerHTML = '<span style="color:#ef4444;">✗ 网络错误: ' + escapeHtml(String(err)) + '</span>';
  });
}

// ==================== AI 提示词管理 ====================

function promptLoadList() {
  fetch('/api/prompts')
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (!json.success) return;
      var sel = document.getElementById('prompt-select');
      sel.innerHTML = '<option value="">-- 选择提示词文件 --</option>';
      (json.files || []).forEach(function(f) {
        sel.innerHTML += '<option value="' + f.id + '">' + f.name + ' (' + (f.size / 1024).toFixed(1) + ' KB)</option>';
      });
    });
}

function promptLoad() {
  var filename = document.getElementById('prompt-select').value;
  if (!filename) {
    document.getElementById('prompt-editor').value = '';
    document.getElementById('prompt-info').textContent = '';
    return;
  }
  document.getElementById('prompt-editor').value = '加载中...';
  fetch('/api/prompts/' + encodeURIComponent(filename))
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success) {
        document.getElementById('prompt-editor').value = json.content;
        document.getElementById('prompt-info').textContent = json.name + ' - 已加载';
      } else {
        document.getElementById('prompt-editor').value = '';
        showToast('加载失败: ' + (json.error || ''), 'error');
      }
    })
    .catch(function(e) {
      document.getElementById('prompt-editor').value = '';
      showToast('请求失败: ' + e.message, 'error');
    });
}

function promptSave() {
  var filename = document.getElementById('prompt-select').value;
  if (!filename) {
    showToast('请先选择一个文件', 'warning');
    return;
  }
  var content = document.getElementById('prompt-editor').value;
  var btn = document.getElementById('prompt-save-btn');
  btn.textContent = '保存中...';
  btn.disabled = true;
  
  fetch('/api/prompts/' + encodeURIComponent(filename), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: content })
  })
    .then(function(r) { return r.json(); })
    .then(function(json) {
      btn.textContent = '💾 保存';
      btn.disabled = false;
      if (json.success) {
        showToast(json.message, 'success');
        document.getElementById('prompt-info').textContent = filename + ' - 已保存';
      } else {
        showToast('保存失败: ' + (json.error || ''), 'error');
      }
    })
    .catch(function(e) {
      btn.textContent = '💾 保存';
      btn.disabled = false;
      showToast('请求失败: ' + e.message, 'error');
    });
}

// ==================== 刷新自动恢复登录态 ====================
(function() {
  fetch('/api/auth/me')
    .then(function(r) { return r.json(); })
    .then(function(json) {
      if (json.success && json.user) {
        enterApp(json.user);
      }
    })
    .catch(function() { /* 未登录，保持登录页 */ });
})();

// ==================== 行业趋势报告（量化模型） ====================
function trendLoadLog() {
  fetch('/api/trend/log').then(function(r) { return r.json(); }).then(function(json) {
    var el = document.getElementById('trend-log');
    if (!el) return;
    if (json.success && json.data && json.data.length > 0) {
      el.textContent = json.data.join('\n');
      el.scrollTop = el.scrollHeight;
    } else {
      el.innerHTML = '<span style="color:#64748b;">暂无日志，点击"运行分析"后此处实时显示进度</span>';
    }
  }).catch(function() {});
}

function trendLoadConfig() {
  fetch('/api/trend/config').then(function(r) { return r.json(); }).then(function(json) {
    var el = document.getElementById('trend-meta');
    if (!el) return;
    if (json.success && json.data) {
      var d = json.data;
      var w = d.weights || {};
      var t = d.thresholds || {};
      var html = '<b>权重：</b>增长动能 ' + (w.growth_momentum || 0) + ' · 受众质量 ' + (w.audience_quality || 0)
        + ' · 风格迁移 ' + (w.style_migration || 0) + ' · 可行性 ' + (w.feasibility || 0)
        + ' · 噪声惩罚 ' + (w.noise_decay || 0) + '<br>';
      html += '<b>阈值：</b>高潜力 &gt;' + (t.high_potential || 0) + ' · 观察 ' + (t.watch || 0) + '~' + (t.high_potential || 0)
        + ' · 成熟 ' + (t.mature || 0) + '~' + (t.watch || 0) + ' · 衰退 &lt;' + (t.mature || 0);
      if (d.keywords && d.keywords.length) {
        html += '<br><b>默认关键词：</b>' + d.keywords.join('、');
        var inp = document.getElementById('trend-keywords');
        if (inp && !inp.value) inp.value = d.keywords.join(',');
      }
      el.innerHTML = html;
    } else {
      el.innerHTML = '<span style="color:#f87171;">配置加载失败: ' + (json.error || '') + '</span>';
    }
  }).catch(function(e) {
    var el = document.getElementById('trend-meta');
    if (el) el.innerHTML = '<span style="color:#f87171;">连接失败: ' + e.message + '</span>';
  });
}

function trendRun() {
  var inp = document.getElementById('trend-keywords');
  var kw = inp ? inp.value.trim() : '';
  if (!kw) { showToast('请输入趋势关键词', 'error'); return; }
  var btn = document.querySelector('#panel-trend .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = '运行中...'; }
  document.getElementById('trend-results').innerHTML = '';
  showToast('趋势分析任务已启动，请稍候...', 'info');
  fetch('/api/trend/batch', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({keywords: kw})
  }).then(function(r) { return r.json(); }).then(function(json) {
    if (!json.success) {
      showToast('启动失败: ' + (json.error || '未知错误'), 'error');
      if (btn) { btn.disabled = false; btn.textContent = '▶ 运行分析'; }
      return;
    }
    var taskId = json.data.task_id;
    var poll = setInterval(function() {
      trendLoadLog();
      fetch('/api/trend/status/' + taskId).then(function(r) { return r.json(); }).then(function(s) {
        if (!s.success) { clearInterval(poll); return; }
        var st = s.data;
        var statusEl = document.getElementById('trend-status');
        if (statusEl && st.message) {
          statusEl.innerHTML = '<b style="color:#e2e8f0;">' + st.status + '</b> · ' + escapeHtml(st.message);
        }
        if (st.status === 'completed' || st.status === 'failed') {
          clearInterval(poll);
          trendLoadLog();
          if (btn) { btn.disabled = false; btn.textContent = '▶ 运行分析'; }
          if (st.status === 'completed') {
            fetch('/api/trend/result/' + taskId).then(function(r) { return r.json(); }).then(function(res) {
              if (res.success) trendRenderResults(res.data);
            });
            showToast('趋势分析完成!', 'success');
          } else {
            showToast('分析失败: ' + (st.message || '未知'), 'error');
          }
        }
      });
    }, 3000);
  }).catch(function(e) {
    showToast('请求失败: ' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '▶ 运行分析'; }
  });
}

function trendRenderResults(results) {
  var el = document.getElementById('trend-results');
  if (!el) return;
  if (!results || !results.length) {
    el.innerHTML = '<div class="card"><span style="color:#94a3b8;font-size:12px;">暂无结果</span></div>';
    return;
  }
  var html = '<div style="display:flex;flex-direction:column;gap:14px;">';
  results.forEach(function(r) {
    var g = r.group_scores || {};
    var score = r.trend_score || 0;
    var scoreColor = score > 0.75 ? '#16a34a' : (score > 0.55 ? '#f59e0b' : (score > 0.35 ? '#64748b' : '#ef4444'));
    var d = r.data_summary || {};
    html += '<div class="card">';
    html += '<div class="card-header" style="align-items:center;">'
      + '<span class="icon accent">&#127891;</span>'
      + '<span style="font-weight:600;">' + escapeHtml(r.trend_name || '') + '</span>'
      + '<span style="margin-left:auto;font-size:18px;font-weight:700;color:' + scoreColor + ';">' + score.toFixed(3) + '</span>'
      + '<span style="margin-left:8px;font-size:11px;padding:2px 8px;border-radius:10px;background:#eef2ff;color:#4f46e5;">' + escapeHtml(r.lifecycle || '') + '</span>'
      + '</div>';
    var factors = [
      ['增长动能', g.growth_momentum, '#6366f1'],
      ['受众质量', g.audience_quality, '#8b5cf6'],
      ['风格迁移', g.style_migration, '#ec4899'],
      ['可行性', g.feasibility, '#0ea5e9'],
      ['噪声衰减', g.noise_decay, '#ef4444']
    ];
    html += '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:10px 0;">';
    factors.forEach(function(f) {
      var v = (f[1] == null ? 0.5 : f[1]);
      var pct = Math.max(0, Math.min(100, Math.round(v * 100)));
      html += '<div style="font-size:11px;">'
        + '<div style="display:flex;justify-content:space-between;color:#94a3b8;"><span>' + f[0] + '</span><span>' + v.toFixed(2) + '</span></div>'
        + '<div style="height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden;margin-top:3px;"><div style="width:' + pct + '%;height:100%;background:' + f[2] + ';"></div></div>'
        + '</div>';
    });
    html += '</div>';
    html += '<div style="font-size:12px;color:#475569;line-height:1.7;">';
    html += '<div><b>数据：</b>抖音 ' + (d.douyin_works || 0) + ' 条 · 淘宝 ' + (d.taobao_products || 0) + ' 件 · B站 ' + (d.bilibili_works || 0) + ' 条 · 供应商 ' + (d.suppliers || 0) + '</div>';
    html += '<div><b>爆发窗口：</b>' + escapeHtml(r.burst_window || '-') + '</div>';
    html += '<div><b>立项动作：</b>' + escapeHtml(r.action || '-') + '</div>';
    html += '<div><b>高客单建议：</b>' + escapeHtml(r.high_end_advice || '-') + '</div>';
    if (r.risks && r.risks.length) {
      html += '<div style="color:#dc2626;"><b>风险：</b>' + r.risks.map(escapeHtml).join('；') + '</div>';
    }
    if (r.material_keywords && r.material_keywords.length) {
      html += '<div><b>素材关键词：</b>' + r.material_keywords.map(escapeHtml).join('、') + '</div>';
    }
    if (r.error) html += '<div style="color:#dc2626;"><b>错误：</b>' + escapeHtml(r.error) + '</div>';
    html += '</div>';
    html += '</div>';
  });
  html += '</div>';
  el.innerHTML = html;
}
