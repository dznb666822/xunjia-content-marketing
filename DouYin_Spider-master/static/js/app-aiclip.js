// ==================== AI 智能剪辑（P1：项目 + 素材） ====================
// 范式照抄 static/js/app-comic.js：list-view / detail-view 双视图切换 + 卡片网格。
// 状态机直接读 DB：projects.status / progress / current_step，前端不自造枚举。

var aiclipProjectId = null;
var aiclipProject = null;
var aiclipMaterials = [];
var aiclipStepsSchema = [];
var aiclipKinds = [];
var aiclipProjects = [];   // 列表页的项目数据，创作流程台要用
var acHeadTitle = '';      // 项目头标题覆盖（新建时显示「新建剪辑项目」，否则取项目名）
var acPanelOpen = false;   // 项目设置区是否展开（详情页取消后，改名/换片型收进这里）

var AC_KIND_LABEL = { oral: '口播型', storyboard: '分镜型' };
var AC_STATUS_LABEL = {
  draft: '草稿', assets_importing: '导入中', assets_ready: '素材就绪',
  script_ready: '剧本就绪', reference_ready: '参考脚本就绪',
  compiled: '已编译', rendered: '已成片'
};

// ---------- 小工具 ----------
function acFmtSize(b) {
  b = Number(b) || 0;
  if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB';
  if (b >= 1024) return (b / 1024).toFixed(0) + ' KB';
  return b + ' B';
}

function acFmtDur(sec) {
  sec = Number(sec) || 0;
  if (sec <= 0) return '—';
  if (sec < 60) return sec.toFixed(sec < 10 ? 1 : 0) + 's';
  var m = Math.floor(sec / 60), s = Math.round(sec % 60);
  return m + '分' + (s < 10 ? '0' : '') + s + '秒';
}

function acFmtTime(iso) {
  if (!iso) return '';
  return String(iso).replace('T', ' ').substring(5, 16);
}

// 帧率：非标准/VFR 素材真实平均帧率会长这样（如 36.7783），显示到 1 位小数即可，
// 整数帧率（24/25/30/50/60）照常显示整数 —— 一眼能看出「这条不是标准帧率」。
function acFmtFps(fps) {
  var n = Number(fps) || 0;
  if (!n) return '';
  return (Math.abs(n - Math.round(n)) < 0.05 ? Math.round(n) : Math.round(n * 10) / 10) + 'fps';
}

function acEl(id) { return document.getElementById(id); }

// ---------- 视图切换 ----------
// 模块有四种视图：① 我的项目（列表）② 素材子页 ③ 参考脚本生成子页 ④ TTS 语音子页。
// ★ 2026-09-17 重构：原来是「列表 → 一个 5688px 的长详情页（左栏概况+步骤条 / 右栏三张卡）」，
//   爸爸的反馈是「总往下滑看上去有点奇怪」→ 拆成子页，导航点一下换一屏。
//   左栏（项目概况 + 步骤条）整块取消：「不要这个详情页了」。
//   项目上下文改由 #aiclip-page-head 一条细带承载，各子页共用。
// ★ 同日晚追加 ④ TTS 语音：「请你再给加一个子页面用来生成 tts 的语音」+
//   「在参考脚本生成下面得有一个导出 需要生成 tts 语音的文案或者台词」
//   → 「导出」按钮长在 ③ 的按钮区，产物（一镜一段的台词清单）落到 ④。
//   AC_PAGES 是 key → DOM id 的唯一映射：加一屏 = 改这里 + AC_NAV + index.html。
var AC_PAGES = { assets: 'aiclip-page-assets', reference: 'aiclip-page-reference',
                 tts: 'aiclip-page-tts' };

function acHidePages() {
  Object.keys(AC_PAGES).forEach(function (k) {
    var el = acEl(AC_PAGES[k]);
    if (el) el.style.display = 'none';
  });
  var head = acEl('aiclip-page-head');
  if (head) head.style.display = 'none';
}

function aiclipShowList() {
  acHidePages();
  acEl('aiclip-list-view').style.display = '';
  aiclipProjectId = null;
  aiclipProject = null;
  acHeadTitle = '';
  acPanelOpen = false;
  acNavActive = 'projects';   // 导航栏跟着回到「我的项目」
  aiclipRenderNav();          // ★ 必须在这里渲染：面板是「按需 display 切换」，不是重新加载页面，
                              //   不主动渲染的话列表页的导航栏就是空的（实测 count=0）
  loadAiclipProjects();
}

/** 切到某个子页（key = AC_NAV 的 key）。只换屏，不重拉接口。 */
function aiclipShowPage(key) {
  var item = acNavByKey(key);
  if (!item || !item.page) return;
  acEl('aiclip-list-view').style.display = 'none';
  Object.keys(AC_PAGES).forEach(function (k) {
    var el = acEl(AC_PAGES[k]);
    if (el) el.style.display = (AC_PAGES[k] === item.page ? '' : 'none');
  });
  acRenderPageHead();
  acNavSetActive(key);
  acNavHint();
  // 切回来时用**缓存**重渲一次（不再请求接口）：保证跨页联动的数字是最新的 ——
  // 例如参考脚本页那个「导出 TTS 台词（N 段）」要跟 TTS 页的段数一致。
  if (key === 'reference' && aiclipReference) aiclipRenderReference();
  if (key === 'tts' && aiclipTts) aiclipRenderTts();
}

/** 项目上下文条：项目名 + 片型/状态/素材数 + 进度 + 「项目设置」/「返回项目列表」 */
function acRenderPageHead() {
  var box = acEl('aiclip-page-head');
  if (!box) return;
  box.style.display = '';
  var p = aiclipProject || {};
  var name = acHeadTitle || p.name || '加载中…';
  var h = '<div class="ac-ph-row">' +
    '<span class="ac-ph-title"><span class="icon accent">&#9986;</span>' +
    '<span id="aiclip-detail-title">' + escapeHtml(name) + '</span></span>' +
    '<span class="ac-badge">' + escapeHtml(AC_KIND_LABEL[p.kind] || '') + '</span>' +
    (p.status ? '<span class="ac-badge">' + escapeHtml(AC_STATUS_LABEL[p.status] || '') + '</span>' : '') +
    (p.id ? '<span class="ac-badge">素材 ' + (p.material_count || 0) + '</span>' : '') +
    (p.id ? '<span class="ac-ph-bar"><i style="width:' + (p.progress || 0) + '%;"></i></span>' : '') +
    '<span class="ac-ph-actions">' +
    (p.id ? '<button class="btn btn-secondary btn-xs" onclick="acToggleProjectPanel()">&#9881; 项目设置</button>' : '') +
    '<button class="btn btn-secondary btn-xs" onclick="aiclipShowList()">&#8592; 返回项目列表</button>' +
    '</span></div>' +
    '<div id="aiclip-project-panel" class="ac-ph-panel"' + (acPanelOpen ? '' : ' style="display:none;"') + '></div>';
  box.innerHTML = h;
  // 设置区内容不是每次都要重建（展开状态下重渲染会把用户正在填的输入框清掉）
  if (p.id && acPanelOpen && !acEl('aiclip-project-panel').innerHTML) {
    acEl('aiclip-project-panel').innerHTML = acProjectInfoHtml(p);
  }
}

/** 「⚙ 项目设置」：默认收起 —— 详情页取消了，但改名/换片型/看 ID 这些还得有个去处 */
function acToggleProjectPanel() {
  var el = acEl('aiclip-project-panel');
  if (!el) return;
  acPanelOpen = !acPanelOpen;
  el.style.display = acPanelOpen ? '' : 'none';
  if (acPanelOpen && !el.innerHTML && aiclipProject) {
    el.innerHTML = acProjectInfoHtml(aiclipProject);
  }
}

// ---------- 项目列表 ----------
function loadAiclipProjects() {
  var grid = acEl('aiclip-cards-grid');
  if (!grid) return;
  fetch('/api/aiclip/projects')
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) {
        grid.innerHTML = '<div style="text-align:center;padding:50px 20px;color:var(--text-hint);grid-column:1/-1;">加载失败: ' + escapeHtml(json.error || '') + '</div>';
        return;
      }
      aiclipStepsSchema = json.steps_schema || [];
      aiclipKinds = json.kinds || [];
      aiclipProjects = json.data || [];
      var list = aiclipProjects;
      var html = acNewCardHtml();
      for (var i = 0; i < list.length; i++) {
        html += acProjectCardHtml(list[i]);
      }
      if (!list.length) {
        html += '<div style="grid-column:1/-1;padding:6px 2px;font-size:12px;color:var(--text-hint);">' +
          '还没有项目 —— 点左边那张虚线卡片建第一个。项目会把「剧本 → 素材 → 参考脚本 → 方案 → 成片」整条链路串起来。</div>';
      }
      grid.innerHTML = html;
    })
    .catch(function (e) {
      grid.innerHTML = '<div style="text-align:center;padding:50px 20px;color:var(--text-hint);grid-column:1/-1;">请求失败: ' + escapeHtml(e.message) + '</div>';
    });
}

function acNewCardHtml() {
  return '<div class="ac-card ac-card-new" onclick="aiclipNewProject()">' +
    '<div class="ac-card-new-icon">＋</div>' +
    '<div class="ac-card-new-text">新建剪辑项目</div>' +
    '<div class="ac-card-new-hint">选片型 → 导入素材</div></div>';
}

function acProjectCardHtml(p) {
  var kindCls = p.kind === 'oral' ? 'ac-badge ac-badge-oral' : 'ac-badge';
  var html = '<div class="ac-card" onclick="aiclipOpenProject(\'' + p.id + '\')">';
  html += '<div class="ac-card-title">' + escapeHtml(p.name || '未命名') + '</div>';
  html += '<div class="ac-card-meta">' + escapeHtml(AC_STATUS_LABEL[p.status] || p.status || '') +
    ' · ' + escapeHtml(acFmtTime(p.updated_at)) + '</div>';
  html += '<div class="ac-card-badges">';
  html += '<span class="' + kindCls + '">' + escapeHtml(AC_KIND_LABEL[p.kind] || p.kind || '') + '</span>';
  html += '<span class="ac-badge">素材 ' + (p.material_count || 0) + '</span>';
  if (p.material_count) {
    html += '<span class="ac-badge ' + (p.probed_count >= p.material_count ? 'ac-badge-ok' : '') + '">体检 ' +
      (p.probed_count || 0) + '/' + p.material_count + '</span>';
  }
  html += '</div>';
  html += '<div class="ac-card-bar"><i style="width:' + (p.progress || 0) + '%;"></i></div>';
  html += '<button class="btn btn-secondary btn-xs ac-card-del" onclick="event.stopPropagation();aiclipDeleteProject(\'' +
    p.id + '\',\'' + escapeHtml(p.name || '') + '\')">&#128465; 删除</button>';
  html += '</div>';
  return html;
}

// ---------- 新建项目 ----------
function aiclipNewProject() {
  aiclipProjectId = null;
  aiclipProject = null;
  aiclipMaterials = [];
  acHeadTitle = '新建剪辑项目';
  acPanelOpen = true;                    // 创建表单就在设置区里，必须展开
  acNavActive = 'assets';
  aiclipShowPage('assets');
  acEl('aiclip-project-panel').innerHTML = acCreateFormHtml();
  acEl('aiclip-materials-panel').innerHTML =
    '<div style="padding:26px 14px;text-align:center;color:var(--text-hint);font-size:12px;">' +
    '先把项目建出来，再导素材</div>';
}

