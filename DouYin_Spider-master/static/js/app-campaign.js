// ==================== 营销策略Agent（内嵌版） ====================
// 所有 ID/类名使用 cp- 前缀，与主控制台隔离；API 调用指向 campaign_creator 服务(8686)。
(function(){
  var API = "http://127.0.0.1:8686";

  var CHANNELS = [
    ["social_media","社交媒体"],["email","邮件营销"],["display_ads","信息流广告"],
    ["influencer","KOL/达人"],["content_marketing","内容营销"],["video","视频短片"],
    ["search_ads","搜索广告"],["affiliate","联盟推广"]
  ];
  var TONES = [
    ["professional","专业"],["casual","轻松"],["playful","俏皮"],["luxury","轻奢"],
    ["educational","科普"],["motivational","励志"],["technical","技术流"],["friendly","亲切"]
  ];
  var STAGES = [
    {k:"research",     n:"01", t:"市场调研", en:"Research Agent",
     icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>',
     hint:"趋势 · 竞品 · 画像"},
    {k:"copywriter",   n:"02", t:"创意文案", en:"Copywriter Agent",
     icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
     hint:"标语 · 渠道文案 · 话题"},
    {k:"art_director", n:"03", t:"视觉方向", en:"Art Director Agent",
     icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9"/><circle cx="8.5" cy="10" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="7.5" r="1.2" fill="currentColor" stroke="none"/><circle cx="15.5" cy="10" r="1.2" fill="currentColor" stroke="none"/><path d="M12 21c-2-3.5 1-5.5 2.5-7"/></svg>',
     hint:"视觉体系 · 图像提示"},
    {k:"manager",      n:"04", t:"策略总监", en:"Manager Agent",
     icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4.5V3h6v1.5"/><path d="M9 10h6M9 14h6M9 18h4"/></svg>',
     hint:"总纲 · 排期 · KPI"}
  ];

  var root = null;
  function $(sel){ return root ? root.querySelector(sel) : null; }
  function $id(id){ return document.getElementById(id); }
  var state = { runId:null, es:null, engine:"langgraph", timer:null, t0:0, stages:{}, inited:false };

  function init(){
    if (state.inited) return;
    root = document.getElementById('panel-campaign');
    if (!root) return;
    state.inited = true;

    // 表单初始化
    $("#cpChannelChips").innerHTML = CHANNELS.map(function(c,i){
      return '<span class="cp-chip'+(i===0?' on':'')+'" data-v="'+c[0]+'">'+c[1]+'</span>';
    }).join("");
    $("#cpChannelChips").addEventListener("click",function(e){
      var c = e.target.closest(".cp-chip"); if(!c) return;
      c.classList.toggle("on");
    });
    $("#cpTone").innerHTML = TONES.map(function(t){ return '<option value="'+t[0]+'">'+t[1]+'</option>'; }).join("");
    $("#cpEngineBox").addEventListener("click",function(e){
      var el = e.target.closest(".cp-engine"); if(!el) return;
      root.querySelectorAll(".cp-engine").forEach(function(x){ x.classList.remove("on"); });
      el.classList.add("on"); state.engine = el.dataset.v;
    });
    root.querySelectorAll(".cp-tab").forEach(function(t){
      t.addEventListener("click",function(){
        root.querySelectorAll(".cp-tab").forEach(function(x){ x.classList.remove("on"); });
        root.querySelectorAll(".cp-tabpane").forEach(function(x){ x.classList.remove("on"); });
        t.classList.add("on");
        $("#cpPane-"+t.dataset.t).classList.add("on");
      });
    });

    renderPipeline();

    $("#cpBtnDemo").addEventListener("click",function(){
      $("#cpProductName").value = "AeroFlow Pro";
      $("#cpProductDesc").value = "An AI-powered smart air purifier that learns your air-quality preferences, adapts to pollen and pollution in real time, and integrates with Alexa and Google Home.";
      $("#cpAudience").value = "Health-conscious millennials and Gen-Z professionals aged 25-38 living in urban apartments who value clean air, modern design and smart-home tech.";
      $("#cpGoals").value = "Drive 10,000 pre-orders in 60 days via Kickstarter, build brand awareness, achieve 5% social-media engagement rate.";
      $("#cpBudget").value = "$50,000 - $100,000";
      $("#cpExtra").value = "Launching on Kickstarter first, then D2C website. Competitors: Dyson Pure Cool, Molekule Air, Coway Airmega. Differentiator: AI-learning feature.";
      toast("已填充示例配置");
    });

    $("#cpBtnGo").addEventListener("click", submitRun);
    refreshHistory();
  }

  // switchPanel 切入时初始化（懒加载）
  window.cpCampaignInit = init;

  /* ── 流水线渲染 ─────────────────────────────────── */
  function renderPipeline(){
    $("#cpPipeline").innerHTML = STAGES.map(function(s,i){
      var conn = i < STAGES.length-1
        ? '<div class="cp-conn" id="cpConn-'+STAGES[i+1].k+'"></div>' : "";
      return '<div class="cp-stage" id="cpCard-'+s.k+'">'+
        '<div class="num">'+s.n+'</div>'+
        '<div class="ic">'+s.icon+'</div>'+
        '<h3>'+s.t+'</h3><div class="en">'+s.en+'</div>'+
        '<div class="state-line"><span class="mark" id="cpMark-'+s.k+'">·</span><span id="cpStat-'+s.k+'">'+s.hint+'</span></div>'+
      '</div>'+conn;
    }).join("");
  }
  function setStage(k, st, info){
    info = info || "";
    var card = $id("cpCard-"+k), mark = $id("cpMark-"+k), stat = $id("cpStat-"+k);
    if(!card) return;
    card.classList.remove("running","done","error");
    if(st==="running"){
      card.classList.add("running");
      mark.textContent = "◐"; stat.textContent = "执行中…";
      var conn = $id("cpConn-"+k);
      if(k!==STAGES[0].k && conn) conn.classList.add("flow");
    }else if(st==="done"){
      card.classList.add("done");
      mark.textContent = "✓";
      stat.textContent = info || "完成";
      var conn2 = $id("cpConn-"+k);
      if(conn2) conn2.classList.remove("flow");
    }else if(st==="error"){
      card.classList.add("error");
      mark.textContent = "✕"; stat.textContent = info || "失败";
      var conn3 = $id("cpConn-"+k);
      if(conn3) conn3.classList.remove("flow");
    }else{
      mark.textContent = "·";
      var hint = "";
      STAGES.forEach(function(s){ if(s.k===k) hint = s.hint; });
      stat.textContent = hint;
    }
  }
  function resetPipeline(){
    STAGES.forEach(function(s){
      setStage(s.k,"idle");
      var conn = $id("cpConn-"+s.k);
      if(conn) conn.classList.remove("flow");
    });
  }

  /* ── 状态条 / 日志 / 提示 ───────────────────────── */
  function setStatus(mode, text){
    var p = $id("cpStatusPill");
    p.className = "cp-statuspill "+mode;
    $id("cpStatusText").textContent = text;
  }
  function fmtTime(ts){ var d=new Date(ts); return d.toTimeString().slice(0,8); }
  function log(type, msg){
    var box = $("#cpLogbox");
    var cls = {run_created:"cp-lc-created",stage_start:"cp-lc-start",stage_done:"cp-lc-done",
               run_complete:"cp-lc-complete",run_failed:"cp-lc-failed"}[type]||"";
    var line = document.createElement("div");
    line.className = "cp-log-line "+cls;
    line.innerHTML = '<span class="cp-log-time">'+fmtTime(Date.now())+'</span><span class="msg"></span>';
    line.querySelector(".msg").textContent = msg;
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
  }
  function toast(msg){
    var t = $id("cpToast"); t.textContent = msg; t.classList.add("show");
    setTimeout(function(){ t.classList.remove("show"); }, 2600);
  }
  function startElapsed(){
    state.t0 = Date.now();
    clearInterval(state.timer);
    state.timer = setInterval(function(){
      var s = Math.floor((Date.now()-state.t0)/1000);
      setStatus("running", "运行中 "+String(Math.floor(s/60)).padStart(2,"0")+":"+String(s%60).padStart(2,"0"));
    }, 500);
  }

  /* ── 提交运行 ───────────────────────────────────── */
  function submitRun(){
    if(!$("#cpProductName").value.trim() || !$("#cpProductDesc").value.trim()){
      $("#cpFName").classList.add("cp-shake");
      setTimeout(function(){ $("#cpFName").classList.remove("cp-shake"); },400);
      toast("请先填写产品名称和产品描述");
      return;
    }
    var channels = [];
    root.querySelectorAll("#cpChannelChips .cp-chip.on").forEach(function(c){ channels.push(c.dataset.v); });
    var body = {
      product_name: $("#cpProductName").value.trim(),
      product_description: $("#cpProductDesc").value.trim(),
      target_audience: $("#cpAudience").value.trim(),
      campaign_goals: $("#cpGoals").value.trim(),
      budget_range: $("#cpBudget").value.trim() || null,
      channels: channels,
      brand_voice: $("#cpTone").value,
      additional_context: $("#cpExtra").value.trim() || null,
      engine: state.engine
    };
    $("#cpBtnGo").disabled = true;
    fetch(API+"/api/campaigns",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})
    .then(function(res){
      if(!res.ok) return res.json().then(function(j){ throw new Error(j.detail||"提交失败"); });
      return res.json();
    })
    .then(function(r){
      showConfig(body, r.run_id);
      resetRun(r.run_id);
      connectSSE(r.run_id);
      refreshHistory();
    })
    .catch(function(err){ toast("提交失败："+err.message); })
    .finally(function(){ $("#cpBtnGo").disabled = false; });
  }

  function resetRun(runId){
    state.runId = runId;
    state.stages = {};
    $("#cpLogbox").innerHTML = "";
    resetPipeline();
    setStatus("running","已提交，排队中…");
    startElapsed();
    var logTab = null;
    root.querySelectorAll(".cp-tab").forEach(function(t){ if(t.dataset.t==="log") logTab = t; });
    if(logTab) logTab.click();
    log("run_created", "新任务已创建 · run_id="+runId+" · 引擎="+state.engine);
  }

  /* ── SSE ────────────────────────────────────────── */
  function connectSSE(runId){
    if(state.es) state.es.close();
    var es = new EventSource(API+"/api/runs/"+runId+"/events");
    state.es = es;
    var titles = {};
    STAGES.forEach(function(s){ titles[s.k]=s.t; });
    es.addEventListener("run_created", function(){ /* 已在 resetRun 记录 */ });
    es.addEventListener("stage_start", function(e){
      var d = JSON.parse(e.data);
      setStage(d.stage,"running");
      setStatus("running","运行中 · "+(titles[d.stage]||d.stage));
      log("stage_start","▸ "+(titles[d.stage]||d.stage)+" Agent 开始工作…");
    });
    es.addEventListener("stage_done", function(e){
      var d = JSON.parse(e.data);
      setStage(d.stage,"done",(d.title||titles[d.stage])+" 完成 · "+d.elapsed+"s · "+(d.chars||0)+" 字");
      log("stage_done","✓ "+(d.title||titles[d.stage])+" 完成（"+d.elapsed+"s，输出 "+(d.chars||0)+" 字符）");
    });
    es.addEventListener("run_complete", function(e){
      var d = JSON.parse(e.data);
      es.close();
      clearInterval(state.timer);
      setStatus("success","完成 · 用时 "+d.elapsed+"s");
      log("run_complete","★ 方案生成完毕（总用时 "+d.elapsed+"s），正在加载简报…");
      loadResult(runId);
      refreshHistory();
    });
    es.addEventListener("run_failed", function(e){
      var d = JSON.parse(e.data);
      es.close();
      clearInterval(state.timer);
      setStatus("failed","运行失败");
      log("run_failed","✕ 运行失败："+d.message);
      STAGES.forEach(function(s){
        if(!state.stages[s.k] || state.stages[s.k]==="running") setStage(s.k,"error","中断");
      });
      refreshHistory();
    });
    es.onerror = function(){ /* 断线自动重连由 EventSource 处理 */ };
  }

  /* ── 结果加载 / 渲染 ────────────────────────────── */
  function renderMD(md){
    if(window.marked && !window.__markedFailed){
      try{ return marked.parse(md); }catch(e){}
    }
    var pre = document.createElement("pre"); pre.className="cp-plain-md";
    pre.textContent = md; return pre.outerHTML;
  }
  function loadResult(runId){
    return fetch(API+"/api/runs/"+runId+"/result")
    .then(function(res){
      if(!res.ok){ toast("读取结果失败"); return; }
      return res.json();
    })
    .then(function(r){
      if(!r) return;
      if(r.markdown){
        $("#cpBriefEmpty").style.display="none";
        $("#cpBriefWrap").style.display="block";
        $("#cpBriefMd").innerHTML = renderMD(r.markdown);
        $("#cpRunInfo").textContent = "run_id="+r.run_id+" · "+(r.product||"")+" · "+r.status;
        $("#cpDlBox").innerHTML = (r.artifacts||[]).map(function(a){
          return '<a href="'+API+a.url+'" download>↓ '+a.path.split("/").pop()+'</a>';
        }).join("");
        var briefTab = null;
        root.querySelectorAll(".cp-tab").forEach(function(t){ if(t.dataset.t==="brief") briefTab = t; });
        if(briefTab) briefTab.click();
      }
      if(r.json){
        $("#cpJsonEmpty").style.display="none";
        $("#cpJsonView").style.display="block";
        $("#cpJsonView").textContent = JSON.stringify(r.json,null,2);
      }
      if(r.status==="failed" && r.failure_reason){
        log("run_failed","✕ 失败原因："+r.failure_reason);
        setStatus("failed","运行失败");
      }
    });
  }
  function showConfig(body, runId){
    $("#cpCfgEmpty").style.display="none";
    var cv = $("#cpCfgView"); cv.style.display="grid";
    var chMap = {}; CHANNELS.forEach(function(c){ chMap[c[0]]=c[1]; });
    var toneLabel = "—";
    TONES.forEach(function(t){ if(t[0]===body.brand_voice) toneLabel = t[1]; });
    var rows = [
      ["run_id", runId],
      ["产品名称", body.product_name],
      ["产品描述", body.product_description],
      ["目标受众", body.target_audience||"—"],
      ["营销目标", body.campaign_goals||"—"],
      ["预算范围", body.budget_range||"—"],
      ["投放渠道", body.channels.map(function(c){ return chMap[c]||c; }).join("、")],
      ["品牌语调", toneLabel],
      ["补充信息", body.additional_context||"—"],
      ["编排引擎", body.engine],
    ];
    cv.innerHTML = rows.map(function(kv){
      return '<dt>'+kv[0]+'</dt><dd>'+String(kv[1]).replace(/</g,"&lt;")+'</dd>';
    }).join("");
  }

  /* ── 历史记录 ───────────────────────────────────── */
  function refreshHistory(){
    fetch(API+"/api/runs")
    .then(function(res){ return res.json(); })
    .then(function(data){
      var runs = data.runs || [];
      var box = $("#cpHistList");
      if(!runs.length){ box.innerHTML = '<div class="cp-empty">暂无记录</div>'; return; }
      box.innerHTML = runs.map(function(r){
        var dot = r.status==="success"?"success":r.status==="failed"?"failed":"running";
        var t = (r.start_time||"").replace("T"," ").slice(5,16);
        return '<div class="cp-hist-item'+(r.run_id===state.runId?' active':'')+'" data-id="'+r.run_id+'" data-status="'+r.status+'">'+
          '<span class="cp-hist-dot '+dot+'"></span>'+
          '<div class="cp-hist-main">'+
            '<div class="cp-hist-product">'+(r.product||"(未命名)")+' <span style="color:var(--cp-faint);font-size:11px">· '+(r.engine||"")+'</span></div>'+
            '<div class="cp-hist-meta">'+r.run_id+' · '+t+' · '+r.status+'</div>'+
          '</div></div>';
      }).join("");
    }).catch(function(){});
  }
  document.addEventListener("click", function(e){
    var item = e.target.closest ? e.target.closest(".cp-hist-item") : null;
    if(!item || !root || !root.contains(item)) return;
    var id = item.dataset.id, st = item.dataset.status;
    root.querySelectorAll(".cp-hist-item").forEach(function(x){ x.classList.remove("active"); });
    item.classList.add("active");
    state.runId = id;
    resetPipeline();
    $("#cpLogbox").innerHTML = "";
    if(st==="running"){
      setStatus("running","正在恢复运行中任务…");
      startElapsed();
      connectSSE(id);
    }else{
      setStatus(st==="success"?"success":"failed", st==="success"?"历史任务 · 已完成":"历史任务 · 失败");
      log("run_created","查看历史运行 "+id);
      loadResult(id);
    }
  });
})();
