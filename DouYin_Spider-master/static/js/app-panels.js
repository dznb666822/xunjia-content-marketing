// ==================== Analysis Section ====================
var currentAnalysisVideoId = null;

function loadAnalysisHistory() {
    var container = document.getElementById('analysis-history-list');
    if (!container) return;
    container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-hint);">加载中...</div>';

    fetch('/api/analysis/history')
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (!json.success) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
                return;
            }
            var data = json.data || [];
            if (data.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">暂无分析记录<br><small>在监听中心分析视频后这里会显示历史</small></div>';
                return;
            }
            var html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:12px;">';
            for (var i = 0; i < data.length; i++) {
                var v = data[i];
                var desc = (v.desc || '无标题');
                var like = fmtCount(v.like_count || v.digg_count) || '0';
                var play = fmtCount(v.play_count);
                var frameUrl = v.first_frame_url || v.cover;
                var coverImg = frameUrl
                    ? '<img src="' + escapeHtml(frameUrl) + '" data-cover="' + escapeHtml(v.cover || '') + '" style="width:100%;height:100%;object-fit:cover;" onerror="if(this.dataset.cover && this.src!==this.dataset.cover){this.src=this.dataset.cover;}else{this.onerror=null;this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';}" alt="">'
                    : '';
                var coverFallback = '<div style="display:' + (frameUrl ? 'none' : 'flex') + ';width:100%;height:100%;align-items:center;justify-content:center;background:linear-gradient(135deg,#eef2f7,#e2e8f0);color:#94a3b8;font-size:11px;">无封面</div>';

                html += '<div class="work-card" onclick="showAnalysisDetail(\'' + v.id + '\')" title="' + escapeHtml(desc) + '" style="display:block;padding:0;margin:0;border-radius:12px;overflow:hidden;cursor:pointer;border:1px solid var(--border);background:#fff;">';
                html += '<div style="position:relative;aspect-ratio:9/16;background:#f1f5f9;">';
                html += coverImg + coverFallback;
                html += '<div style="position:absolute;left:0;right:0;bottom:0;padding:22px 8px 8px;background:linear-gradient(transparent,rgba(0,0,0,0.65));color:#fff;font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:space-between;">';
                html += '<span>&hearts; ' + like + '</span>';
                if (play) html += '<span style="font-weight:400;opacity:0.85;">' + play + '</span>';
                html += '</div>';
                html += '</div></div>';
            }
            html += '</div>';
            container.innerHTML = html;
        })
        .catch(function (e) {
            container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败: ' + e.message + '</div>';
        });
}

function openAnalysisModal() {
    var modal = document.getElementById('analysis-detail-modal');
    if (modal) modal.style.display = 'flex';
}

function closeAnalysisModal() {
    var modal = document.getElementById('analysis-detail-modal');
    if (modal) modal.style.display = 'none';
}

function showAnalysisDetail(videoId) {
    var body = document.getElementById('analysis-detail-modal-body');
    if (!body) return;
    body.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-hint);">加载中...</div>';
    openAnalysisModal();

    fetch('/api/analysis/result/' + encodeURIComponent(videoId))
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (!json.success) {
                body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
                return;
            }
            var data = json.data || {};
            // Set as current for cross-panel use
            currentAnalysisVideoId = videoId;
            renderAnalysisDetail(data);
            // Highlight selected item
            highlightHistoryItem('analysis-history-list', videoId);
        })
        .catch(function (e) {
            body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
        });
}