function acCreateFormHtml() {
  var html = '<div class="form-group"><label class="form-label">项目名称</label>' +
    '<input type="text" id="aiclip-new-name" placeholder="例如：洁耳液 30 秒带货 / 耳净 分镜版"></div>';
  html += '<div class="form-group"><label class="form-label">片型（决定中游用哪套编译规则）</label><div class="ac-kind-row">';
  for (var i = 0; i < aiclipKinds.length; i++) {
    var k = aiclipKinds[i];
    var checked = k.value === 'storyboard' ? ' checked' : '';
    html += '<label class="ac-kind"><input type="radio" name="aiclip-kind" value="' + k.value + '"' + checked + '>' +
      '<span><b>' + escapeHtml(k.label) + '</b><i>' + escapeHtml(k.desc) + '</i></span></label>';
  }
  html += '</div></div>';
  html += '<div class="btn-group"><button class="btn btn-primary" onclick="aiclipCreateProject()">创建项目</button>' +
    '<button class="btn btn-secondary" onclick="aiclipShowList()">返回列表</button></div>';
  return html;
}

function aiclipCreateProject() {
  var name = (acEl('aiclip-new-name').value || '').trim();
  if (!name) { showToast('请填项目名', 'error'); return; }
  var kindEl = document.querySelector('input[name="aiclip-kind"]:checked');
  fetch('/api/aiclip/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name, kind: kindEl ? kindEl.value : 'storyboard' })
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast('创建失败: ' + (json.error || ''), 'error'); return; }
      showToast('项目已创建', 'success');
      aiclipOpenProject(json.data.id);
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

function aiclipDeleteProject(pid, name) {
  if (!confirm('确定删除项目「' + name + '」吗？\n（素材是全库资产，会保留；只解除与本项目的引用）')) return;
  fetch('/api/aiclip/projects/' + encodeURIComponent(pid), { method: 'DELETE' })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast('删除失败: ' + (json.error || ''), 'error'); return; }
      showToast('已删除', 'success');
      if (aiclipProjectId === pid) aiclipShowList();
      else loadAiclipProjects();
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

// ---------- 打开项目（直接落到指定子页） ----------
function aiclipOpenProject(pid, pageKey) {
  aiclipProjectId = pid;
  aiclipScript = null;        // 切项目要清掉，否则会闪上一个项目的剧本/参考脚本/TTS
  aiclipReference = null;
  aiclipTts = null;
  acTtsSel = {};              // 勾选状态也要清（否则会把上一项目的 seq 带过来）
  aiclipProject = null;
  acHeadTitle = '';
  acPanelOpen = false;
  aiclipShowPage(pageKey || 'assets');   // 先切屏 + 高亮，区块里先显示「加载中」
  acEl('aiclip-materials-panel').innerHTML = '<div style="padding:24px;color:var(--text-hint);font-size:12px;">加载中…</div>';
  acEl('aiclip-script-panel').innerHTML = '';
  acEl('aiclip-reference-panel').innerHTML = '';
  acEl('aiclip-tts-panel').innerHTML = '';
  aiclipReloadDetail();
}

function aiclipReloadDetail() {
  if (!aiclipProjectId) return;
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId))
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast('加载失败: ' + (json.error || ''), 'error'); aiclipShowList(); return; }
      aiclipProject = json.data;
      aiclipMaterials = json.data.materials || [];
      acRenderPageHead();    // 项目头拿真实数据重渲（徽标 / 进度 / 项目设置）
      aiclipRenderMaterials();
      aiclipLoadScript();
      aiclipLoadReference();
      aiclipLoadTts();
      aiclipRenderNav();
      acNavHint();
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

function acProjectInfoHtml(p) {
  var html = '<div class="form-group" style="margin-bottom:10px;">' +
    '<label class="form-label">项目名称</label>' +
    '<input type="text" id="aiclip-name-input" value="' + escapeHtml(p.name || '') + '"></div>';
  html += '<div class="form-group" style="margin-bottom:10px;">' +
    '<label class="form-label">片型</label><select id="aiclip-kind-input">';
  var kinds = aiclipKinds.length ? aiclipKinds : [{ value: 'storyboard', label: '分镜型' }, { value: 'oral', label: '口播型' }];
  for (var i = 0; i < kinds.length; i++) {
    html += '<option value="' + kinds[i].value + '"' + (p.kind === kinds[i].value ? ' selected' : '') + '>' +
      escapeHtml(kinds[i].label) + '</option>';
  }
  html += '</select></div>';
  html += '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px;">' +
    '<span class="ac-badge">' + escapeHtml(AC_STATUS_LABEL[p.status] || p.status || '') + '</span>' +
    '<span class="ac-badge">素材 ' + (p.material_count || 0) + '</span>' +
    '<span class="ac-badge">已体检 ' + (p.probed_count || 0) + '</span>' +
    '<span style="font-size:11px;color:var(--text-hint);">进度 ' + (p.progress || 0) + '%</span></div>';
  html += '<div class="ac-card-bar" style="margin-bottom:12px;"><i style="width:' + (p.progress || 0) + '%;"></i></div>';
  html += '<div class="btn-group">' +
    '<button class="btn btn-primary btn-sm" onclick="aiclipSaveProject()">保存信息</button>' +
    '<button class="btn btn-secondary btn-sm" onclick="aiclipShowList()">返回列表</button>' +
    '<button class="btn btn-secondary btn-sm" onclick="aiclipDeleteProject(\'' + p.id + '\',\'' + escapeHtml(p.name || '') + '\')">删除项目</button>' +
    '</div>';
  html += '<div style="margin-top:10px;font-size:11px;color:var(--text-hint);line-height:1.7;">' +
    'ID <code>' + escapeHtml(p.id) + '</code><br>创建 ' + escapeHtml(acFmtTime(p.created_at)) +
    ' · 更新 ' + escapeHtml(acFmtTime(p.updated_at)) + '</div>';
  return html;
}

function aiclipSaveProject() {
  if (!aiclipProjectId) return;
  var name = (acEl('aiclip-name-input').value || '').trim();
  var kind = acEl('aiclip-kind-input').value;
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name, kind: kind })
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast('保存失败: ' + (json.error || ''), 'error'); return; }
      showToast('已保存', 'success');
      aiclipReloadDetail();
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

// ---------- 七步路线图 · 创作流程台 ----------
// ★ 2026-09-17 两次删除，别再加回来：
//   1) 「链路进度」左栏步骤条（acStepsHtml）—— 随详情页一起取消；
//   2) 模块首页的「创作流程 · 剧本 × 素材理解 × 用户需求 → 参考脚本」台
//      （AC_FLOW / acFlowState / aiclipRenderFlow / aiclipFlowGo / acScrollTo）
//      —— 爸爸明确「这个就不用了 直接删除」。
//      它当初是为了解决「SOP 在模块首页一个字都看不见」才加的；现在这份职责由
//      **顶部导航栏 + 两个子页**承担，再摆一张表就是纯冗余。
// 结论：模块首页只留项目卡片列表 + 新建卡，入口全部交给导航栏。

// ==================== 模块级导航栏 ====================
// 爸爸 2026-09-17：「我希望的是这个模块页面上面可以有一个导航栏」
//                「我的想法是这里有一个列表一样的 素材 参考脚本生成之类的」
// → 一条横排导航，列表页/子页都常驻可见。
// ★ 同日晚追加：「你就不能弄一个子页面吗 总往下滑看上去有点奇怪」
//   → 导航项从「滚到某个锚点」改成**切屏**：每个导航项各是一屏。
//     所以这里每一项带的是 page（DOM id），不是 anchor。
//     原先 6 项里的「素材理解 / 剧本 / 用户需求」不再是独立一屏：
//       · 素材理解 → 就在「素材」页里（每张素材卡 + 统计栏都有入口）
//       · 剧本 / 用户需求 → 是「参考脚本生成」的输入，收进那一页
// ★ 再追加第四项「TTS 语音」：参考脚本页的「导出」把台词交接给这一页，一镜一段。
var AC_NAV = [
  { key: 'projects', name: '我的项目', icon: '&#128203;', page: null },
  { key: 'assets', name: '素材', icon: '&#128230;', page: 'aiclip-page-assets' },
  { key: 'reference', name: '参考脚本生成', icon: '&#127916;', page: 'aiclip-page-reference' },
  { key: 'tts', name: 'TTS 语音', icon: '&#128266;', page: 'aiclip-page-tts' }
];
var acNavActive = 'projects';

function acNavByKey(key) {
  for (var i = 0; i < AC_NAV.length; i++) { if (AC_NAV[i].key === key) return AC_NAV[i]; }
  return null;
}

function aiclipRenderNav() {
  var box = acEl('aiclip-nav');
  if (!box) return;
  var h = '';
  for (var i = 0; i < AC_NAV.length; i++) {
    var n = AC_NAV[i];
    h += '<button class="ac-nav-item' + (acNavActive === n.key ? ' ac-nav-on' : '') +
      '" data-nav="' + n.key + '" onclick="acNavGo(\'' + n.key + '\')">' +
      '<span class="ac-nav-icon">' + n.icon + '</span>' + escapeHtml(n.name) + '</button>';
  }
  h += '<span class="ac-nav-hint" id="aiclip-nav-hint"></span>';
  box.innerHTML = h;
  acNavHint();
}

function acNavHint() {
  var el = acEl('aiclip-nav-hint');
  if (!el) return;
  el.textContent = aiclipProjectId
    ? ('当前项目：' + ((aiclipProject || {}).name || ''))
    : '未选项目 · 点任一步会自动打开最近的项目';
}

/** 只切 class，不重建 DOM —— 切屏时重建会让按钮闪一下 */
function acNavSetActive(key) {
  if (acNavActive === key) return;
  acNavActive = key;
  var items = document.querySelectorAll('#aiclip-nav .ac-nav-item');
  for (var i = 0; i < items.length; i++) {
    if (items[i].getAttribute('data-nav') === key) items[i].classList.add('ac-nav-on');
    else items[i].classList.remove('ac-nav-on');
  }
}

function acNavGo(key) {
  if (key === 'projects') {
    acNavActive = 'projects';
    aiclipRenderNav();
    aiclipShowList();
    return;
  }
  var item = acNavByKey(key);
  if (!item || !item.page) return;
  if (!aiclipProjectId) {
    // 还没进任何项目：用最近更新的那个（列表按 updated_at DESC 排），直接落到目标子页
    if (!aiclipProjects.length) { showToast('还没有项目，先新建一个', 'warn'); return; }
    var p = aiclipProjects[0];
    showToast('已打开最近项目「' + (p.name || '') + '」', 'success');
    aiclipOpenProject(p.id, key);
  } else {
    aiclipShowPage(key);
  }
}

