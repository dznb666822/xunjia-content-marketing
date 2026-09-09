// ==================== AI 漫剧设计中心 ====================
var comicDesignId = null;
var comicResults = { art_result: '', storyboard_result: '', video_result: '' };

var COMIC_STAGES = [
  { key: 'art', field: 'art_result', url: '/api/comic/art', name: '美术视觉资产', desc: '角色 / 场景 / 道具设定提示词' },
  { key: 'storyboard', field: 'storyboard_result', url: '/api/comic/storyboard', name: '专业分镜表', desc: '镜号 / 景别 / 运镜 / 台词 / 音效' },
  { key: 'video', field: 'video_result', url: '/api/comic/video', name: '分镜图 + 视频提示词', desc: 'T2I 起始帧 + Seedance 提示词' }
];

// ---------- 视图切换 ----------
function comicShowList() {
  document.getElementById('comic-list-view').style.display = '';
  document.getElementById('comic-edit-view').style.display = 'none';
  loadComicHistory();
}

function comicShowEdit(title) {
  document.getElementById('comic-list-view').style.display = 'none';
  document.getElementById('comic-edit-view').style.display = '';
  if (title) document.getElementById('comic-edit-title').textContent = title;
}

// 新增设计：进入编辑视图并清空
function comicNewDesign() {
  comicClearInput();
  comicShowEdit('新增漫剧设计');
}

// ---------- 输入 ----------
function comicReadFile(file) {
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    showToast('文件过大（超过 2MB），请拆分后再上传', 'error');
    return;
  }
  var reader = new FileReader();
  reader.onload = function (e) {
    document.getElementById('comic-script-input').value = e.target.result;
    showToast('已载入: ' + file.name, 'success');
  };
  reader.onerror = function () { showToast('文件读取失败', 'error'); };
  reader.readAsText(file, 'utf-8');
}

function comicClearInput() {
  document.getElementById('comic-script-input').value = '';
  comicDesignId = null;
  comicResults = { art_result: '', storyboard_result: '', video_result: '' };
  comicResetUI();
}

function comicResetUI() {
  document.getElementById('comic-stage-progress').style.display = 'none';
  document.getElementById('comic-stage-progress').innerHTML = '';
  document.getElementById('comic-results').innerHTML =
    '<div style="text-align:center;padding:60px 20px;color:var(--text-hint);">' +
    '粘贴或上传剧本后点击「一键生成全套」<br>' +
    '<small style="color:var(--text-dim);">三个阶段的结果将依次呈现在这里</small></div>';
}

// ---------- 一键工作流 ----------
function comicRunAll() {
  var script = document.getElementById('comic-script-input').value.trim();
  if (!script) { showToast('请先粘贴剧本或上传 .txt 文件', 'error'); return; }
  if (script.length < 50) { showToast('剧本内容太短，至少需要 50 字', 'error'); return; }
  comicShowEdit('生成中 · ' + (comicDesignId ? '继续生成' : '新增漫剧设计'));

  comicDesignId = null;
  comicResults = { art_result: '', storyboard_result: '', video_result: '' };

  // 初始化进度区与结果区
  var progress = document.getElementById('comic-stage-progress');
  progress.style.display = 'block';
  var pHtml = '';
  for (var i = 0; i < COMIC_STAGES.length; i++) {
    var s = COMIC_STAGES[i];
    pHtml += '<div id="comic-stage-' + s.key + '" style="display:flex;align-items:center;gap:8px;padding:7px 10px;margin-bottom:6px;border-radius:var(--radius-tag);background:var(--bg-subtle);font-size:12px;color:var(--text-hint);">' +
      '<span class="comic-stage-dot" id="comic-stage-dot-' + s.key + '"></span>' +
      '<b style="color:var(--text-secondary);">阶段' + (i + 1) + ' · ' + s.name + '</b>' +
      '<span style="flex:1;"></span>' +
      '<span id="comic-stage-status-' + s.key + '">等待中</span></div>';
  }
  progress.innerHTML = pHtml;
  document.getElementById('comic-results').innerHTML = '';

  comicRunStage(0, script);
}