function renderAnalysisDetail(data) {
    var container = document.getElementById('analysis-detail-modal-body');
    if (!container) return;

    var textStructure = data.text_structure || {};
    var hook = textStructure.hook || '';
    var body = textStructure.body || '';
    var cta = textStructure.cta || '';
    var videoType = data.video_type || '';
    var sceneDesc = data.scene_desc || '';
    var coverDesc = data.cover_desc || '';
    var mood = data.mood || '';
    var title = (data.desc || data.title || '--').substring(0, 50);
    var productAnalysis = data.product_analysis || {};
    var marketingStrategy = data.marketing_strategy || {};
    var storyboard = data.storyboard || [];
    var frames = data.storyboard_frames || [];

    // 构建 shot_number -> frame_url 映射
    var frameMap = {};
    for (var fi = 0; fi < frames.length; fi++) {
        frameMap[frames[fi].shot_number] = frames[fi].frame_url || '';
    }

    var html = '<div style="display:flex;flex-direction:column;gap:12px;">';

    // 视频信息头
    html += '<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:rgba(240,244,252,0.4);border-radius:var(--radius-card);">';
    var headFrame = currentAnalysisVideoId ? '/api/videos/first-frame/' + currentAnalysisVideoId : (data.cover || '');
    if (headFrame) {
        html += '<img src="' + escapeHtml(headFrame) + '" data-cover="' + escapeHtml(data.cover || '') + '" style="width:56px;height:56px;object-fit:cover;border-radius:10px;" onerror="if(this.dataset.cover && this.src!==this.dataset.cover){this.src=this.dataset.cover;}else{this.style.display=\'none\';}">';
    }
    html += '<div>';
    html += '<div style="font-size:14px;font-weight:500;color:var(--text-primary);">' + escapeHtml(title) + '</div>';
    html += '<div style="font-size:11px;color:var(--text-hint);margin-top:2px;">' + escapeHtml(data.author || '--') + ' · ' + fmtCount(data.play_count) + ' 播放 · ' + fmtCount(data.digg_count) + ' 赞</div>';
    html += '</div></div>';

    // Badges
    html += '<div style="display:flex;gap:8px;flex-wrap:wrap;">';
    if (videoType) html += '<span style="font-size:11px;padding:3px 12px;border-radius:999px;color:var(--color-accent-text);background:rgba(180,195,230,0.25);font-weight:500;">' + escapeHtml(videoType) + '</span>';
    if (mood) html += '<span style="font-size:11px;padding:3px 12px;border-radius:999px;color:var(--color-accent2-text);background:rgba(175,210,220,0.25);font-weight:500;">' + escapeHtml(mood) + '</span>';
    html += '</div>';

    // 封面描述
    if (coverDesc) {
        html += '<div style="border:1px solid rgba(210,216,235,0.5);border-radius:var(--radius-card);padding:12px 14px;background:rgba(248,249,255,0.5);">';
        html += '<div style="font-size:11px;font-weight:500;color:var(--text-hint);margin-bottom:4px;">封面描述</div>';
        html += '<div style="font-size:12px;line-height:1.6;color:var(--text-secondary);">' + escapeHtml(coverDesc) + '</div></div>';
    }

    // 场景描述
    if (sceneDesc) {
        html += '<div style="border:1px solid rgba(210,216,235,0.5);border-radius:var(--radius-card);padding:12px 14px;background:rgba(248,249,255,0.5);">';
        html += '<div style="font-size:11px;font-weight:500;color:var(--text-hint);margin-bottom:4px;">场景描述</div>';
        html += '<div style="font-size:12px;line-height:1.6;color:var(--text-secondary);">' + escapeHtml(sceneDesc) + '</div></div>';
    }

    // Hook / Body / CTA
    html += '<div style="border:1px solid rgba(210,216,235,0.5);border-radius:var(--radius-card);padding:12px 14px;background:rgba(248,249,255,0.5);">';
    html += '<div style="font-size:11px;font-weight:500;color:var(--color-accent-text);margin-bottom:6px;">文本结构分析</div>';
    html += '<div style="font-size:12px;line-height:1.6;margin-bottom:4px;"><span style="color:var(--text-hint);">钩子: </span>' + (hook ? escapeHtml(hook) : '<span style="color:var(--text-hint);">无</span>') + '</div>';
    html += '<div style="font-size:12px;line-height:1.6;margin-bottom:4px;"><span style="color:var(--text-hint);">正文: </span>' + (body ? escapeHtml(body) : '<span style="color:var(--text-hint);">无</span>') + '</div>';
    html += '<div style="font-size:12px;line-height:1.6;"><span style="color:var(--text-hint);">CTA: </span>' + (cta ? escapeHtml(cta) : '<span style="color:var(--text-hint);">无</span>') + '</div>';
    html += '</div>';

    // 产品分析
    var pa = productAnalysis;
    if (pa.product_category || pa.target_audience || (pa.selling_points && pa.selling_points.length)) {
        html += '<div style="border:1px solid rgba(210,216,235,0.5);border-radius:var(--radius-card);padding:12px 14px;background:rgba(248,249,255,0.5);">';
        html += '<div style="font-size:11px;font-weight:500;color:var(--color-accent2-text);margin-bottom:6px;">产品分析</div>';
        if (pa.product_category) html += '<div style="font-size:12px;line-height:1.6;margin-bottom:3px;"><span style="color:var(--text-hint);">品类: </span>' + escapeHtml(pa.product_category) + '</div>';
        if (pa.target_audience) html += '<div style="font-size:12px;line-height:1.6;margin-bottom:3px;"><span style="color:var(--text-hint);">受众: </span>' + escapeHtml(pa.target_audience) + '</div>';
        if (pa.selling_points && pa.selling_points.length) {
            var sp = pa.selling_points;
            if (typeof sp === 'string') sp = sp.split('\n');
            html += '<div style="font-size:12px;line-height:1.6;"><span style="color:var(--text-hint);">卖点: </span>' + escapeHtml(sp.join('、')) + '</div>';
        }
        if (pa.pain_points && pa.pain_points.length) {
            var pp = pa.pain_points;
            if (typeof pp === 'string') pp = pp.split('\n');
            html += '<div style="font-size:12px;line-height:1.6;margin-top:3px;"><span style="color:var(--text-hint);">痛点: </span>' + escapeHtml(pp.join('、')) + '</div>';
        }
        html += '</div>';
    }

    // 营销策略
    var ms = marketingStrategy;
    if (ms.trust_building || ms.urgency_tactics || ms.interaction_guide) {
        html += '<div style="border:1px solid rgba(210,216,235,0.5);border-radius:var(--radius-card);padding:12px 14px;background:rgba(248,249,255,0.5);">';
        html += '<div style="font-size:11px;font-weight:500;color:var(--color-success-text);margin-bottom:6px;">营销策略</div>';
        if (ms.trust_building) html += '<div style="font-size:12px;line-height:1.6;margin-bottom:3px;"><span style="color:var(--text-hint);">信任建立: </span>' + escapeHtml(ms.trust_building) + '</div>';
        if (ms.urgency_tactics) html += '<div style="font-size:12px;line-height:1.6;margin-bottom:3px;"><span style="color:var(--text-hint);">紧迫感策略: </span>' + escapeHtml(ms.urgency_tactics) + '</div>';
        if (ms.interaction_guide) html += '<div style="font-size:12px;line-height:1.6;"><span style="color:var(--text-hint);">互动引导: </span>' + escapeHtml(ms.interaction_guide) + '</div>';
        html += '</div>';
    }

    // 分镜脚本表
    if (storyboard.length > 0) {
        html += '<div style="border:1px solid rgba(210,216,235,0.5);border-radius:var(--radius-card);padding:10px 10px 4px;background:rgba(248,249,255,0.5);">';
        html += '<div style="font-size:11px;font-weight:500;color:var(--text-hint);margin:0 6px 8px;">分镜脚本 (' + storyboard.length + ' 个分镜)</div>';

        for (var si = 0; si < storyboard.length; si++) {
            var s = storyboard[si];
            var shotNum = s.shot_number || (si + 1);
            var frameUrl = frameMap[shotNum] || '';

            html += '<div style="display:flex;gap:12px;margin-bottom:10px;padding:10px 12px;background:rgba(255,255,255,0.6);border-radius:var(--radius-tag);border:1px solid rgba(220,226,240,0.3);">';

            // 关键帧图片
            if (frameUrl) {
                html += '<div style="flex-shrink:0;">';
                html += '<div style="font-size:10px;font-weight:500;color:var(--text-hint);text-align:center;margin-bottom:4px;">#' + shotNum + '</div>';
                html += '<img src="' + escapeHtml(frameUrl) + '" style="width:120px;height:68px;object-fit:cover;border-radius:8px;border:1px solid rgba(220,226,240,0.4);" onerror="this.parentElement.innerHTML=\'<div style=width:120px;height:68px;display:flex;align-items:center;justify-content:center;background:rgba(230,235,248,0.3);border-radius:8px;font-size:10px;color:var(--text-hint);>无图片</div>\'">';
                html += '</div>';
            }

            // 分镜字段
            html += '<div style="flex:1;min-width:0;">';
            html += '<div style="font-size:12px;font-weight:500;color:var(--text-primary);margin-bottom:4px;">';
            html += '#' + shotNum + ' · ' + escapeHtml(s.shot_type || '--');
            if (s.camera_movement) html += ' · ' + escapeHtml(s.camera_movement);
            if (s.duration_seconds) html += ' · ' + s.duration_seconds + 's';
            html += '</div>';
            if (s.visual_content) html += '<div style="font-size:11px;line-height:1.5;color:var(--text-secondary);margin-bottom:3px;"><span style="color:var(--text-hint);">画面: </span>' + escapeHtml(s.visual_content) + '</div>';
            if (s.character_scene) html += '<div style="font-size:11px;line-height:1.5;color:var(--text-secondary);margin-bottom:3px;"><span style="color:var(--text-hint);">场景: </span>' + escapeHtml(s.character_scene) + '</div>';
            if (s.dialogue) html += '<div style="font-size:11px;line-height:1.5;color:var(--text-secondary);margin-bottom:3px;"><span style="color:var(--text-hint);">台词: </span>' + escapeHtml(s.dialogue) + '</div>';
            if (s.sound_effect) html += '<div style="font-size:11px;line-height:1.5;color:var(--text-hint);">音效: ' + escapeHtml(s.sound_effect) + '</div>';
            html += '</div>';
            html += '</div>'; // end shot card
        }
        html += '</div>';
    }

    // Buttons
    html += '<div style="display:flex;gap:8px;">';
    html += '<button class="btn btn-primary btn-sm" onclick="closeAnalysisModal();showScriptsDetail(\'' + currentAnalysisVideoId + '\');" style="font-size:11px;">生成剧本</button>';
    html += '<button class="btn btn-secondary btn-sm" onclick="exportAnalysisExcel()" style="font-size:11px;">导出Excel</button>';
    html += '</div>';

    html += '</div>';
    container.innerHTML = html;
}