// ★ 2026-09-17 删除 IntersectionObserver 滚动联动（原 acBindNavObserver）：
//   拆成子页后「一屏 = 一个导航项」，不存在「滚到哪算哪一区」的问题。
//   而且旧实现有真 bug：回调里 for 循环 return 第一个 isIntersecting 的 entry，
//   entries 顺序不保证上→下，且「已经在视口里没发生状态变化」时不触发回调
//   —— 实测「滚回素材区后高亮仍停在 script」。（T5c / T3b / T3e 三条断言抓到）

// ---------- 素材区 ----------
function aiclipRenderMaterials() {
  var box = acEl('aiclip-materials-panel');
  var html = acImportHtml();
  if (!aiclipMaterials.length) {
    html += '<div style="padding:26px 14px;text-align:center;color:var(--text-hint);font-size:12px;">' +
      '还没有素材 —— 拖文件到上面的框里，或从素材箱导入</div>';
  } else {
    html += '<div class="ac-mat-grid">';
    for (var i = 0; i < aiclipMaterials.length; i++) {
      html += acMaterialCardHtml(aiclipMaterials[i]);
    }
    html += '</div>';
  }
  box.innerHTML = html;
  acScheduleUndPoll();
}

function acImportHtml() {
  return '' +
    '<div class="ac-drop" id="aiclip-drop" ondragover="event.preventDefault();this.classList.add(\'ac-drop-on\');" ' +
    'ondragleave="this.classList.remove(\'ac-drop-on\');" ondrop="aiclipDrop(event)">' +
    '<b>&#128193; 把素材拖到这里</b>' +
    '<span>或 <button class="btn btn-primary btn-xs" onclick="acEl(\'aiclip-file-input\').click()">选择文件</button>' +
    ' （图片 / 视频，同一文件重复导入不会产生第二条）</span>' +
    '<input type="file" id="aiclip-file-input" multiple accept="image/*,video/*" style="display:none;" ' +
    'onchange="aiclipUpload(this.files);this.value=\'\';">' +
    '</div>' +
    '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0 4px;">' +
    '<button class="btn btn-secondary btn-sm" onclick="aiclipToggleInbox()">&#128230; 从素材箱导入</button>' +
    '<span style="font-size:11px;color:var(--text-hint);" id="aiclip-hint">' +
    '素材箱 = 宿主机 <code>D:/aiclip_inbox</code>（容器 /app/aiclip_inbox），大文件走这条' +
    '</span></div>' +
    '<div id="aiclip-inbox-panel" style="display:none;margin-bottom:10px;"></div>' +
    acUnderstandBarHtml();
}

function acMaterialCardHtml(m) {
  var title = m.name || m.original_name || '(未命名)';
  var html = '<div class="ac-mat">';
  // 缩略图直接可点 → 打开素材弹窗（视频能播、图片能放大）。
  // 爸爸要「素材可以直接预览，因为需要确保素材的理解不出问题」——
  // 所以预览必须一步可达，不能藏在「看理解」按钮里。
  html += '<div class="ac-mat-thumb" onclick="aiclipOpenMaterial(\'' + m.id +
    '\')" title="点击预览原素材">';
  if (m.thumb_url) {
    html += '<img src="' + m.thumb_url + '" loading="lazy" alt="" onerror="this.style.display=\'none\';this.parentNode.classList.add(\'ac-mat-nothumb\');">';
  }
  html += '<span class="ac-mat-play">' + (m.type === 'video' ? '&#9654;' : '&#9974;') + '</span>';
  html += '<span class="ac-mat-type">' + (m.type === 'video' ? '视频' : '图片') + '</span>';
  if (m.type === 'video' && m.duration) {
    html += '<span class="ac-mat-dur">' + escapeHtml(acFmtDur(m.duration)) + '</span>';
  }
  html += '</div>';
  html += '<div class="ac-mat-body">';
  html += '<div class="ac-mat-name" title="' + escapeHtml(title) + '">' + escapeHtml(title) + '</div>';
  html += '<div class="ac-mat-meta">' + escapeHtml(m.resolution || '—') +
    ' · ' + escapeHtml(acFmtSize(m.file_size)) + '</div>';
  html += '<div class="ac-mat-badges">';
  if (!m.probed) {
    html += '<span class="ac-badge ac-badge-warn">未体检</span>';
  } else {
    if (m.fps) html += '<span class="ac-badge">' + escapeHtml(acFmtFps(m.fps)) + '</span>';
    if (m.type === 'video') {
      html += '<span class="ac-badge ' + (m.has_audio ? 'ac-badge-ok' : '') + '">' +
        (m.has_audio ? '有声' : '无声') + '</span>';
    }
    if (m.has_alpha) html += '<span class="ac-badge ac-badge-ok">透明底</span>';
    if (typeof m.content_ratio === 'number') {
      var pct = Math.round(m.content_ratio * 100);
      html += '<span class="ac-badge ' + (pct < 95 ? 'ac-badge-warn' : '') + '">内容 ' + pct + '%</span>';
    }
  }
  if (m.used_count > 1) html += '<span class="ac-badge">复用 ' + m.used_count + '</span>';
  html += '</div>';
  if (typeof m.content_ratio === 'number' && m.content_ratio < 0.95 && m.bbox_px) {
    html += '<div class="ac-mat-note">真实内容 ' + (m.bbox_px[2] - m.bbox_px[0]) + '×' +
      (m.bbox_px[3] - m.bbox_px[1]) + '，外面是空白/透明边</div>';
  }
  html += acMatUnderstandHtml(m);
  html += '</div>';
  html += '<div class="ac-mat-ops">' +
    '<button class="btn btn-secondary btn-xs" onclick="aiclipReprobe(\'' + m.id + '\')">重检</button>' +
    '<button class="btn btn-secondary btn-xs" onclick="aiclipUnlink(\'' + m.id + '\')">移出项目</button>' +
    (m.used_count <= 1 ? '<button class="btn btn-secondary btn-xs" onclick="aiclipRemoveMaterial(\'' + m.id + '\')">&#128465;</button>' : '') +
    '</div>';
  html += '</div>';
  return html;
}

// ---------- 上传 ----------
function aiclipDrop(ev) {
  ev.preventDefault();
  var dz = acEl('aiclip-drop');
  if (dz) dz.classList.remove('ac-drop-on');
  var dt = ev.dataTransfer;
  if (dt && dt.files && dt.files.length) aiclipUpload(dt.files);
}

function aiclipUpload(files) {
  if (!aiclipProjectId || !files || !files.length) return;
  var fd = new FormData();
  for (var i = 0; i < files.length; i++) fd.append('files', files[i]);
  spinner('spinner-aiclip', true);
  var hint = acEl('aiclip-hint');
  if (hint) hint.textContent = '正在导入 ' + files.length + ' 个文件（体检中，视频可能要几秒）…';
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/materials/upload', {
    method: 'POST', body: fd
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      spinner('spinner-aiclip', false);
      if (!json.success) {
        showToast('导入失败: ' + (json.error || ''), 'error');
        aiclipReloadDetail();
        return;
      }
      var d = json.data;
      var msg = '新增 ' + d.added_count + ' 个';
      if (d.deduped_count) msg += '，复用 ' + d.deduped_count + ' 个（同内容已存在）';
      if (d.failed_count) msg += '，失败 ' + d.failed_count + ' 个';
      showToast(msg, d.failed_count ? 'warning' : 'success');
      if (d.failed_count) {
        for (var i = 0; i < d.failed.length; i++) console.warn('导入失败', d.failed[i]);
      }
      aiclipReloadDetail();
    })
    .catch(function (e) {
      spinner('spinner-aiclip', false);
      showToast('请求失败: ' + e.message, 'error');
      aiclipReloadDetail();
    });
}

// ---------- 素材箱 ----------
function aiclipToggleInbox() {
  var p = acEl('aiclip-inbox-panel');
  if (p.style.display === 'none') {
    p.style.display = '';
    aiclipLoadInbox();
  } else {
    p.style.display = 'none';
  }
}

function aiclipLoadInbox() {
  var p = acEl('aiclip-inbox-panel');
  p.innerHTML = '<div style="padding:12px;color:var(--text-hint);font-size:12px;">读取中…</div>';
  fetch('/api/aiclip/inbox')
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { p.innerHTML = '<div style="padding:12px;color:var(--text-hint);font-size:12px;">读取失败</div>'; return; }
      var files = json.data || [];
      var html = '<div class="ac-inbox">';
      html += '<div class="ac-inbox-head"><b>素材箱</b><code>' + escapeHtml(json.root || '') + '</code>' +
        (json.exists ? '' : ' <span class="ac-badge ac-badge-warn">目录不存在</span>') + '</div>';
      if (!files.length) {
        html += '<div style="padding:12px;color:var(--text-hint);font-size:12px;">箱里没有可导入的图片/视频 —— 把文件复制到上面那个目录再刷新</div>';
      } else {
        html += '<div class="ac-inbox-list">';
        for (var i = 0; i < files.length; i++) {
          var f = files[i];
          html += '<label class="ac-inbox-item"><input type="checkbox" class="ac-inbox-cb" value="' + escapeHtml(f.name) + '">' +
            '<span class="ac-inbox-name">' + escapeHtml(f.name) + '</span>' +
            '<span class="ac-inbox-meta">' + escapeHtml(f.kind === 'video' ? '视频' : '图片') +
            ' · ' + escapeHtml(acFmtSize(f.size)) + '</span></label>';
        }
        html += '</div>';
        html += '<div class="btn-group" style="margin-top:8px;">' +
          '<button class="btn btn-primary btn-sm" onclick="aiclipScanSelected()">导入选中</button>' +
          '<button class="btn btn-secondary btn-sm" onclick="aiclipScanSelected(true)">全部导入</button>' +
          '<button class="btn btn-secondary btn-sm" onclick="aiclipLoadInbox()">刷新</button></div>';
      }
      html += '</div>';
      p.innerHTML = html;
    })
    .catch(function (e) { p.innerHTML = '<div style="padding:12px;color:var(--text-hint);font-size:12px;">请求失败: ' + escapeHtml(e.message) + '</div>'; });
}

function aiclipScanSelected(all) {
  if (!aiclipProjectId) return;
  var body = { all: !!all };
  if (!all) {
    var cbs = document.querySelectorAll('.ac-inbox-cb:checked');
    var names = [];
    for (var i = 0; i < cbs.length; i++) names.push(cbs[i].value);
    if (!names.length) { showToast('先勾选要导入的文件', 'error'); return; }
    body.names = names;
  }
  spinner('spinner-aiclip', true);
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/materials/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      spinner('spinner-aiclip', false);
      if (!json.success) { showToast('导入失败: ' + (json.error || ''), 'error'); return; }
      var d = json.data;
      showToast('新增 ' + d.added_count + ' 个，复用 ' + d.deduped_count + ' 个' +
        (d.failed_count ? '，失败 ' + d.failed_count + ' 个' : ''), d.failed_count ? 'warning' : 'success');
      aiclipReloadDetail();
    })
    .catch(function (e) { spinner('spinner-aiclip', false); showToast('请求失败: ' + e.message, 'error'); });
}

