// ==================== Monitor Bloggers Section ====================
var selectedMonitorBloggerId = null;

function loadMonitorBloggers() {
    fetch('/api/monitor/bloggers')
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (!json.success) {
                showToast('加载监听博主失败: ' + (json.error || '未知错误'), 'error');
                return;
            }
            var bloggers = json.data || [];
            var container = document.getElementById('monitor-bloggers-list');
            if (!container) return;

            if (bloggers.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted);">暂无监听博主 · 请手动添加博主链接</div>';
                return;
            }

            var html = '';
            for (var i = 0; i < bloggers.length; i++) {
                var b = bloggers[i];
                var bid = b.id || '';
                var avatar = b.avatar || '';
                var nickname = escapeHtml(b.nickname || '未知');
                var firstChar = nickname.charAt(0) || '?';
                var followers = fmtCount(b.follower_count || 0);
                var videoCount = b.video_count || 0;
                var isPaused = b.status === 'paused';
                var selectedClass = (bid === selectedMonitorBloggerId) ? ' selected' : '';

                html += '<div class="blogger-item' + selectedClass + '" data-blogger-id="' + bid + '" onclick="selectMonitorBlogger(\'' + bid + '\')" style="display:flex;align-items:center;gap:12px;padding:10px 12px;border-bottom:1px solid var(--border);cursor:pointer;transition:background 0.15s;">';
                if (avatar) {
                    html += '<img src="' + avatar + '" style="width:40px;height:40px;border-radius:50%;object-fit:cover;flex-shrink:0;" alt="">';
                } else {
                    html += '<div style="width:40px;height:40px;border-radius:50%;background:var(--accent);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:16px;flex-shrink:0;">' + firstChar + '</div>';
                }
                html += '<div style="flex:1;min-width:0;">';
                html += '<div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + nickname + '</div>';
                html += '<div style="font-size:11px;color:var(--text-dim);margin-top:2px;">粉丝 ' + followers + ' · 视频 ' + videoCount + '</div>';
                html += '</div>';
                html += '<button class="btn btn-sm ' + (isPaused ? 'btn-secondary' : 'btn-primary') + '" style="flex-shrink:0;font-size:11px;padding:4px 10px;" onclick="event.stopPropagation();toggleMonitorBlogger(\'' + bid + '\')" title="' + (isPaused ? '恢复监听' : '暂停监听') + '">' + (isPaused ? '&#9654;' : '&#9208;') + '</button>';
                html += '</div>';
            }
            container.innerHTML = html;
        })
        .catch(function (e) {
            showToast('请求监听博主失败: ' + e.message, 'error');
        });
}

function selectMonitorBlogger(bid) {
    selectedMonitorBloggerId = bid;
    // highlight selected
    var items = document.querySelectorAll('#monitor-bloggers-list .blogger-item');
    for (var i = 0; i < items.length; i++) {
        items[i].classList.remove('selected');
        if (items[i].getAttribute('data-blogger-id') === bid) {
            items[i].classList.add('selected');
        }
    }
    loadBloggerVideos(bid);
}