// ==================== Scripts Section ====================
function loadScriptsHistory() {
    var container = document.getElementById('scripts-history-list');
    if (!container) return;
    container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-hint);">加载中...</div>';

    fetch('/api/scripts/history')
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (!json.success) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
                return;
            }
            var data = json.data || [];
            if (data.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">暂无脚本记录<br><small>在内容分析中选择视频生成剧本</small></div>';
                return;
            }
            var html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:12px;">';
            for (var i = 0; i < data.length; i++) {
                var v = data[i];
                var desc = (v.desc || '无标题');
                var cover = v.cover || '';
                var frameUrl = v.first_frame_url || cover;
                var coverImg = frameUrl
                    ? '<img src="' + escapeHtml(frameUrl) + '" data-cover="' + escapeHtml(cover) + '" style="width:100%;height:100%;object-fit:cover;" onerror="if(this.dataset.cover && this.src!==this.dataset.cover){this.src=this.dataset.cover;}else{this.onerror=null;this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';}" alt="">'
                    : '';
                var coverFallback = '<div style="display:' + (frameUrl ? 'none' : 'flex') + ';width:100%;height:100%;align-items:center;justify-content:center;background:linear-gradient(135deg,#eef2f7,#e2e8f0);color:#94a3b8;font-size:11px;">无封面</div>';

                html += '<div class="work-card" onclick="showScriptsDetail(\'' + v.id + '\')" title="' + escapeHtml(desc) + '" style="display:block;padding:0;margin:0;border-radius:12px;overflow:hidden;cursor:pointer;border:1px solid var(--border);background:#fff;">';
                html += '<div style="position:relative;aspect-ratio:9/16;background:#f1f5f9;">';
                html += coverImg + coverFallback;
                html += '<div style="position:absolute;left:0;right:0;bottom:0;padding:22px 8px 8px;background:linear-gradient(transparent,rgba(0,0,0,0.65));color:#fff;font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:space-between;">';
                html += '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escapeHtml(desc.substring(0, 20)) + '</span>';
                html += '</div>';
                html += '</div></div>';
            }
            html += '</div>';
            container.innerHTML = html;
        })
        .catch(function (e) {
            container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
        });
}