// ---------- 素材操作 ----------
function aiclipUnlink(mid) {
  if (!aiclipProjectId) return;
  if (!confirm('从本项目移出这个素材？\n（素材本身会保留在全库素材里）')) return;
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/materials/' + encodeURIComponent(mid), { method: 'DELETE' })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast('操作失败: ' + (json.error || ''), 'error'); return; }
      showToast('已移出项目', 'success');
      aiclipReloadDetail();
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

function aiclipRemoveMaterial(mid) {
  if (!confirm('从全库素材里彻底删除？磁盘文件也会删掉。')) return;
  fetch('/api/aiclip/materials/' + encodeURIComponent(mid), { method: 'DELETE' })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast('删除失败: ' + (json.error || ''), 'error'); return; }
      showToast('已删除', 'success');
      aiclipReloadDetail();
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

function aiclipReprobe(mid) {
  spinner('spinner-aiclip', true);
  fetch('/api/aiclip/materials/' + encodeURIComponent(mid) + '/reprobe', { method: 'POST' })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      spinner('spinner-aiclip', false);
      if (!json.success) { showToast('重检失败: ' + (json.error || ''), 'error'); return; }
      showToast('已重检', 'success');
      aiclipReloadDetail();
    })
    .catch(function (e) { spinner('spinner-aiclip', false); showToast('请求失败: ' + e.message, 'error'); });
}

// ==================== 素材理解（P2） ====================
// 理解是异步的（246s 口播要 2–3 分钟），POST 立即返回，进度靠轮询素材列表。
// 不另造任务轮询接口 —— 素材列表里本来就带 understand.status。
var acUndTimer = null;
var acUndWasRunning = false;
var acUndDetailMid = null;

function acUndLabel(u) {
  u = u || {};
  if (u.status === 'running') return '理解中…';
  if (u.status === 'failed') return '理解失败';
  if (u.status === 'done') {
    // 卡片徽标宽度有限：「真人出镜口播」压成「口播」，完整形态放 title
    var k = String(u.kind || '')
      .replace('真人出镜', '').replace('真人', '').trim() || '已理解';
    return k + ' · ' + (u.unit_count || 0) + '单元';
  }
  return '未理解';
}

function acUndClass(u) {
  u = u || {};
  if (u.status === 'done') return 'ac-und-done';
  if (u.status === 'running') return 'ac-und-running';
  if (u.status === 'failed') return 'ac-und-failed';
  return 'ac-und-pending';
}

function acMatUnderstandHtml(m) {
  var u = m.understand || {};
  var html = '<div class="ac-mat-und">';
  html += '<span class="ac-und-badge ' + acUndClass(u) + '" title="' +
    escapeHtml((u.kind ? u.kind + ' · ' : '') + (u.error || u.summary || '')) + '">' +
    escapeHtml(acUndLabel(u)) + '</span>';
  if (u.status === 'done') {
    html += '<button class="btn btn-secondary btn-xs" onclick="aiclipOpenMaterial(\'' +
      m.id + '\')">看理解</button>';
  } else if (u.status !== 'running') {
    html += '<button class="btn btn-primary btn-xs" onclick="aiclipUnderstandOne(\'' +
      m.id + '\')">理解</button>';
  }
  html += '</div>';
  if (u.text_on_screen) {
    html += '<div class="ac-mat-note">屏幕文字：' +
      escapeHtml(String(u.text_on_screen).substring(0, 36)) + '</div>';
  }
  return html;
}

function acUnderstandBarHtml() {
  var total = aiclipMaterials.length;
  if (!total) return '';
  var done = 0, running = 0, failed = 0, units = 0, chars = 0;
  for (var i = 0; i < total; i++) {
    var u = aiclipMaterials[i].understand || {};
    if (u.status === 'done') {
      done++; units += (u.unit_count || 0); chars += (u.speech_chars || 0);
    } else if (u.status === 'running') { running++; }
    else if (u.status === 'failed') { failed++; }
  }
  var pending = total - done - running;
  var h = '<div class="ac-und-bar"><b>素材理解</b>';
  h += '<span>已理解 <b style="color:#047857;">' + done + '</b>/' + total +
    '　·　可编排单元 ' + units + ' 个　·　转写 ' + chars + ' 字' +
    (running ? '　·　<b style="color:var(--accent-text);">' + running + ' 个理解中</b>' : '') +
    (failed ? '　·　<b style="color:#b91c1c;">' + failed + ' 个失败</b>' : '') + '</span>';
  h += '<span style="margin-left:auto;display:flex;gap:6px;align-items:center;">';
  if (running) {
    h += '<button class="btn btn-secondary btn-sm" onclick="acStartUndPoll()">刷新进度</button>';
  } else if (pending > 0) {
    h += '<button class="btn btn-primary btn-sm" onclick="aiclipUnderstandAll(false)">' +
      '&#10024; 理解素材（' + pending + ' 个待理解）</button>';
  } else if (done > 0) {
    h += '<button class="btn btn-secondary btn-sm" onclick="aiclipUnderstandAll(true)">重跑全部理解</button>';
  }
  h += '</span></div>';
  return h;
}

function aiclipUnderstandOne(mid) {
  fetch('/api/aiclip/materials/' + encodeURIComponent(mid) + '/understand', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force: false })
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast(json.error || '启动失败', 'error'); return; }
      showToast('已开始理解，长素材需要几分钟', 'success');
      acUndWasRunning = true;
      acScheduleUndPoll(true);
      setTimeout(aiclipReloadDetail, 700);
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

function aiclipUnderstandAll(force) {
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) +
    '/materials/understand', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force: !!force })
    })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast(json.error || '启动失败', 'error'); return; }
      var d = json.data || {};
      if (!d.total) { showToast('没有需要理解的素材（都已完成）', 'success'); return; }
      showToast('已启动 ' + d.started + ' 个素材的理解' +
        (d.skipped ? '（跳过 ' + d.skipped + ' 个已完成）' : ''), 'success');
      acUndWasRunning = true;
      acScheduleUndPoll(true);
      setTimeout(aiclipReloadDetail, 900);
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

function acStartUndPoll() { acScheduleUndPoll(true); }

function acScheduleUndPoll(force) {
  var running = 0;
  for (var i = 0; i < aiclipMaterials.length; i++) {
    if ((aiclipMaterials[i].understand || {}).status === 'running') running++;
  }
  if (!running && !force) return;
  if (acUndTimer) return;
  acUndTimer = setTimeout(function () {
    acUndTimer = null;
    if (!aiclipProjectId) return;
    fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/materials')
      .then(function (r) { return r.json(); })
      .then(function (json) {
        if (!json.success) return;
        aiclipMaterials = json.data || [];
        aiclipRenderMaterials();
        var still = 0;
        for (var i = 0; i < aiclipMaterials.length; i++) {
          if ((aiclipMaterials[i].understand || {}).status === 'running') still++;
        }
        if (still) {
          acUndWasRunning = true;
        } else if (acUndWasRunning) {
          acUndWasRunning = false;
          showToast('素材理解完成', 'success');
        }
      })
      .catch(function () { });
  }, 4000);
}

// ---------- 理解详情弹窗 ----------
function aiclipOpenMaterial(mid) {
  acUndDetailMid = mid;
  var mask = document.createElement('div');
  mask.className = 'ac-mask';
  mask.id = 'aiclip-mat-mask';
  mask.onclick = function (e) { if (e.target === mask) aiclipCloseMaterial(); };
  mask.innerHTML = '<div class="ac-modal"><div class="ac-modal-head"><b>加载中…</b></div>' +
    '<div class="ac-modal-body" style="padding:26px;text-align:center;color:var(--text-hint);font-size:12px;">' +
    '读取理解结果…</div></div>';
  document.body.appendChild(mask);
  fetch('/api/aiclip/materials/' + encodeURIComponent(mid))
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast(json.error || '读取失败', 'error'); aiclipCloseMaterial(); return; }
      acRenderMaterialModal(json.data);
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); aiclipCloseMaterial(); });
}

function aiclipCloseMaterial() {
  var m = acEl('aiclip-mat-mask');
  if (m && m.parentNode) m.parentNode.removeChild(m);
  acUndDetailMid = null;
}

// ---------- 弹窗共用件：预览 / 可编辑字段 ----------
var acMatRaw = null;    // 当前弹窗的素材数据
var acMatEdit = false;  // 是否处于「校对」模式

/** 原素材预览：视频带播放控件，图片可点开放大。
 *  爸爸的原话是「素材可以直接预览，比如视频可以直接预览，因为我需要确保素材的理解不出问题」——
 *  所以这里的预览是**核对理解**用的：左边看画面，右边看模型描述，对不对一眼就知道。 */
function acPreviewHtml(m) {
  var url = m.file_url;
  if (!url) {
    return '<div class="ac-preview ac-preview-none">原素材文件不可访问</div>';
  }
  var h = '<div class="ac-preview">';
  if (m.type === 'video') {
    h += '<video class="ac-preview-media" src="' + url +
      '" controls preload="metadata" playsinline></video>';
  } else {
    h += '<img class="ac-preview-media ac-preview-zoomable" src="' + url +
      '" alt="" onclick="acZoomImage(this.src)">';
  }
  h += '<div class="ac-preview-bar"><span>' + escapeHtml(m.name || '') + '</span>';
  h += '<span style="color:var(--text-hint);">' + escapeHtml(m.resolution || '—') +
    ' · ' + escapeHtml(acFmtSize(m.file_size)) +
    (m.type === 'video' ? ' · ' + escapeHtml(acFmtDur(m.duration)) : '') + '</span>';
  h += '<a href="' + url + '?download=1" target="_blank" rel="noopener" ' +
    'style="margin-left:auto;font-size:11px;">下载原文件</a></div>';
  h += '</div>';
  return h;
}

function acZoomImage(src) {
  var d = document.createElement('div');
  d.className = 'ac-lightbox';
  d.onclick = function () { if (d.parentNode) d.parentNode.removeChild(d); };
  d.innerHTML = '<img src="' + src + '" alt="">';
  document.body.appendChild(d);
}

/** 只读 → kv 行；校对模式 → 输入框。key 与 PATCH body 的字段名一致。 */
function acFieldHtml(label, key, value, multiline, hint) {
  var v = value == null ? '' : String(value);
  if (acMatEdit) {
    var inp = multiline
      ? '<textarea class="ac-input ac-input-area" data-ac-f="' + key + '">' +
        escapeHtml(v) + '</textarea>'
      : '<input class="ac-input" type="text" data-ac-f="' + key + '" value="' +
        escapeHtml(v) + '">';
    return '<div class="ac-field">' +
      (label ? '<label>' + escapeHtml(label) + '</label>' : '') + inp +
      (hint ? '<i class="ac-field-hint">' + escapeHtml(hint) + '</i>' : '') + '</div>';
  }
  return '<div class="ac-kv">' + (label ? '<b>' + escapeHtml(label) + '</b>' : '') +
    '<span>' + (v ? escapeHtml(v).replace(/\n/g, '<br>') : '—') + '</span></div>';
}

/** 可编排单元的单个字段（按 index 局部提交，见 materials.update_understand） */
function acUnitFieldHtml(index, field, label, value) {
  return '<div class="ac-field ac-field-inline"><label>' + escapeHtml(label) + '</label>' +
    '<textarea class="ac-input ac-input-area" data-ac-u="' + index +
    '" data-ac-uf="' + field + '">' + escapeHtml(value == null ? '' : String(value)) +
    '</textarea></div>';
}