function comicSetStage(key, status, errorMsg) {
  var row = document.getElementById('comic-stage-' + key);
  var dot = document.getElementById('comic-stage-dot-' + key);
  var statusEl = document.getElementById('comic-stage-status-' + key);
  if (!row || !dot || !statusEl) return;
  row.style.background = status === 'done' ? 'rgba(16,185,129,0.08)'
    : status === 'running' ? 'rgba(99,102,241,0.10)'
    : status === 'failed' ? 'rgba(239,68,68,0.08)' : 'var(--bg-subtle)';
  dot.className = 'comic-stage-dot ' + (status === 'done' ? 'done' : status === 'running' ? 'running' : status === 'failed' ? 'failed' : '');
  statusEl.textContent = status === 'running' ? '生成中…' : status === 'done' ? '完成' : status === 'failed' ? ('失败: ' + (errorMsg || '')) : '等待中';
}

function comicRunStage(index, script) {
  if (index >= COMIC_STAGES.length) {
    spinner('spinner-comic', false);
    showToast('全部阶段生成完成', 'success');
    comicShowEdit('生成完成');
    loadComicHistory();
    return;
  }
  var stage = COMIC_STAGES[index];
  spinner('spinner-comic', true);
  comicSetStage(stage.key, 'running');

  fetch(stage.url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ design_id: comicDesignId, script_text: script })
  })
    .then(function (resp) { return resp.json(); })
    .then(function (json) {
      if (json.success) {
        comicDesignId = json.data.design_id;
        comicResults[stage.field] = json.data[stage.field] || '';
        comicSetStage(stage.key, 'done');
        comicRenderStage(stage, index);
        comicRunStage(index + 1, script);
      } else {
        spinner('spinner-comic', false);
        comicSetStage(stage.key, 'failed', json.error || '未知错误');
        showToast('「' + stage.name + '」生成失败: ' + (json.error || '未知错误'), 'error');
        loadComicHistory();
      }
    })
    .catch(function (e) {
      spinner('spinner-comic', false);
      comicSetStage(stage.key, 'failed', e.message);
      showToast('请求失败: ' + e.message, 'error');
    });
}

// ---------- 结果渲染 ----------
function comicRenderStage(stage, index, container, idPrefix) {
  container = container || document.getElementById('comic-results');
  var text = comicResults[stage.field] || '';
  var sectionId = (idPrefix || 'comic-section-') + stage.key;

  var html = '<div id="' + sectionId + '" style="border:1px solid var(--border);border-radius:var(--radius-card);overflow:hidden;background:rgba(248,249,255,0.5);">';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:rgba(180,195,230,0.15);">';
  html += '<div><span style="font-weight:600;font-size:13px;color:var(--color-accent-text);">阶段' + (index + 1) + ' · ' + escapeHtml(stage.name) + '</span>';
  html += '<span style="font-size:11px;color:var(--text-hint);margin-left:10px;">' + escapeHtml(stage.desc) + '</span></div>';
  html += '<button class="btn btn-primary btn-xs" onclick="comicCopyField(\'' + stage.field + '\')">&#128203; 一键复制</button>';
  html += '</div>';
  html += '<div class="comic-md-body">' + comicRenderMarkdown(text) + '</div>';
  html += '</div>';

  var existing = document.getElementById(sectionId);
  if (existing) existing.outerHTML = html;
  else container.insertAdjacentHTML('beforeend', html);
}