function openScriptsModal() {
    var modal = document.getElementById('scripts-detail-modal');
    if (modal) modal.style.display = 'flex';
}

function closeScriptsModal() {
    var modal = document.getElementById('scripts-detail-modal');
    if (modal) modal.style.display = 'none';
}

function showScriptsDetail(videoId) {
    var container = document.getElementById('scripts-detail-modal-body');
    if (!container) return;
    container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-hint);">加载中...</div>';
    openScriptsModal();

    // Set as current for generate button
    currentAnalysisVideoId = videoId;

    fetch('/api/scripts/' + encodeURIComponent(videoId))
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (!json.success) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">暂无脚本</div>';
                return;
            }
            var d = json.data || {};
            renderScriptsDetailContent(d, d.scripts || []);
            highlightHistoryItem('scripts-history-list', videoId);
        })
        .catch(function (e) {
            container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-hint);">加载失败</div>';
        });
}

function renderScriptsDetailContent(data, scripts) {
    var container = document.getElementById('scripts-detail-modal-body');
    if (!container) return;

    var html = '';
    var textStruct = data.text_structure || {};
    var frames = data.storyboard_frames || [];

    // 构建 shot_number -> frame_url 映射
    var frameMap = {};
    for (var fi = 0; fi < frames.length; fi++) {
        var f = frames[fi];
        frameMap[f.shot_number] = f.frame_url || '';
    }

    // 视频基本信息
    html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;padding:10px 14px;background:rgba(240,244,252,0.4);border-radius:var(--radius-card);">';
    var headFrame = currentAnalysisVideoId ? '/api/videos/first-frame/' + currentAnalysisVideoId : '';
    if (headFrame) {
        html += '<img src="' + escapeHtml(headFrame) + '" data-cover="' + escapeHtml(data.cover || '') + '" style="width:56px;height:56px;object-fit:cover;border-radius:10px;" onerror="if(this.dataset.cover && this.src!==this.dataset.cover){this.src=this.dataset.cover;}else{this.style.display=\'none\';}">';
    }
    html += '<div>';
    html += '<div style="font-size:14px;font-weight:500;color:var(--text-primary);">' + escapeHtml((data.desc || '无标题').substring(0, 50)) + '</div>';
    html += '<div style="font-size:11px;color:var(--text-hint);margin-top:2px;">' + escapeHtml(data.author || '--') + ' · ' + escapeHtml(data.video_type || '') + ' · ' + escapeHtml(data.mood || '') + '</div>';
    html += '</div></div>';

    // 改编文本结构
    if (textStruct.hook || textStruct.body || textStruct.cta) {
        html += '<div style="border:1px solid rgba(210,216,235,0.5);border-radius:var(--radius-card);padding:12px 14px;margin-bottom:12px;background:rgba(248,249,255,0.5);">';
        html += '<div style="font-size:11px;font-weight:500;color:var(--color-accent-text);margin-bottom:6px;">改编文本结构</div>';
        html += '<div style="font-size:12px;line-height:1.6;"><span style="color:var(--text-hint);">钩子: </span>' + escapeHtml(textStruct.hook || '--') + '</div>';
        html += '<div style="font-size:12px;line-height:1.6;"><span style="color:var(--text-hint);">正文: </span>' + escapeHtml(textStruct.body || '--') + '</div>';
        html += '<div style="font-size:12px;line-height:1.6;"><span style="color:var(--text-hint);">CTA: </span>' + escapeHtml(textStruct.cta || '--') + '</div>';
        html += '</div>';
    }

    // 每个版本
    for (var vi = 0; vi < scripts.length; vi++) {
        var v = scripts[vi];
        var angle = v.angle || ('版本 ' + (vi + 1));

        html += '<div style="border:1px solid rgba(210,216,235,0.5);border-radius:var(--radius-card);margin-bottom:14px;overflow:hidden;background:rgba(248,249,255,0.5);">';

        // 版本标题
        html += '<div style="padding:10px 14px;background:rgba(180,195,230,0.15);display:flex;justify-content:space-between;align-items:center;">';
        html += '<span style="font-weight:500;font-size:13px;color:var(--color-accent-text);">版本 ' + (v.version || (vi + 1)) + '</span>';
        html += '<span style="font-size:11px;color:var(--text-hint);">' + escapeHtml(angle) + '</span>';
        html += '</div>';

        // 切入角度描述
        html += '<div style="padding:8px 14px;font-size:11px;color:var(--text-secondary);line-height:1.5;border-bottom:1px solid rgba(220,226,240,0.3);">';
        html += '<span style="color:var(--text-hint);">切入角度: </span>' + escapeHtml(angle);
        html += '</div>';

        // 完整脚本
        if (v.full_script) {
            html += '<div style="padding:12px 14px;border-bottom:1px solid rgba(220,226,240,0.3);">';
            html += '<div style="font-size:11px;font-weight:500;color:var(--text-hint);margin-bottom:6px;">完整脚本</div>';
            html += '<div style="font-size:13px;line-height:1.8;white-space:pre-wrap;color:var(--text-primary);">' + escapeHtml(v.full_script) + '</div>';
            html += '</div>';
        }

        // 分镜脚本表
        var sb = v.storyboard || [];
        if (sb.length > 0) {
            html += '<div style="padding:8px 8px 4px;">';
            html += '<div style="font-size:11px;font-weight:500;color:var(--text-hint);margin:0 6px 8px;">改编分镜脚本 (' + sb.length + ' 个分镜)</div>';

            for (var si = 0; si < sb.length; si++) {
                var s = sb[si];
                var shotNum = s.shot_number || (si + 1);
                var frameUrl = frameMap[shotNum] || '';

                html += '<div style="display:flex;gap:12px;margin-bottom:10px;padding:10px 12px;background:rgba(255,255,255,0.6);border-radius:var(--radius-tag);border:1px solid rgba(220,226,240,0.3);">';

                // 关键帧图片
                if (frameUrl) {
                    html += '<div style="flex-shrink:0;">';
                    html += '<div style="font-size:10px;font-weight:500;color:var(--text-hint);text-align:center;margin-bottom:4px;">#' + shotNum + '</div>';
                    html += '<img src="' + escapeHtml(frameUrl) + '" style="width:120px;height:68px;object-fit:cover;border-radius:8px;border:1px solid rgba(220,226,240,0.4);" onerror="this.parentElement.innerHTML=\'<div style=width:120px;height:68px;display:flex;align-items:center;justify-content:center;background:rgba(230,235,248,0.3);border-radius:8px;font-size:10px;color:var(--text-hint);>无图片</div>\'">';
                    html += '</div>';
                }

                // 分镜详细字段
                html += '<div style="flex:1;min-width:0;">';
                html += '<div style="font-size:12px;font-weight:500;color:var(--text-primary);margin-bottom:4px;">';
                html += '#' + shotNum + ' · ' + escapeHtml(s.shot_type || '--');
                if (s.camera_movement) {
                    html += ' · ' + escapeHtml(s.camera_movement);
                }
                if (s.duration_seconds) {
                    html += ' · ' + s.duration_seconds + 's';
                }
                html += '</div>';

                if (s.visual_content) {
                    html += '<div style="font-size:11px;line-height:1.5;color:var(--text-secondary);margin-bottom:3px;">';
                    html += '<span style="color:var(--text-hint);">画面: </span>' + escapeHtml(s.visual_content);
                    html += '</div>';
                }
                if (s.character_scene) {
                    html += '<div style="font-size:11px;line-height:1.5;color:var(--text-secondary);margin-bottom:3px;">';
                    html += '<span style="color:var(--text-hint);">场景: </span>' + escapeHtml(s.character_scene);
                    html += '</div>';
                }
                if (s.dialogue) {
                    html += '<div style="font-size:11px;line-height:1.5;color:var(--text-secondary);margin-bottom:3px;">';
                    html += '<span style="color:var(--text-hint);">台词: </span>' + escapeHtml(s.dialogue);
                    html += '</div>';
                }
                if (s.sound_effect) {
                    html += '<div style="font-size:11px;line-height:1.5;color:var(--text-hint);">';
                    html += '音效: ' + escapeHtml(s.sound_effect);
                    html += '</div>';
                }
                html += '</div>';
                html += '</div>'; // end shot card
            }
            html += '</div>';
        }

        html += '</div>'; // end version card
    }

    if (scripts.length === 0) {
        html += '<div style="text-align:center;padding:40px;color:var(--text-hint);">暂无剧本内容</div>';
    } else {
        html += '<div style="display:flex;gap:8px;margin-top:8px;">';
        html += '<button class="btn btn-secondary btn-xs" onclick="exportScriptExcel()">导出Excel</button>';
        html += '</div>';
    }

    container.innerHTML = html;
}