function acToggleMatEdit() {
  acMatEdit = !acMatEdit;
  if (acMatRaw) acRenderMaterialModal(acMatRaw);
}

/** 保存校对：把界面上所有 data-ac-f / data-ac-u 收成 PATCH body 提交。
 *  只提交界面上存在的字段 —— 所以后端是 PATCH 语义（没传的不动）。 */
function aiclipSaveUnderstand() {
  var mask = acEl('aiclip-mat-mask');
  if (!mask || !acMatRaw) return;
  var body = {};
  var scalars = mask.querySelectorAll('[data-ac-f]');
  for (var i = 0; i < scalars.length; i++) {
    body[scalars[i].getAttribute('data-ac-f')] = scalars[i].value;
  }
  var unitEls = mask.querySelectorAll('[data-ac-u]');
  var byIdx = {};
  var order = [];
  for (var j = 0; j < unitEls.length; j++) {
    var idx = parseInt(unitEls[j].getAttribute('data-ac-u'), 10);
    if (isNaN(idx)) continue;
    if (!byIdx[idx]) { byIdx[idx] = { index: idx }; order.push(idx); }
    byIdx[idx][unitEls[j].getAttribute('data-ac-uf')] = unitEls[j].value;
  }
  var units = [];
  for (var k = 0; k < order.length; k++) units.push(byIdx[order[k]]);
  if (units.length) body.units = units;

  var btn = acEl('ac-save-und');
  if (btn) { btn.disabled = true; btn.textContent = '保存中…'; }
  fetch('/api/aiclip/materials/' + encodeURIComponent(acMatRaw.id) + '/understand', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) {
        showToast('保存失败: ' + (json.error || ''), 'error');
        if (btn) { btn.disabled = false; btn.textContent = '保存校对'; }
        return;
      }
      showToast('校对已保存', 'success');
      acMatEdit = false;
      acMatRaw = json.data;
      acRenderMaterialModal(json.data);
      aiclipReloadDetail();   // 卡片徽标要同步「已人工校对」
    })
    .catch(function (e) {
      showToast('请求失败: ' + e.message, 'error');
      if (btn) { btn.disabled = false; btn.textContent = '保存校对'; }
    });
}

function acRenderMaterialModal(m) {
  acMatRaw = m;
  var mask = acEl('aiclip-mat-mask');
  if (!mask) return;
  var u = m.understand || {};
  var units = u.units || [];
  var sp = u.speech || {};
  var mod = u.modality || {};
  var h = '<div class="ac-modal">';
  h += '<div class="ac-modal-head"><b>' + escapeHtml(m.name || '') + '</b>';
  h += '<span class="ac-und-badge ' + acUndClass(u) + '" style="flex:none;">' +
    escapeHtml(acUndLabel(u)) + '</span>';
  if (u.edited) {
    h += '<span class="ac-badge ac-badge-ok" style="flex:none;" title="最后校对 ' +
      escapeHtml(u.edited_at || '') + '">&#9998; 已人工校对</span>';
  }
  if (u.status === 'done') {
    h += '<button class="btn ' + (acMatEdit ? 'btn-primary' : 'btn-secondary') +
      ' btn-xs" style="flex:none;" onclick="acToggleMatEdit()">' +
      (acMatEdit ? '&#10003; 退出校对' : '&#9998; 校对理解结果') + '</button>';
  }
  h += '<button class="btn btn-secondary btn-xs" style="flex:none;" onclick="aiclipCloseMaterial()">关闭</button></div>';
  h += '<div class="ac-modal-body">';

  // ---- 预览（核对理解的依据）----
  h += acPreviewHtml(m);

  if (u.status === 'running') {
    h += '<div style="padding:30px;text-align:center;color:var(--accent-text);font-size:12.5px;">' +
      '正在理解中，请稍候…</div>';
  } else if (u.status === 'failed') {
    h += '<div style="padding:18px;color:#b91c1c;font-size:12.5px;line-height:1.8;">理解失败：' +
      escapeHtml(u.error || '未知错误') + '</div>';
  } else if (u.status === 'done') {
    h += '<div class="ac-sec-title">素材概况' +
      (acMatEdit ? '<span class="ac-edit-hint">校对中 —— 改完点右上「退出校对」保存</span>' : '') +
      '</div>';
    h += acFieldHtml('形态', 'kind', u.kind, false);
    h += acFieldHtml('摘要', 'summary', u.summary, true);
    h += acFieldHtml('标签', 'tags', (u.tags || []).join('、'), false, '顿号 / 逗号分隔');
    h += '<div class="ac-kv"><b>声音</b><span>' +
      (mod.has_speech ? ('有语音 · ' + escapeHtml(mod.speech_desc || '')) : '无语音') +
      (mod.has_music ? ' · 有配乐' : '') +
      ((mod.audio_metrics || {}).usable ? ' · 音轨可用' : '') + '</span></div>';
    // 屏幕文字与转写全文是**同音错别字的重灾区**，所以即使为空也给可编辑入口
    h += acFieldHtml('屏幕文字', 'text_on_screen', u.text_on_screen, true,
      '画面里烧的字，错一个字成片就跟着错');
    h += acFieldHtml('注意', 'notes', u.notes, true);
    var g = m.geom || {};
    h += '<div class="ac-kv"><b>几何</b><span>' + escapeHtml(m.resolution || '—') +
      (g.has_alpha ? ' · 透明底' : '') +
      (typeof m.content_ratio === 'number'
        ? ' · 真实内容占 ' + Math.round(m.content_ratio * 100) + '%' : '') + '</span></div>';
    if (u.cost) {
      h += '<div class="ac-kv"><b>开销</b><span>' + (u.cost.calls || 0) + ' 次调用 · ' +
        (u.cost.seconds || 0) + 's · ' + (u.cost.input_tokens || 0) + ' in / ' +
        (u.cost.output_tokens || 0) + ' out tokens</span></div>';
    }

    h += '<div class="ac-sec-title">可编排单元（' + units.length + ' 个）</div>';
    for (var i = 0; i < units.length; i++) {
      var un = units[i];
      h += '<div class="ac-unit"><div class="ac-unit-h">' +
        '<span class="ac-unit-idx">#' + (i + 1) + '</span>' +
        '<span class="ac-unit-time">' + un.start + ' – ' + un.end + 's</span>' +
        (un.usable_for && un.usable_for.length
          ? '<span class="ac-badge">' + escapeHtml(un.usable_for.join(' / ')) + '</span>' : '') +
        '</div>';
      if (acMatEdit) {
        h += acUnitFieldHtml(i, 'visual', '画面', un.visual);
        h += acUnitFieldHtml(i, 'speech', '语音', un.speech);
        h += acUnitFieldHtml(i, 'usable_for', '可用于', (un.usable_for || []).join('、'));
      } else {
        if (un.visual) h += '<div class="ac-unit-visual">' + escapeHtml(un.visual) + '</div>';
        if (un.speech) h += '<div class="ac-unit-speech">' + escapeHtml(un.speech) + '</div>';
      }
      h += '</div>';
    }
    // 转写全文是 ② 参考脚本里「台词」的唯一来源，同音错别字会原样进字幕，
    // 所以校对模式下即使还没有转写也要给输入框。
    if (acMatEdit || sp.full_text) {
      h += '<div class="ac-sec-title">语音转写全文（' +
        String(sp.full_text || '').length + ' 字）' +
        (acMatEdit ? '<span class="ac-edit-hint">同音错别字高发区，务必核对</span>' : '') +
        '</div>';
      if (acMatEdit) {
        h += acFieldHtml('', 'speech_full_text', sp.full_text, true);
      } else {
        h += '<div class="ac-transcript">' + escapeHtml(sp.full_text) + '</div>';
      }
    }
  }
  h += '</div>';
  h += '<div class="ac-modal-foot">';
  if (acMatEdit) {
    h += '<button class="btn btn-primary btn-sm" id="ac-save-und" ' +
      'onclick="aiclipSaveUnderstand()">&#128190; 保存校对</button>';
  }
  h += '<button class="btn btn-secondary btn-sm" onclick="aiclipUnderstandOne(\'' + m.id +
    '\');aiclipCloseMaterial();">重跑本条理解</button>' +
    '<span style="font-size:11px;color:var(--text-hint);margin-left:auto;">' +
    '理解结果 = ② 参考脚本的输入（素材能力层）' +
    (u.edited ? '　·　<span style="color:#047857;">已被人工校对</span>' : '') +
    '</span>';
  h += '</div>';
  h += '</div>';
  mask.innerHTML = h;
}

// ==================== P3：剧本导入（SOP ①） ====================
var aiclipScript = null;
var aiclipReference = null;
var acRefTimer = null;

// P5c：TTS 语音（一镜一段旁白）。aiclipTts = GET /api/aiclip/projects/<pid>/tts 的整包出参。
var aiclipTts = null;
var acTtsTimer = null;
var acTtsSel = {};      // {seq: true} —— 用户勾了哪些段要合成（默认勾 ② 判定缺配音的）

function aiclipLoadScript() {
  if (!aiclipProjectId) return;
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/script')
    .then(function (r) { return r.json(); })
    .then(function (json) {
      aiclipScript = json.success ? json.data : null;
      aiclipRenderScript();
    })
    .catch(function () { aiclipRenderScript(); });
}

function aiclipLoadReference() {
  if (!aiclipProjectId) return;
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/reference?full=1')
    .then(function (r) { return r.json(); })
    .then(function (json) {
      aiclipReference = json.success ? json.data : null;
      aiclipRenderReference();
    })
    .catch(function () { aiclipRenderReference(); });
}

function acSec(v) {
  var n = Number(v || 0);
  return (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1)) + 's';
}

function acScriptFileName() {
  var raw = aiclipScript && aiclipScript.raw;
  return (raw && raw.source_name) || '';
}