function addMonitorBlogger() {
    var userUrl = getVal('monitor-add-url');
    if (!userUrl) { showToast('请输入抖音用户链接', 'error'); return; }

    spinner('spinner-monitor-add', true);
    fetch('/api/monitor/bloggers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_url: userUrl })
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-monitor-add', false);
            if (json.success) {
                showToast('博主添加成功: ' + (json.data && json.data.nickname || ''), 'success');
                document.getElementById('monitor-add-url').value = '';
                loadMonitorBloggers();
            } else {
                showToast('添加失败: ' + (json.error || '未知错误'), 'error');
                showResult('result-monitor-add', json);
            }
        })
        .catch(function (e) {
            spinner('spinner-monitor-add', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function toggleMonitorBlogger(bid) {
    if (!bid) return;
    fetch('/api/monitor/bloggers/' + bid + '/toggle', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (json.success) {
                var newStatus = (json.data && json.data.status) || '';
                showToast(newStatus === 'paused' ? '已暂停监听' : '已恢复监听', 'success');
                loadMonitorBloggers();
            } else {
                showToast('操作失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            showToast('请求失败: ' + e.message, 'error');
        });
}

function loadBloggerVideos(bid) {
    if (!bid) return;
    var container = document.getElementById('monitor-blogger-videos');
    if (!container) return;
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">加载中...</div>';

    fetch('/api/monitor/bloggers/' + bid + '/videos')
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (!json.success) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">加载失败: ' + (json.error || '未知错误') + '</div>';
                return;
            }
            var videos = json.data || [];
            if (videos.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted);">暂无视频 · <a href="javascript:void(0)" onclick="fetchVideosForMonitorBlogger(\'' + bid + '\')" style="color:var(--accent);">点击从抖音拉取</a></div>';
                return;
            }

            var html = '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">';
            html += '<span style="font-size:12px;color:var(--text-dim);">共 ' + videos.length + ' 个视频</span>';
            html += '<button class="btn btn-secondary btn-sm" onclick="fetchVideosForMonitorBlogger(\'' + bid + '\')">&#128260; 拉取最新视频</button>';
            html += '</div>';

            for (var i = 0; i < videos.length; i++) {
                var v = videos[i];
                var awemeId = v.aweme_id || '';
                var videoDbId = v.id || '';
                var title = escapeHtml(v.title || '无标题');
                var cover = v.cover_url || '';
                var duration = fmtDuration(v.duration || 0);
                var stats = v.stats || {};
                var digg = fmtCount(stats.digg_count || 0);
                var comment = fmtCount(stats.comment_count || 0);
                var share = fmtCount(stats.share_count || 0);
                var date = '';
                if (v.first_seen_at) {
                    date = v.first_seen_at.substring(0, 10);
                } else if (v.created_at) {
                    date = v.created_at.substring(0, 10);
                }

                html += '<div class="monitor-video" style="display:flex;gap:12px;padding:10px;margin-bottom:8px;border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,0.02);">';
                // Cover
                html += '<div style="flex-shrink:0;position:relative;width:120px;height:160px;border-radius:6px;overflow:hidden;background:#1a1a2e;">';
                if (cover) {
                    html += '<img src="' + cover + '" style="width:100%;height:100%;object-fit:cover;" alt="">';
                } else {
                    html += '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:24px;">&#127916;</div>';
                }
                html += '<div style="position:absolute;bottom:4px;right:6px;background:rgba(0,0,0,0.7);color:#fff;font-size:10px;padding:2px 6px;border-radius:3px;">' + duration + '</div>';
                html += '</div>';
                // Info
                html += '<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:4px;">';
                html += '<div style="font-weight:600;font-size:13px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + title + '</div>';
                html += '<div style="font-size:11px;color:var(--text-dim);display:flex;gap:12px;">';
                html += '<span>&#10084; ' + digg + '</span>';
                html += '<span>&#128172; ' + comment + '</span>';
                html += '<span>&#128257; ' + share + '</span>';
                html += '</div>';
                if (date) {
                    html += '<div style="font-size:11px;color:var(--text-dim);">' + date + '</div>';
                }
                html += '<div style="margin-top:auto;display:flex;gap:8px;">';
                html += '<a href="https://www.douyin.com/video/' + awemeId + '" target="_blank" class="btn btn-sm" style="font-size:11px;padding:4px 10px;color:var(--accent);">查看</a>';
                html += '<button class="btn btn-sm btn-accent2" style="font-size:11px;padding:4px 10px;" onclick="analyzeMonitorVideo(\'' + awemeId + '\',\'' + videoDbId + '\')">&#128300; 分析</button>';
                html += '</div></div>';
                html += '</div>';
            }
            container.innerHTML = html;
        })
        .catch(function (e) {
            container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">加载失败: ' + e.message + '</div>';
        });
}

function fetchVideosForMonitorBlogger(bid) {
    if (!bid) return;
    showToast('正在从抖音拉取视频...', 'success');
    fetch('/api/competitors/' + bid + '/fetch-videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (json.success) {
                var newCount = (json.data && json.data.new_videos) || 0;
                showToast('拉取完成，新增 ' + newCount + ' 个视频', 'success');
                loadBloggerVideos(bid);
            } else {
                showToast('拉取失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            showToast('请求失败: ' + e.message, 'error');
        });
}

function analyzeMonitorVideo(awemeId, videoDbId) {
    if (!awemeId) { showToast('缺少视频 aweme_id', 'error'); return; }
    showToast('正在下载视频并分析...', 'success');

    // 切换到内容分析面板
    switchPanel('analysis');

    // 显示加载状态
    var resultsContainer = document.getElementById('analysis-results');
    if (resultsContainer) resultsContainer.innerHTML = '<div style="text-align:center;padding:40px;"><div class="spinner show"></div><div style="color:var(--text-muted);margin-top:12px;">正在下载视频到本地，然后进行内容分析...</div></div>';

    fetch('/api/video/download-and-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aweme_id: awemeId })
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (json.success) {
                showToast('视频分析完成！', 'success');
                showAnalysisResult(json.data);
                // 同步到脚本生成面板
                setCurrentAnalysisVideo(json.data.video_id, json.data);
            } else {
                if (resultsContainer) resultsContainer.innerHTML = '<div style="text-align:center;padding:30px;color:var(--danger);">分析失败: ' + (json.error || '未知错误') + '</div>';
                showToast('分析失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            if (resultsContainer) resultsContainer.innerHTML = '<div style="text-align:center;padding:30px;color:var(--danger);">请求失败: ' + e.message + '</div>';
            showToast('请求失败: ' + e.message, 'error');
        });
}

function showAnalysisResult(data) {
    var container = document.getElementById('analysis-results');
    if (!container) return;

    var analysis = data.analysis || data;
    var textStruct = analysis.text_structure || {};
    var prod = analysis.product_analysis || {};
    var mkt = analysis.marketing_strategy || {};
    var storyboard = analysis.storyboard || [];

    // 构建帧图片URL查找表
    var frameMap = {};
    var frames = data.storyboard_frames || [];
    for (var fi = 0; fi < frames.length; fi++) {
        frameMap[frames[fi].shot_number] = frames[fi].frame_url;
    }

    var html = '<div class="script-card" style="border-left:3px solid var(--success);">';
    html += '<div class="script-card-header"><span class="script-ver">分析结果: ' + (data.title || '未知标题') + '</span>';
    html += '<span style="font-size:12px;color:var(--text-muted);margin-left:8px;">@' + (data.author || '--') + '</span></div>';

    // 封面描述
    if (data.cover_desc) {
        html += '<div style="padding:8px 16px;background:var(--bg-hover);border-bottom:1px solid var(--border);font-size:13px;">';
        html += '<b>封面: </b><span style="color:var(--text-dim);">' + data.cover_desc + '</span>';
        html += '</div>';
    }

    // 基本信息
    html += '<div style="padding:12px 16px;border-bottom:1px solid var(--border);">';
    html += '<span style="font-weight:600;">类型: </span><span class="badge badge-primary">' + (analysis.video_type || '--') + '</span>';
    html += '<span style="font-weight:600;margin-left:16px;">情绪: </span><span class="badge badge-accent">' + (analysis.mood || '--') + '</span>';
    html += '<span style="font-weight:600;margin-left:16px;">场景: </span><span style="color:var(--text-dim);font-size:12px;">' + (analysis.scene_desc || '--') + '</span>';
    html += '</div>';

    // 文本结构拆解
    html += '<div style="padding:12px 16px;border-bottom:1px solid var(--border);">';
    html += '<div class="script-label">文本结构拆解</div>';
    html += '<div class="script-text"><b>钩子: </b>' + (textStruct.hook || '--') + '</div>';
    html += '<div class="script-text" style="margin-top:6px;"><b>正文: </b>' + (textStruct.body || '--') + '</div>';
    html += '<div class="script-text" style="margin-top:6px;"><b>行动号召: </b>' + (textStruct.cta || '--') + '</div>';
    html += '</div>';

    // 产品分析
    if (prod.product_category || prod.selling_points) {
        html += '<div style="padding:12px 16px;border-bottom:1px solid var(--border);">';
        html += '<div class="script-label">产品分析</div>';
        if (prod.product_category) html += '<div class="script-text"><b>品类: </b>' + prod.product_category + '</div>';
        if (prod.target_audience) html += '<div class="script-text" style="margin-top:4px;"><b>目标受众: </b>' + prod.target_audience + '</div>';
        if (prod.pain_points) html += '<div class="script-text" style="margin-top:4px;"><b>解决痛点: </b>' + prod.pain_points + '</div>';
        if (prod.selling_points) {
            var sps = Array.isArray(prod.selling_points) ? prod.selling_points : [prod.selling_points];
            html += '<div style="margin-top:6px;"><b>核心卖点: </b>';
            sps.forEach(function(sp, i) {
                html += '<span class="badge badge-primary" style="margin:2px 4px 2px 0;">' + (i+1) + '. ' + sp + '</span>';
            });
            html += '</div>';
        }
        html += '</div>';
    }

    // 营销策略
    if (mkt.trust_building || mkt.urgency_tactics || mkt.interaction_guide) {
        html += '<div style="padding:12px 16px;">';
        html += '<div class="script-label">营销策略</div>';
        if (mkt.trust_building) html += '<div class="script-text"><b>信任建立: </b>' + mkt.trust_building + '</div>';
        if (mkt.urgency_tactics) html += '<div class="script-text" style="margin-top:4px;"><b>紧迫感: </b>' + mkt.urgency_tactics + '</div>';
        if (mkt.interaction_guide) html += '<div class="script-text" style="margin-top:4px;"><b>互动引导: </b>' + mkt.interaction_guide + '</div>';
        html += '</div>';
    }

    html += '</div>';

    // 导出按钮
    html += '<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;">';
    html += '<button class="btn btn-secondary btn-sm" onclick="exportAnalysisExcel()" style="font-size:12px;">&#128196; 导出Excel报告</button>';
    html += '<button class="btn btn-secondary btn-sm" onclick="switchPanel(\'scripts\')" style="font-size:12px;">&#9997; 生成改编剧本</button>';
    html += '</div>';

    // 分镜脚本表格
    if (storyboard.length > 0) {
        html += '<div class="script-card" style="margin-top:16px;border-left:3px solid var(--accent);">';
        html += '<div class="script-card-header"><span class="script-ver">分镜脚本</span>';
        html += '<span style="font-size:12px;color:var(--text-muted);margin-left:8px;">共 ' + storyboard.length + ' 个分镜</span></div>';
        html += '<div style="overflow-x:auto;padding:0;">';
        html += '<table style="width:100%;border-collapse:collapse;font-size:12px;min-width:900px;">';
        html += '<thead><tr style="background:var(--bg-hover);text-align:left;">';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;">镜号</th>';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;width:140px;">关键帧</th>';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;">景别/构图</th>';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;">运镜</th>';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;">画面内容</th>';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;">人物&场景</th>';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;">台词</th>';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;">音效</th>';
        html += '<th style="padding:8px 10px;border-bottom:2px solid var(--border);white-space:nowrap;">时长</th>';
        html += '</tr></thead><tbody>';

        for (var si = 0; si < storyboard.length; si++) {
            var s = storyboard[si];
            var sn = s.shot_number || (si + 1);
            var frameUrl = frameMap[sn] || '';
            var rowBg = si % 2 === 0 ? '' : 'background:rgba(255,255,255,0.02);';

            html += '<tr style="' + rowBg + 'border-bottom:1px solid var(--border);">';
            html += '<td style="padding:8px 10px;vertical-align:top;font-weight:700;">' + sn + '</td>';

            // 关键帧图片
            html += '<td style="padding:6px 10px;vertical-align:top;">';
            if (frameUrl) {
                html += '<img src="' + frameUrl + '" style="width:120px;height:68px;object-fit:cover;border-radius:4px;border:1px solid var(--border);" alt="镜' + sn + '关键帧" loading="lazy">';
                html += '<div style="font-size:10px;color:var(--text-dim);margin-top:2px;">' + (s.key_frame_time || '--') + 's</div>';
            } else {
                html += '<div style="width:120px;height:68px;border-radius:4px;background:var(--bg-hover);display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:11px;">暂无帧图</div>';
            }
            html += '</td>';

            html += '<td style="padding:8px 10px;vertical-align:top;">' + (s.shot_type || '--') + '</td>';
            html += '<td style="padding:8px 10px;vertical-align:top;">' + (s.camera_movement || '--') + '</td>';
            html += '<td style="padding:8px 10px;vertical-align:top;">' + (s.visual_content || '--') + '</td>';
            html += '<td style="padding:8px 10px;vertical-align:top;">' + (s.character_scene || '--') + '</td>';
            html += '<td style="padding:8px 10px;vertical-align:top;">' + (s.dialogue || '--') + '</td>';
            html += '<td style="padding:8px 10px;vertical-align:top;">' + (s.sound_effect || '--') + '</td>';
            html += '<td style="padding:8px 10px;vertical-align:top;white-space:nowrap;">' + (s.duration_seconds || '--') + 's</td>';
            html += '</tr>';
        }

        html += '</tbody></table></div>';
        html += '</div>';
    }

    container.innerHTML = html;
}