// 轻量 markdown 渲染（标题/表格/列表/引用/加粗/代码）
function comicInline(s) {
  return escapeHtml(s)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/\*([^*]+)\*/g, '<i>$1</i>')
    .replace(/`([^`]+)`/g, '<code style="background:var(--bg-subtle);padding:1px 5px;border-radius:4px;font-size:11px;">$1</code>');
}

function comicRenderMarkdown(text) {
  if (!text) return '<div style="padding:20px;color:var(--text-hint);text-align:center;">暂无内容</div>';
  var lines = String(text).replace(/\r\n/g, '\n').split('\n');
  var html = [];
  var tableBuf = [];

  function flushTable() {
    if (!tableBuf.length) return;
    var rows = [];
    for (var t = 0; t < tableBuf.length; t++) {
      var line = tableBuf[t].trim();
      if (/^\|[\s:\-|]+\|?$/.test(line)) continue; // 分隔行
      var cells = line.replace(/^\|/, '').replace(/\|$/, '').split('|');
      for (var c = 0; c < cells.length; c++) cells[c] = cells[c].trim();
      rows.push(cells);
    }
    if (rows.length) {
      var out = '<div style="overflow-x:auto;"><table class="comic-md-table"><thead><tr>';
      for (var c = 0; c < rows[0].length; c++) out += '<th>' + comicInline(rows[0][c]) + '</th>';
      out += '</tr></thead><tbody>';
      for (var r = 1; r < rows.length; r++) {
        out += '<tr>';
        for (var c = 0; c < rows[r].length; c++) out += '<td>' + comicInline(rows[r][c]) + '</td>';
        out += '</tr>';
      }
      out += '</tbody></table></div>';
      html.push(out);
    }
    tableBuf = [];
  }

  for (var i = 0; i < lines.length; i++) {
    var trimmed = lines[i].trim();
    if (trimmed.charAt(0) === '|') { tableBuf.push(trimmed); continue; }
    flushTable();
    if (!trimmed) continue;
    var h = trimmed.match(/^#{1,6}\s+(.*)$/);
    if (h) { html.push('<div class="comic-md-h">' + comicInline(h[1]) + '</div>'); continue; }
    if (/^(---+|===+|\*\*\*+)$/.test(trimmed)) { html.push('<div class="comic-md-hr"></div>'); continue; }
    if (trimmed.charAt(0) === '>') { html.push('<div class="comic-md-quote">' + comicInline(trimmed.replace(/^>\s?/, '')) + '</div>'); continue; }
    if (/^[-*•]\s+/.test(trimmed)) { html.push('<div class="comic-md-li">• ' + comicInline(trimmed.replace(/^[-*•]\s+/, '')) + '</div>'); continue; }
    if (/^\d+[.、]\s+/.test(trimmed)) { html.push('<div class="comic-md-li">' + comicInline(trimmed) + '</div>'); continue; }
    html.push('<div class="comic-md-p">' + comicInline(trimmed) + '</div>');
  }
  flushTable();
  return html.join('');
}

// ---------- 复制 ----------
function comicCopyField(field) {
  comicCopyText(comicResults[field] || '', '该阶段暂无内容');
}

function comicCopyAll() {
  var parts = [];
  for (var i = 0; i < COMIC_STAGES.length; i++) {
    var s = COMIC_STAGES[i];
    if (comicResults[s.field]) {
      parts.push('===== 阶段' + (i + 1) + ' · ' + s.name + ' =====\n\n' + comicResults[s.field]);
    }
  }
  if (!parts.length) { showToast('暂无可复制的内容', 'error'); return; }
  comicCopyText(parts.join('\n\n---\n\n'), '暂无可复制的内容');
}

function comicCopyText(text, emptyMsg) {
  if (!text) { showToast(emptyMsg || '暂无内容', 'error'); return; }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () {
      showToast('已复制到剪贴板', 'success');
    }, function () { comicCopyFallback(text); });
  } else {
    comicCopyFallback(text);
  }
}

function comicCopyFallback(text) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    showToast('已复制到剪贴板', 'success');
  } catch (e) {
    showToast('复制失败，请手动选择复制', 'error');
  }
  document.body.removeChild(ta);
}

// ---------- 历史（卡片网格） ----------
function loadComicHistory() {
  var container = document.getElementById('comic-cards-grid');
  if (!container) return;
  fetch('/api/comic/history')
    .then(function (resp) { return resp.json(); })
    .then(function (json) {
      if (!json.success) {
        container.innerHTML = '<div style="text-align:center;padding:50px 20px;color:var(--text-hint);grid-column:1/-1;">加载失败</div>';
        return;
      }
      var data = json.data || [];
      // 第一张固定为「新增」卡片（与其他卡片同尺寸）
      var html = '<div class="comic-card comic-card-new" onclick="comicNewDesign()">' +
        '<div class="comic-card-new-icon">＋</div>' +
        '<div class="comic-card-new-text">新增漫剧设计</div>' +
        '<div class="comic-card-new-hint">上传小说 / 粘贴剧本</div></div>';
      for (var i = 0; i < data.length; i++) {
        var d = data[i];
        var time = (d.updated_at || '').substring(0, 16).replace('T', ' ');
        var badges = '';
        if (d.has_art) badges += '<span class="comic-badge">美术</span>';
        if (d.has_storyboard) badges += '<span class="comic-badge">分镜</span>';
        if (d.has_video) badges += '<span class="comic-badge">视频</span>';
        html += '<div class="comic-card" onclick="showComicDetail(\'' + d.id + '\')">' +
          '<div class="comic-card-title">' + escapeHtml(d.title || '未命名') + '</div>' +
          '<div class="comic-card-meta">' + escapeHtml(time) + '</div>' +
          '<div class="comic-card-badges">' + badges + '</div>' +
          '<button class="btn btn-secondary btn-xs comic-card-del" onclick="event.stopPropagation();deleteComicDesign(\'' + d.id + '\')">&#128465; 删除</button>' +
          '</div>';
      }
      container.innerHTML = html;
    })
    .catch(function (e) {
      container.innerHTML = '<div style="text-align:center;padding:50px 20px;color:var(--text-hint);grid-column:1/-1;">加载失败: ' + e.message + '</div>';
    });
}

// ---------- 详情悬浮窗 ----------
function closeComicModal() {
  document.getElementById('comic-detail-modal').style.display = 'none';
}

function showComicDetail(designId) {
  var body = document.getElementById('comic-modal-body');
  var tabs = document.getElementById('comic-modal-tabs');
  body.innerHTML = '<div style="text-align:center;padding:60px 20px;color:var(--text-hint);">加载中...</div>';
  tabs.innerHTML = '';
  document.getElementById('comic-modal-title').textContent = '加载中...';
  document.getElementById('comic-detail-modal').style.display = '';

  fetch('/api/comic/' + encodeURIComponent(designId))
    .then(function (resp) { return resp.json(); })
    .then(function (json) {
      if (!json.success) {
        body.innerHTML = '<div style="text-align:center;padding:60px 20px;color:var(--text-hint);">加载失败: ' + escapeHtml(json.error || '') + '</div>';
        return;
      }
      var d = json.data || {};
      comicDesignId = d.id;
      comicResults = {
        art_result: d.art_result || '',
        storyboard_result: d.storyboard_result || '',
        video_result: d.video_result || ''
      };
      document.getElementById('comic-modal-title').textContent = d.title || '未命名漫剧';

      // 阶段标签页 + 内容面板（每个阶段独立复制按钮）
      tabs.innerHTML = '';
      body.innerHTML = '';
      var available = [];
      for (var i = 0; i < COMIC_STAGES.length; i++) {
        if (!comicResults[COMIC_STAGES[i].field]) continue;
        available.push(COMIC_STAGES[i]);
      }
      if (!available.length) {
        body.innerHTML = '<div style="text-align:center;padding:60px 20px;color:var(--text-hint);">该设计暂无生成结果</div>';
        return;
      }
      for (var j = 0; j < available.length; j++) {
        var st = available[j];
        var stageIndex = COMIC_STAGES.indexOf(st);
        // 标签按钮
        var tabBtn = document.createElement('button');
        tabBtn.className = 'comic-tab' + (j === 0 ? ' active' : '');
        tabBtn.id = 'comic-tab-' + st.key;
        tabBtn.innerHTML = '阶段' + (stageIndex + 1) + ' · ' + escapeHtml(st.name);
        tabBtn.setAttribute('onclick', 'comicSwitchTab(\'' + st.key + '\')');
        tabs.appendChild(tabBtn);
        // 内容面板（默认显示第一个）
        var panel = document.createElement('div');
        panel.id = 'comic-panel-' + st.key;
        panel.style.display = j === 0 ? '' : 'none';
        body.appendChild(panel);
        comicRenderStage(st, stageIndex, panel, 'comic-modal-sec-');
      }
      // 切换到第一个标签
      if (available.length) comicSwitchTab(available[0].key);
    })
    .catch(function (e) {
      body.innerHTML = '<div style="text-align:center;padding:60px 20px;color:var(--text-hint);">请求失败: ' + escapeHtml(e.message) + '</div>';
    });
}

// 切换阶段标签页
function comicSwitchTab(key) {
  var tabBtns = document.querySelectorAll('#comic-modal-tabs .comic-tab');
  for (var i = 0; i < tabBtns.length; i++) {
    tabBtns[i].classList.toggle('active', tabBtns[i].id === 'comic-tab-' + key);
  }
  var panels = document.querySelectorAll('#comic-modal-body > div[id^="comic-panel-"]');
  for (var j = 0; j < panels.length; j++) {
    panels[j].style.display = panels[j].id === 'comic-panel-' + key ? '' : 'none';
  }
  // 切换后回到顶部
  document.getElementById('comic-modal-body').scrollTop = 0;
}

function deleteComicDesign(designId) {
  if (!confirm('确定删除这条设计记录吗？')) return;
  fetch('/api/comic/' + encodeURIComponent(designId), { method: 'DELETE' })
    .then(function (resp) { return resp.json(); })
    .then(function (json) {
      if (json.success) {
        showToast('已删除', 'success');
        if (comicDesignId === designId) { comicClearInput(); closeComicModal(); }
        loadComicHistory();
      } else {
        showToast('删除失败: ' + (json.error || ''), 'error');
      }
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

// ESC 关闭详情悬浮窗
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    var modal = document.getElementById('comic-detail-modal');
    if (modal && modal.style.display !== 'none') closeComicModal();
  }
});