function aiclipRenderScript() {
  var box = acEl('aiclip-script-panel');
  if (!box) return;
  var badge = acEl('aiclip-script-badge');
  var sc = aiclipScript;
  var h = '';

  h += '<div class="ac-hit"><div class="ac-drop2" id="aiclip-script-drop" ' +
    'ondragover="event.preventDefault();this.classList.add(\'ac-drop2-on\');" ' +
    'ondragleave="this.classList.remove(\'ac-drop2-on\');" ondrop="aiclipScriptDrop(event)">' +
    '<b>&#128221; 拖剧本 xlsx 到这里</b><br>' +
    '<span style="font-size:11px;">或 <button class="btn btn-primary btn-xs" ' +
    'onclick="acEl(\'aiclip-script-input\').click()">选择文件</button>' +
    '（.xlsx / .csv / .txt；sheet 名建议「分镜脚本」）</span>' +
    '<input type="file" id="aiclip-script-input" accept=".xlsx,.xlsm,.csv,.txt" style="display:none;" ' +
    'onchange="aiclipUploadScript(this.files);this.value=\'\';">' +
    '</div></div>' +
    '<div style="display:flex;gap:6px;margin-bottom:8px;align-items:flex-start;">' +
    '<textarea id="aiclip-script-text" rows="2" placeholder="或粘贴表格：每行一镜，Tab / 竖线分隔" ' +
    'style="flex:1;padding:7px 9px;border:1px solid var(--border);border-radius:8px;background:var(--bg);' +
    'color:var(--text);font-size:12px;resize:vertical;"></textarea>' +
    '<button class="btn btn-secondary btn-sm" onclick="aiclipPasteScript()">粘贴导入</button></div>';

  if (!sc) {
    h += '<div class="ac-dim">还没有剧本。剧本是 ② 参考脚本的一路输入（另一路是素材理解结果）。</div>';
    box.innerHTML = h;
    if (badge) badge.style.display = 'none';
    return;
  }
  if (badge) {
    badge.style.display = '';
    badge.textContent = sc.shot_count + ' 镜 · ' + acSec(sc.total_duration) +
      ' · v' + (sc.version || 1);
  }
  h += '<div class="ac-dim">来源 <code>' + escapeHtml(acScriptFileName() || '-') +
    '</code>｜更新 ' + escapeHtml(acFmtTime(sc.updated_at)) + '</div>';

  var shots = sc.shots || [];
  h += '<div class="ac-shot-wrap"><table><thead><tr>' +
    '<th>镜</th><th>时间</th><th>景别/角度</th><th>运镜</th><th>画面内容</th>' +
    '<th>人物&amp;场景</th><th>台词</th><th>音效</th></tr></thead><tbody>';
  for (var i = 0; i < shots.length; i++) {
    var s = shots[i];
    var meta = [s.shot_size, s.angle, s.composition].filter(function (x) { return !!x; }).join('/');
    h += '<tr>' +
      '<td class="ac-seq">#' + s.seq + '</td>' +
      '<td class="ac-dim">' + acSec(s.start) + '<br>&#8594;' + acSec(s.end) + '</td>' +
      '<td>' + escapeHtml(meta || '-') + '</td>' +
      '<td class="ac-dim">' + escapeHtml(s.camera_move || '-') + '</td>' +
      '<td>' + escapeHtml(s.content || '-') + '</td>' +
      '<td class="ac-dim">' + escapeHtml(s.characters_scene || '-') + '</td>' +
      '<td>' + escapeHtml(s.subtitle_text || '-') + '</td>' +
      '<td class="ac-dim">' + escapeHtml(s.audio_note || '-') + '</td>' +
      '</tr>';
  }
  h += '</tbody></table></div>';
  box.innerHTML = h;
}

function aiclipScriptDrop(ev) {
  ev.preventDefault();
  var el = acEl('aiclip-script-drop');
  if (el) el.classList.remove('ac-drop2-on');
  if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files.length) {
    aiclipUploadScript(ev.dataTransfer.files);
  }
}

function aiclipUploadScript(files) {
  if (!files || !files.length) return;
  if (!aiclipProjectId) { showToast('先打开一个项目', 'error'); return; }
  var fd = new FormData();
  fd.append('file', files[0]);
  var req = acEl('aiclip-req-input');
  if (req && req.value.trim()) fd.append('requirement', req.value.trim());
  var btn = acEl('aiclip-script-input');
  if (btn) btn.disabled = true;
  showToast('正在解析剧本…');
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/script', {
    method: 'POST', body: fd
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (btn) btn.disabled = false;
      if (!json.success) { showToast('导入失败: ' + (json.error || ''), 'error'); return; }
      showToast('已导入 ' + (json.parsed || 0) + ' 镜 / ' + acSec(json.total_duration), 'success');
      aiclipReloadDetail();
    })
    .catch(function (e) {
      if (btn) btn.disabled = false;
      showToast('请求失败: ' + e.message, 'error');
    });
}

function aiclipPasteScript() {
  if (!aiclipProjectId) { showToast('先打开一个项目', 'error'); return; }
  var ta = acEl('aiclip-script-text');
  var text = ta ? ta.value.trim() : '';
  if (!text) { showToast('先粘贴剧本文本', 'error'); return; }
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/script', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: text, source_name: 'pasted' })
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast('导入失败: ' + (json.error || ''), 'error'); return; }
      showToast('已导入 ' + (json.parsed || 0) + ' 镜', 'success');
      aiclipReloadDetail();
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

// ==================== P3：参考脚本（SOP ②, LLM#1） ====================
function acMatName(mid) {
  for (var i = 0; i < aiclipMaterials.length; i++) {
    if (aiclipMaterials[i].id === mid) {
      return aiclipMaterials[i].name || aiclipMaterials[i].original_name || mid.slice(0, 8);
    }
  }
  return mid ? String(mid).slice(0, 8) : '-';
}

function acGapHtml(g) {
  var act = g.action || 'shoot';
  var label = {
    tts: '&#127897; TTS 配音', shoot: '&#127916; 需补拍', stock: '&#128269; 找素材',
    effect: '&#10024; 需特效', reuse: '&#9851; 复用素材'
  }[act] || act;
  var h = '<div class="ac-gap ac-gap-' + act + '">' +
    '<div class="ac-gap-h">' + label +
    ' <span class="ac-seq">剧本镜 #' + (g.source_seq != null ? g.source_seq : '-') + '</span>' +
    (g.auto ? ' <span class="ac-tag-auto">自动诊断</span>' : '') +
    (g.priority === 'high' ? ' <span class="ac-pill ac-pill-bad">高</span>' : '') +
    '</div>' +
    '<div>' + escapeHtml(g.need || '-') + '</div>';
  if (g.reason) h += '<div class="ac-dim">原因：' + escapeHtml(g.reason) + '</div>';
  if (g.suggestion) h += '<div><b>建议：</b>' + escapeHtml(g.suggestion) + '</div>';
  h += '</div>';
  return h;
}