// ==================== Shared helpers ====================
function setCurrentAnalysisVideo(videoId, data) {
    currentAnalysisVideoId = videoId;
}

function generateScriptFromModal() {
    if (!currentAnalysisVideoId) {
        showToast('请先选择视频', 'error');
        return;
    }
    var prompt = getVal('script-modal-prompt');
    var numVariants = parseInt(getVal('script-modal-variants')) || 1;

    spinner('spinner-scripts-modal', true);
    fetch('/api/scripts/generate-from-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            video_id: currentAnalysisVideoId,
            user_prompt: prompt,
            num_variants: numVariants
        })
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-scripts-modal', false);
            if (json.success) {
                showToast('剧本生成成功', 'success');
                showScriptsDetail(currentAnalysisVideoId);
                loadScriptsHistory();
            } else {
                showToast('生成失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-scripts-modal', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function exportScriptExcel() {
    if (!currentAnalysisVideoId) {
        showToast('请先选择视频', 'error');
        return;
    }
    window.open('/api/scripts/export/' + encodeURIComponent(currentAnalysisVideoId), '_blank');
}

function exportAnalysisExcel() {
    if (!currentAnalysisVideoId) {
        showToast('请先选择视频', 'error');
        return;
    }
    window.open('/api/analysis/export/' + encodeURIComponent(currentAnalysisVideoId), '_blank');
}

function highlightHistoryItem(listId, videoId) {
    var list = document.getElementById(listId);
    if (!list) return;
    var cards = list.querySelectorAll('.work-card');
    for (var i = 0; i < cards.length; i++) {
        if (cards[i].getAttribute('onclick') && cards[i].getAttribute('onclick').indexOf(videoId) > -1) {
            cards[i].style.borderColor = 'var(--color-accent)';
            cards[i].style.background = 'rgba(240,244,252,0.7)';
        } else {
            cards[i].style.borderColor = '';
            cards[i].style.background = '';
        }
    }
}

// ==================== Dashboard Section ====================
function loadDashboard() {
    var brandId = getVal('dash-brand');
    var competitorId = getVal('dash-competitor');
    var videoType = getVal('dash-video-type');
    var days = parseInt(getVal('dash-days')) || 30;

    var params = '?days=' + days;
    if (brandId) params += '&brand_id=' + encodeURIComponent(brandId);
    if (competitorId) params += '&competitor_id=' + encodeURIComponent(competitorId);
    if (videoType) params += '&video_type=' + encodeURIComponent(videoType);

    spinner('spinner-dash', true);
    fetch('/api/dashboard/video-stats' + params)
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-dash', false);
            if (json.success) {
                renderDashboardStats(json.data || []);
                renderDashboardVideoTable(json.data || []);
            } else {
                showToast('加载看板数据失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-dash', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function renderDashboardStats(videos) {
    var totalVideos = videos.length;
    var totalDigg = 0;
    var totalComment = 0;
    var totalShare = 0;

    for (var i = 0; i < videos.length; i++) {
        var s = videos[i].stats || {};
        totalDigg += parseInt(s.digg_count || 0);
        totalComment += parseInt(s.comment_count || 0);
        totalShare += parseInt(s.share_count || 0);
    }

    var totalPlays = totalDigg + totalComment + totalShare;
    var avgEngagement = totalVideos > 0 ? ((totalDigg + totalComment + totalShare) / totalVideos).toFixed(0) : '0';

    document.getElementById('stat-total-videos').textContent = fmtCount(totalVideos);
    document.getElementById('stat-total-plays').textContent = fmtCount(totalPlays);
    document.getElementById('stat-total-likes').textContent = fmtCount(totalDigg);
    document.getElementById('stat-avg-engagement').textContent = fmtCount(avgEngagement);
}

function renderDashboardVideoTable(videos) {
    var container = document.getElementById('dash-video-table');
    if (!container) return;

    if (!videos || videos.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">暂无数据</div>';
        return;
    }

    var html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<thead><tr>';
    html += '<th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);"><input type="checkbox" onchange="toggleCheckAll(\'dash-video-cb\', this)"></th>';
    html += '<th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);">视频</th>';
    html += '<th style="text-align:right;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);">点赞</th>';
    html += '<th style="text-align:right;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);">评论</th>';
    html += '<th style="text-align:right;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);">分享</th>';
    html += '<th style="text-align:center;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-dim);">类型</th>';
    html += '</tr></thead><tbody>';

    for (var i = 0; i < videos.length; i++) {
        var v = videos[i];
        var s = v.stats || {};
        var title = escapeHtml((v.title || '无标题').substring(0, 50));
        html += '<tr>';
        html += '<td style="padding:6px 10px;border-bottom:1px solid var(--border);"><input type="checkbox" class="dash-video-cb" value="' + (v.id || '') + '"></td>';
        html += '<td style="padding:6px 10px;border-bottom:1px solid var(--border);font-size:12px;">' + title + '</td>';
        html += '<td style="text-align:right;padding:6px 10px;border-bottom:1px solid var(--border);font-size:12px;">' + fmtCount(s.digg_count || 0) + '</td>';
        html += '<td style="text-align:right;padding:6px 10px;border-bottom:1px solid var(--border);font-size:12px;">' + fmtCount(s.comment_count || 0) + '</td>';
        html += '<td style="text-align:right;padding:6px 10px;border-bottom:1px solid var(--border);font-size:12px;">' + fmtCount(s.share_count || 0) + '</td>';
        html += '<td style="text-align:center;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;">' + escapeHtml(v.video_type || '-') + '</td>';
        html += '</tr>';
    }
    html += '</tbody></table>';
    container.innerHTML = html;
    document.getElementById('btn-ad-analyze').disabled = false;
}

function loadDashboardCharts() {
    var brandId = getVal('dash-brand');
    var days = parseInt(getVal('dash-days')) || 30;

    var params = '?days=' + days;
    if (brandId) params += '&brand_id=' + encodeURIComponent(brandId);

    fetch('/api/dashboard/video-stats' + params)
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (json.success) {
                renderTrendChart(json.data || []);
                renderBrandComparison(json.data || []);
            }
        })
        .catch(function (e) {
            console.error('加载图表失败:', e);
        });
}

function renderTrendChart(data) {
    var container = document.getElementById('trend-chart-container');
    if (!container) return;

    var dateMap = {};
    for (var i = 0; i < data.length; i++) {
        var v = data[i];
        var date = '';
        if (v.first_seen_at) date = v.first_seen_at.substring(0, 10);
        else if (v.created_at) date = v.created_at.substring(0, 10);
        if (!date) continue;
        if (!dateMap[date]) dateMap[date] = { count: 0, digg: 0 };
        dateMap[date].count += 1;
        var s = v.stats || {};
        dateMap[date].digg += parseInt(s.digg_count || 0);
    }

    var dates = Object.keys(dateMap).sort();
    var counts = [];
    var diggs = [];
    for (var d = 0; d < dates.length; d++) {
        counts.push(dateMap[dates[d]].count);
        diggs.push(dateMap[dates[d]].digg);
    }

    if (typeof Chart === 'undefined') {
        container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted);">Chart.js 未加载</div>';
        return;
    }

    var canvas = container.querySelector('canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'trend-chart-canvas';
        container.innerHTML = '';
        container.appendChild(canvas);
    }

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: '视频数',
                data: counts,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99,102,241,0.1)',
                fill: true,
                tension: 0.3
            }, {
                label: '点赞数',
                data: diggs,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16,185,129,0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

function renderBrandComparison(data) {
    var container = document.getElementById('brand-comparison-container');
    if (!container) return;

    var authorMap = {};
    for (var i = 0; i < data.length; i++) {
        var v = data[i];
        var author = v.author_name || '未知';
        if (!authorMap[author]) authorMap[author] = { count: 0, digg: 0 };
        authorMap[author].count += 1;
        var s = v.stats || {};
        authorMap[author].digg += parseInt(s.digg_count || 0);
    }

    var authors = Object.keys(authorMap);
    authors.sort(function (a, b) { return authorMap[b].count - authorMap[a].count; });
    authors = authors.slice(0, 10);

    var counts = [];
    for (var j = 0; j < authors.length; j++) {
        counts.push(authorMap[authors[j]].count);
    }

    if (typeof Chart === 'undefined') {
        container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted);">Chart.js 未加载</div>';
        return;
    }

    var canvas = container.querySelector('canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'brand-comp-canvas';
        container.innerHTML = '';
        container.appendChild(canvas);
    }

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: authors,
            datasets: [{
                label: '视频数',
                data: counts,
                backgroundColor: 'rgba(99,102,241,0.6)',
                borderColor: '#6366f1',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            indexAxis: 'y',
            plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

function refreshDashboard() {
    loadDashboard();
    loadDashboardCharts();
}

function onDashBrandChange() {
    var brandId = getVal('dash-brand');
    var compSelect = document.getElementById('dash-competitor');
    if (!compSelect) return;

    if (!brandId) {
        compSelect.innerHTML = '<option value="">-- 全部 --</option>';
        return;
    }

    compSelect.innerHTML = '<option value="">加载中...</option>';
    fetch('/api/competitors?brand_id=' + encodeURIComponent(brandId))
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            compSelect.innerHTML = '<option value="">-- 全部 --</option>';
            if (json.success) {
                var list = json.data || [];
                for (var i = 0; i < list.length; i++) {
                    var c = list[i];
                    compSelect.innerHTML += '<option value="' + c.id + '">' + escapeHtml(c.nickname || c.id) + '</option>';
                }
            }
        })
        .catch(function () {
            compSelect.innerHTML = '<option value="">-- 全部 --</option>';
        });
}

function collectStats() {
    spinner('spinner-dash', true);
    fetch('/api/dashboard/collect-stats', { method: 'POST' })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-dash', false);
            if (json.success) {
                var d = json.data || {};
                showToast('采集完成: 更新 ' + (d.updated_count || 0) + ' 条', 'success');
                loadDashboard();
            } else {
                showToast('采集失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-dash', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function adAnalyze() {
    var ids = getCheckedIds('dash-video-cb');
    if (ids.length === 0) { showToast('请先勾选视频', 'error'); return; }

    spinner('spinner-dash', true);
    fetch('/api/ad/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_ids: ids })
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-dash', false);
            var container = document.getElementById('ad-analysis-result');
            if (!container) return;
            if (json.success) {
                var html = '<div class="card" style="margin-top:10px;"><div class="card-header">投流分析结果</div>';
                html += '<div style="padding:10px 14px;font-size:13px;line-height:1.6;white-space:pre-wrap;">';
                html += escapeHtml(typeof json.data === 'string' ? json.data : JSON.stringify(json.data, null, 2));
                html += '</div></div>';
                container.innerHTML = html;
                showToast('投流分析完成', 'success');
            } else {
                showToast('分析失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-dash', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

// ==================== Initialization ====================
function init() {
    fetchAndPopulateBrands();
    loadMonitorBloggers();
}

init();