function aiclipRenderReference() {
  var box = acEl('aiclip-reference-panel');
  if (!box) return;
  var badge = acEl('aiclip-reference-badge');
  var rf = aiclipReference;
  var proj = aiclipProject || {};
  var running = !!(rf && rf.gen_status === 'generating');
  var ttsTotal = (aiclipTts && aiclipTts.stats) ? aiclipTts.stats.total : 0;

  var h = '<div style="margin-bottom:8px;">' +
    '<label class="form-label">用户需求（这条片子要什么效果）</label>' +
    '<textarea id="aiclip-req-input" rows="2" ' +
    'placeholder="例：30 秒带货，节奏快，突出痛点与性价比，结尾留互动钩子" ' +
    'style="width:100%;padding:7px 9px;border:1px solid var(--border);border-radius:8px;' +
    'background:var(--bg);color:var(--text);font-size:12px;resize:vertical;">' +
    escapeHtml((rf && rf.requirement) || proj.requirement || '') + '</textarea></div>';

  h += '<div class="ac-hit">' +
    '<button class="btn btn-primary btn-sm' + (running ? ' ac-busy' : '') +
    '" onclick="aiclipGenReference()">' +
    (running ? '生成中…（约 2 分钟）' : ((rf && rf.timeline_count) ? '重新生成' : '生成参考脚本')) +
    '</button>';
  if (rf && rf.timeline_count) {
    h += '<a class="btn btn-secondary btn-sm" href="/api/aiclip/projects/' +
      encodeURIComponent(aiclipProjectId) + '/reference.md?download=1">&#11015; 下载 md</a>';
    // ★ 爸爸要的「导出」：把每镜台词交接给 TTS 语音子页。
    //   幂等 —— 重复点只是「对齐」，台词改过的段会把旧音频置为过期。
    h += '<button class="btn btn-secondary btn-sm" onclick="aiclipExportTts()">' +
      '&#128266; 导出 TTS 台词' + (ttsTotal ? '（' + ttsTotal + ' 段）' : '') + '</button>';
  }
  h += '<span class="ac-dim">LLM 第 1 次 · 实测约 2 分钟 / 1.8 万 token</span></div>';

  if (!rf) {
    var why = !proj.script_id ? '先导入剧本。'
      : (!proj.understood_count ? '先把素材理解跑完（至少要有一条已理解素材）。' : '');
    h += '<div class="ac-dim">还没有生成参考脚本。' + escapeHtml(why || '') + '</div>';
    box.innerHTML = h;
    if (badge) badge.style.display = 'none';
    return;
  }

  if (running) {
    h += '<div class="ac-dim">&#9203; 正在生成… 本页每 5 秒自动刷新（不用手动点）。</div>';
    box.innerHTML = h;
    if (badge) { badge.style.display = ''; badge.textContent = '生成中…'; }
    acScheduleRefPoll();
    return;
  }
  if (rf.gen_status === 'failed') {
    h += '<div class="ac-gap ac-gap-shoot"><div class="ac-gap-h">生成失败</div>' +
      '<div>' + escapeHtml(rf.gen_error || '未知原因') + '</div></div>';
    box.innerHTML = h;
    if (badge) { badge.style.display = ''; badge.textContent = '失败'; }
    return;
  }

  if (badge) {
    badge.style.display = '';
    badge.textContent = rf.timeline_count + ' 镜 · ' + rf.gap_count + ' 缺口' +
      (rf.issues && rf.issues.length ? ' · ' + rf.issues.length + ' 提醒' : '');
  }
  h += '<div class="ac-dim" style="margin-bottom:8px;">' +
    '生成 ' + escapeHtml(acFmtTime(rf.generated_at)) +
    '｜模型 <code>' + escapeHtml(rf.model || '') + '</code>' +
    '｜耗时 ' + acSec(rf.seconds) +
    (rf.gen_cost ? '｜' + (rf.gen_cost.input_tokens || 0) + ' in / ' + (rf.gen_cost.output_tokens || 0) + ' out tokens' : '') +
    '</div>';

  // 可预览性
  h += '<div style="margin-bottom:8px;">' +
    (rf.renderable
      ? '<span class="ac-pill ac-pill-ok">&#10003; 可整片进工作台预览</span>'
      : '<span class="ac-pill ac-pill-warn">&#9888; ' + rf.blocked_seqs.length + ' 条镜缺素材，暂不能整片预览</span>') +
    '<span class="ac-pill">缺配音 ' + ((rf.gap_kinds && rf.gap_kinds.tts) || 0) + '</span>' +
    '<span class="ac-pill">缺画面 ' + ((rf.gap_kinds && rf.gap_kinds.material) || 0) + '</span>' +
    '<span class="ac-pill">缺特效 ' + ((rf.gap_kinds && rf.gap_kinds.effect) || 0) + '</span>' +
    '</div>';

  // overall
  var ov = rf.overall || {};
  if (ov.video_type || ov.core_structure) {
    h += '<div class="ac-sub">视频 overall</div>';
    var kv = [['类型', ov.video_type], ['时长', ov.duration != null ? acSec(ov.duration) : ''],
      ['画幅', ov.ratio], ['核心结构', ov.core_structure], ['整体节奏', ov.rhythm]];
    for (var k = 0; k < kv.length; k++) {
      if (!kv[k][1]) continue;
      h += '<div class="ac-kv"><i>' + kv[k][0] + '</i><span>' + escapeHtml(String(kv[k][1])) + '</span></div>';
    }
  }

  // timeline
  var tl = rf.timeline || [];
  if (tl.length) {
    h += '<div class="ac-sub">逐镜剪辑脚本（' + tl.length + ' 镜）</div>';
    h += '<div class="ac-shot-wrap"><table><thead><tr>' +
      '<th>镜</th><th>时间</th><th>素材</th><th>单元</th><th>入出点</th><th>落位</th>' +
      '<th>剪辑手法</th><th>字幕</th></tr></thead><tbody>';
    for (var t = 0; t < tl.length; t++) {
      var x = tl[t];
      h += '<tr>' +
        '<td class="ac-seq">#' + x.seq + '<br><span class="ac-dim">剧本#' + (x.source_seq != null ? x.source_seq : '-') + '</span></td>' +
        '<td class="ac-dim">' + acSec(x.start) + '<br>&#8594;' + acSec(x.end) + '</td>' +
        '<td>' + escapeHtml(acMatName(x.material_id)) + '</td>' +
        '<td class="ac-dim">' + (x.unit_index != null ? '#' + x.unit_index : '-') + '</td>' +
        '<td class="ac-dim ac-mono">' + Number(x.in_offset || 0).toFixed(1) + '-' + Number(x.out_offset || 0).toFixed(1) + '</td>' +
        '<td><span class="ac-band">' + escapeHtml(x.band || 'C') + '</span></td>' +
        '<td>' + escapeHtml(x.visual_note || '-') + '</td>' +
        '<td>' + escapeHtml((x.subtitle_text || '-').replace(/\n/g, ' / ')) +
        '<br><span class="ac-dim">' + escapeHtml([x.subtitle_style, x.subtitle_position].filter(function (y) { return !!y; }).join('·')) + '</span></td>' +
        '</tr>';
    }
    h += '</tbody></table></div>';

    // 选材理由
    var reasons = [];
    for (var r2 = 0; r2 < tl.length; r2++) {
      if (tl[r2].match_reason) reasons.push('#' + tl[r2].seq + '（剧本#' + tl[r2].source_seq + '）' + tl[r2].match_reason);
    }
    if (reasons.length) {
      h += '<div class="ac-sub">选材理由（人审用）</div><div class="ac-dim">';
      for (var r3 = 0; r3 < reasons.length; r3++) h += '&#8226; ' + escapeHtml(reasons[r3]) + '<br>';
      h += '</div>';
    }
  }

  // 素材分组
  var mm = rf.material_map || [];
  if (mm.length) {
    h += '<div class="ac-sub">素材清单（本片实际用到）</div>';
    for (var g = 0; g < mm.length; g++) {
      var grp = mm[g];
      h += '<div class="ac-kv"><i>' + escapeHtml(grp.role || '-') + '</i><span><b>' +
        escapeHtml(grp.label || '') + '</b>' + (grp.note ? '<br>' + escapeHtml(grp.note) : '') + '<br>';
      var ids = grp.material_ids || [];
      for (var m2 = 0; m2 < ids.length; m2++) {
        h += '<span class="ac-pill">' + escapeHtml(acMatName(ids[m2])) + '</span>';
      }
      h += '</span></div>';
    }
  }

  // 节奏
  var rs = rf.rhythm_notes || [];
  if (rs.length) {
    h += '<div class="ac-sub">节奏设计</div><div class="ac-dim">';
    for (var q = 0; q < rs.length; q++) h += (q + 1) + '. ' + escapeHtml(rs[q]) + '<br>';
    h += '</div>';
  }

  // 字幕规范
  var ss = rf.subtitle_spec || {};
  if (Object.keys(ss).length) {
    h += '<div class="ac-sub">字幕规范</div>';
    var pairs = [['字体', ss.font], ['位置', ss.position], ['动画', ss.animation], ['字号', ss.size]];
    var cols = ss.colors;
    if (cols) { if (!(cols instanceof Array)) cols = [cols]; pairs.push(['配色', cols.join('；')]); }
    for (var p2 = 0; p2 < pairs.length; p2++) {
      if (!pairs[p2][1]) continue;
      h += '<div class="ac-kv"><i>' + pairs[p2][0] + '</i><span>' + escapeHtml(String(pairs[p2][1])) + '</span></div>';
    }
  }

  // 特效
  var el = rf.effect_list || [];
  if (el.length) {
    h += '<div class="ac-sub">特效清单（' + el.length + '）</div>';
    for (var e2 = 0; e2 < el.length; e2++) {
      var it = el[e2];
      if (typeof it === 'object' && it) {
        h += '<div class="ac-kv"><i>' + escapeHtml(String(it.at || '-')) + '</i><span><b>' +
          escapeHtml(String(it.name || '')) + '</b>' + (it.note ? ' — ' + escapeHtml(String(it.note)) : '') +
          '</span></div>';
      } else {
        h += '<div class="ac-dim">&#8226; ' + escapeHtml(String(it)) + '</div>';
      }
    }
  }

  // ★ 需要补的能力
  var gaps = rf.gaps || [];
  h += '<div class="ac-sub">需要补的能力（' + gaps.length + '）</div>';
  if (!gaps.length) {
    h += '<div class="ac-dim">没有发现缺口 —— 声音和画面都齐了。</div>';
  } else {
    h += '<div class="ac-dim" style="margin-bottom:6px;">标 <span class="ac-tag-auto">自动诊断</span> ' +
      '的是代码按实测数据推出来的（素材有没有音轨/人声、时长够不够），不是模型猜的。</div>';
    var order = ['tts', 'shoot', 'stock', 'effect', 'reuse'];
    for (var o = 0; o < order.length; o++) {
      for (var gi = 0; gi < gaps.length; gi++) {
        if ((gaps[gi].action || 'shoot') === order[o]) h += acGapHtml(gaps[gi]);
      }
    }
  }

  // 自动校验提醒
  if (rf.issues && rf.issues.length) {
    h += '<div class="ac-sub">自动校验提醒（' + rf.issues.length + '）</div>';
    for (var ii = 0; ii < rf.issues.length; ii++) {
      h += '<div class="ac-dim">&#9888; ' + escapeHtml(rf.issues[ii]) + '</div>';
    }
  }

  box.innerHTML = h;
  acScheduleRefPoll();
}

function aiclipGenReference() {
  if (!aiclipProjectId) { showToast('先打开一个项目', 'error'); return; }
  var req = acEl('aiclip-req-input');
  var body = {};
  if (req && req.value.trim()) body.requirement = req.value.trim();
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/reference', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast(json.error || '生成失败', 'error'); return; }
      showToast('已开始生成，约 2 分钟');
      if (aiclipReference) aiclipReference.gen_status = 'generating';
      aiclipRenderReference();
      acScheduleRefPoll(true);
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

function acScheduleRefPoll(force) {
  if (!aiclipProjectId) return;
  var running = !!(aiclipReference && aiclipReference.gen_status === 'generating');
  if (!running) return;
  if (acRefTimer && !force) return;
  acRefTimer = setTimeout(function () {
    acRefTimer = null;
    fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/reference?full=1')
      .then(function (r) { return r.json(); })
      .then(function (json) {
        if (!json.success) return;
        var before = aiclipReference && aiclipReference.gen_status;
        aiclipReference = json.data;
        aiclipRenderReference();
        if (before === 'generating' && aiclipReference && aiclipReference.gen_status !== 'generating') {
          if (aiclipReference.gen_status === 'done') {
            showToast('参考脚本生成完成：' + aiclipReference.timeline_count + ' 镜 / ' +
              aiclipReference.gap_count + ' 个缺口', 'success');
          } else {
            showToast('生成失败：' + (aiclipReference.gen_error || ''), 'error');
          }
          aiclipReloadDetail();
        }
      })
      .catch(function () { acScheduleRefPoll(true); });
  }, 5000);
}

// ==================== P5c：TTS 语音（一镜一段旁白） ====================
// 爸爸 2026-09-17：「请你再给加一个子页面用来生成 tts 的语音」
//                「在参考脚本生成下面得有一个导出 需要生成 tts 语音的文案或者台词」
//                「导出的东西可用给 tts 生成页面处理 生成每一段的 tts 还可以预览」
//                「按镜头一段」
// 台词在本页**只读** —— 单一数据源是参考脚本（要改就回那一页改，再重新导出）。
// 「导出」= 把参考脚本每镜的 subtitle_text 对齐进 audio_tracks(kind='tts')，幂等。
var AC_TTS_STATUS = {
  pending: { text: '待生成', cls: '' },
  generating: { text: '合成中…', cls: 'ac-pill-warn' },
  done: { text: '已生成', cls: 'ac-pill-ok' },
  failed: { text: '失败', cls: 'ac-pill-bad' }
};

function aiclipLoadTts() {
  if (!aiclipProjectId) return;
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/tts')
    .then(function (r) { return r.json(); })
    .then(function (json) {
      aiclipTts = json.success ? json.data : null;
      acTtsDefaultSelect();
      aiclipRenderTts();
    })
    .catch(function () { aiclipRenderTts(); });
}

/** 默认勾选：② 判定「缺配音」的段（其余留给用户自己决定） */
function acTtsDefaultSelect() {
  var segs = (aiclipTts && aiclipTts.segments) || [];
  for (var i = 0; i < segs.length; i++) {
    var s = segs[i];
    if (acTtsSel[s.seq] === undefined) acTtsSel[s.seq] = !!s.need_tts;
  }
}

function acTtsPick(seq, on) { acTtsSel[seq] = !!on; acTtsToolbarStats(); }

function acTtsPicked() {
  var out = [];
  for (var k in acTtsSel) { if (acTtsSel[k]) out.push(Number(k)); }
  return out.sort(function (a, b) { return a - b; });
}

function acTtsToolbarStats() {
  var btn = acEl('ac-tts-picked');
  if (btn) btn.textContent = '生成本页勾选（' + acTtsPicked().length + '）';
}

function acTtsVoice() { var el = acEl('ac-tts-voice'); return el ? el.value : null; }

function acTtsRate() {
  var el = acEl('ac-tts-rate');
  var v = el ? parseFloat(el.value) : NaN;
  return isNaN(v) ? null : v;
}

function acTtsSegBySeq(seq) {
  var segs = (aiclipTts && aiclipTts.segments) || [];
  for (var i = 0; i < segs.length; i++) {
    if (Number(segs[i].seq) === Number(seq)) return segs[i];
  }
  return null;
}

function aiclipRenderTts() {
  var box = acEl('aiclip-tts-panel');
  if (!box) return;
  var badge = acEl('aiclip-tts-badge');
  var t = aiclipTts;

  function empty(html) {
    box.innerHTML = '<div class="ac-tts-empty">' + html + '</div>';
    if (badge) badge.style.display = 'none';
  }
  if (!t) { empty('TTS 清单加载中…'); return; }

  var meta = t.meta || {};
  if (!meta.reference_id) {
    empty('还没有参考脚本。<br>先到「参考脚本生成」跑一次，再点那一页的 ' +
      '<b>&#128266; 导出 TTS 台词</b>。');
    return;
  }
  var segs = t.segments || [];
  if (!segs.length) {
    empty('参考脚本里没有可配音的台词 —— ' + (meta.shots_total || 0) +
      ' 镜的 subtitle_text 都是空的。');
    return;
  }

  var st = t.stats || {};
  var batch = t.batch || {};
  var running = !!batch.running;
  if (badge) {
    badge.style.display = '';
    badge.textContent = st.total + ' 段 · 已生成 ' + st.done +
      (st.failed ? ' · 失败 ' + st.failed : '') +
      (running ? ' · 合成中 ' + (batch.done || 0) + '/' + (batch.total || 0) : '');
  }

  var h = '<div class="ac-tts-toolbar">';
  h += '<label>音色</label><select id="ac-tts-voice">';
  var voices = t.voices || [];
  for (var v = 0; v < voices.length; v++) {
    h += '<option value="' + escapeHtml(voices[v].id) + '"' +
      (voices[v].id === t.default_voice ? ' selected' : '') + '>' +
      escapeHtml(voices[v].name) + ' · ' + escapeHtml(voices[v].desc || '') + '</option>';
  }
  h += '</select>';
  h += '<label>语速</label><input type="number" id="ac-tts-rate" step="0.02" min="0.5" max="2" value="' +
    Number(t.default_rate || 0.88) + '">';
  h += '<button class="btn btn-primary btn-sm" id="ac-tts-picked"' +
    (running ? ' disabled' : '') + ' onclick="aiclipGenPickedTts()">生成本页勾选（' +
    acTtsPicked().length + '）</button>';
  h += '<button class="btn btn-secondary btn-sm" onclick="acTtsRunBatch({all:true})">全部生成</button>';
  h += '<button class="btn btn-secondary btn-sm" onclick="aiclipExportTts()">&#8635; 重新导出</button>';
  h += '<span class="ac-tts-stats">' +
    '<span class="ac-pill ac-pill-ok">已生成 ' + st.done + '</span>' +
    '<span class="ac-pill">待生成 ' + st.pending + '</span>' +
    (st.failed ? '<span class="ac-pill ac-pill-bad">失败 ' + st.failed + '</span>' : '') +
    '<span class="ac-pill">共 ' + st.chars + ' 字</span>' +
    (st.audio_seconds ? '<span class="ac-pill">音频 ' + acSec(st.audio_seconds) + '</span>' : '') +
    '</span></div>';

  if (running) {
    h += '<div class="ac-dim" style="margin-bottom:8px;">&#9203; 批量合成中（#' +
      (batch.current != null ? batch.current : '-') + '）· 本页每 3 秒自动刷新。' +
      'CosyVoice 逐段串行合成，几十段要几分钟。</div>';
  }

  h += '<div class="ac-tts-list">';
  for (var i = 0; i < segs.length; i++) h += acTtsRowHtml(segs[i]);
  h += '</div>';

  if (batch.errors && batch.errors.length) {
    h += '<div class="ac-tts-err" style="margin-top:10px;">上一轮批量合成的失败：' +
      escapeHtml(batch.errors.join(' ｜ ')) + '</div>';
  }
  if (t.orphan_seqs && t.orphan_seqs.length) {
    h += '<div class="ac-dim" style="margin-top:10px;">&#9888; 有 ' + t.orphan_seqs.length +
      ' 段已落库但参考脚本里已经没有（#' + t.orphan_seqs.join(' #') +
      '）—— 点「重新导出」会清掉它们。</div>';
  }
  box.innerHTML = h;
  acScheduleTtsPoll();
}

function acTtsRowHtml(s) {
  var st = s.status || 'pending';
  var stt = AC_TTS_STATUS[st] || AC_TTS_STATUS.pending;
  var h = '<div class="ac-tts-row' + (s.need_tts ? ' is-need' : '') +
    (st === 'done' ? ' is-done' : '') + '" data-tts-seq="' + s.seq + '">';
  h += '<input type="checkbox" class="ac-tts-check" data-tts-pick="' + s.seq + '"' +
    (acTtsSel[s.seq] ? ' checked' : '') +
    ' onchange="acTtsPick(' + s.seq + ',this.checked)">';
  h += '<div class="ac-tts-seq"><b>#' + s.seq + '</b>镜头</div>';
  h += '<div class="ac-tts-body">';
  h += '<div class="ac-tts-text">' + escapeHtml(s.text) + '</div>';
  h += '<div class="ac-tts-meta">';
  h += '<span class="ac-pill ' + stt.cls + '">' + stt.text + '</span>';
  h += '<span>' + s.chars + ' 字</span>';
  h += '<span>画面 ' + acSec(s.start) + ' &#8594; ' + acSec(s.end) + '</span>';
  h += '<span>落位 ' + escapeHtml(s.band || 'C') + '</span>';
  if (s.need_tts) h += '<span class="ac-pill">&#9878; ② 判定缺配音</span>';
  if (s.too_long) h += '<span class="ac-pill ac-pill-warn">台词偏长，建议回参考脚本拆镜</span>';
  if (!s.synced) h += '<span class="ac-pill ac-pill-warn">尚未导出</span>';
  if (s.audio_duration) h += '<span>音频 ' + acSec(s.audio_duration) + '</span>';
  if (st === 'done' && s.voice) {
    h += '<span>' + escapeHtml(s.voice) + (s.rate ? ' · ' + s.rate : '') + '</span>';
  }
  h += '</div>';
  if (st === 'done' && s.audio_url) {
    h += '<div class="ac-tts-audio">' +
      '<audio controls preload="none" src="' + escapeHtml(s.audio_url) + '?v=' +
      encodeURIComponent(s.gen_at || '') + '"></audio>' +
      '<a class="btn btn-secondary btn-xs" href="' + escapeHtml(s.audio_url) +
      '?download=1">&#11015; wav</a></div>';
  }
  if (s.gen_error) {
    h += '<div class="ac-tts-err">' + escapeHtml(s.gen_error) + '</div>';
  }
  h += '</div>';
  h += '<div class="ac-tts-acts">';
  h += '<button class="btn ' + (st === 'done' ? 'btn-secondary' : 'btn-primary') +
    ' btn-xs' + (st === 'generating' ? ' ac-busy' : '') +
    '" onclick="aiclipGenTts(' + s.seq + ')">' +
    (st === 'generating' ? '合成中' : (st === 'done' ? '重生成' : '生成')) + '</button>';
  if (st === 'done') {
    h += '<button class="btn btn-secondary btn-xs" onclick="aiclipDelTts(' + s.seq +
      ')">删除</button>';
  }
  h += '</div></div>';
  return h;
}

/** 「导出」：参考脚本台词 → TTS 清单（幂等）。cb 可选，成功后调用。 */
function aiclipExportTts(cb) {
  if (!aiclipProjectId) { showToast('先打开一个项目', 'error'); return; }
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/tts/sync',
    { method: 'POST' })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast(json.error || '导出失败', 'error'); return; }
      aiclipTts = json.data;
      acTtsDefaultSelect();
      var page = acEl('aiclip-page-tts');
      var onTts = page && page.style.display !== 'none';
      if (!onTts && typeof cb !== 'function') aiclipShowPage('tts');
      aiclipRenderTts();
      if (typeof cb !== 'function') {
        var c = json.changed || {};
        showToast('已导出 ' + (c.total || 0) + ' 段台词到 TTS 页' +
          (c.added ? '（新增 ' + c.added + '）' : '') +
          (c.updated ? '（更新 ' + c.updated + '）' : '') +
          (c.removed ? '（移除 ' + c.removed + '）' : ''), 'success');
      }
      if (typeof cb === 'function') cb();
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

/** 单段合成（同步 —— 几秒，前端转圈等结果） */
function aiclipGenTts(seq, force) {
  if (!aiclipProjectId) return;
  var s = acTtsSegBySeq(seq);
  if (!s) return;
  if (!s.track_id) {
    // 这段还没落库 → 先导出一次再续上合成（toast 说清楚，不做静默写库）
    showToast('#' + seq + ' 还没导出，已先做一次导出', 'warn');
    aiclipExportTts(function () { aiclipGenTts(seq, force); });
    return;
  }
  s.status = 'generating';
  aiclipRenderTts();
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) +
        '/tts/' + encodeURIComponent(s.track_id) + '/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ voice: acTtsVoice(), rate: acTtsRate(), force: !!force })
  })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) {
        showToast(json.error || '合成失败', 'error');
        aiclipLoadTts();
        return;
      }
      showToast('#' + seq + ' 合成完成（' + acSec((json.data || {}).audio_duration) + '）',
        'success');
      aiclipLoadTts();
    })
    .catch(function (e) {
      showToast('请求失败: ' + e.message, 'error');
      aiclipLoadTts();
    });
}

function aiclipGenPickedTts() {
  var ids = acTtsPicked();
  if (!ids.length) { showToast('先勾几段，或直接点「全部生成」', 'warn'); return; }
  acTtsRunBatch({ ids: ids, voice: acTtsVoice(), rate: acTtsRate() });
}

/** 批量合成：先导出一次（保证每段都有 track），再交给后台逐段串行跑。 */
function acTtsRunBatch(body) {
  if (!aiclipProjectId) return;
  aiclipExportTts(function () {
    fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/tts/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        if (!json.success) { showToast(json.error || '批量合成没起来', 'error'); return; }
        showToast('已开始批量合成 —— CosyVoice 逐段串行，本页每 3 秒自动刷新');
        aiclipLoadTts();
        acScheduleTtsPoll(true);
      })
      .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
  });
}

function aiclipDelTts(seq) {
  var s = acTtsSegBySeq(seq);
  if (!s || !s.track_id) return;
  if (!window.confirm('删掉 #' + seq + ' 这一段（连带 wav 文件）？')) return;
  fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) +
        '/tts/' + encodeURIComponent(s.track_id), { method: 'DELETE' })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (!json.success) { showToast(json.error || '删除失败', 'error'); return; }
      aiclipTts = json.data;
      aiclipRenderTts();
      showToast('已删除 #' + seq, 'success');
    })
    .catch(function (e) { showToast('请求失败: ' + e.message, 'error'); });
}

function acScheduleTtsPoll(force) {
  if (!aiclipProjectId) return;
  var running = !!(aiclipTts && aiclipTts.batch && aiclipTts.batch.running);
  if (!running) return;
  if (acTtsTimer && !force) return;
  acTtsTimer = setTimeout(function () {
    acTtsTimer = null;
    fetch('/api/aiclip/projects/' + encodeURIComponent(aiclipProjectId) + '/tts')
      .then(function (r) { return r.json(); })
      .then(function (json) {
        if (!json.success) return;
        var was = !!(aiclipTts && aiclipTts.batch && aiclipTts.batch.running);
        aiclipTts = json.data;
        aiclipRenderTts();
        var now = !!(aiclipTts && aiclipTts.batch && aiclipTts.batch.running);
        if (was && !now) {
          var b = aiclipTts.batch || {};
          if (b.failed) {
            showToast('批量合成结束：成功 ' + (b.done || 0) + ' / 失败 ' + b.failed, 'warn');
          } else {
            showToast('批量合成完成：' + (b.done || 0) + ' 段', 'success');
          }
          aiclipReloadDetail();
        }
      })
      .catch(function () { acScheduleTtsPoll(true); });
  }, 3000);
}

// ESC 返回列表
document.addEventListener('keydown', function (e) {
  if (e.key !== 'Escape') return;
  var mk = acEl('aiclip-mat-mask');
  if (mk) { aiclipCloseMaterial(); return; }
  var onPage = false;
  Object.keys(AC_PAGES).forEach(function (k) {
    var el = acEl(AC_PAGES[k]);
    if (el && el.style.display !== 'none') onPage = true;
  });
  if (onPage) aiclipShowList();
});
