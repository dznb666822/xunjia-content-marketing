# -*- coding: utf-8 -*-
"""
视频智能混剪服务
输入文案 + 已分类视频库(含AI时间线) → AI 匹配最佳片段 → FFmpeg 拼接输出
"""
import os
import re
import json
import uuid
import subprocess
import threading
from loguru import logger

from services import tts as tts_service

# FFmpeg 路径探测（避免 PATH 不生效）
_FFMPEG_BIN = None
_FFPROBE_BIN = None


def _find_ffmpeg() -> tuple:
    """探测 ffmpeg/ffprobe 路径"""
    global _FFMPEG_BIN, _FFPROBE_BIN
    if _FFMPEG_BIN:
        return _FFMPEG_BIN, _FFPROBE_BIN

    # 优先使用官方安装位置
    import glob as _glob
    ffmpeg_home = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ffmpeg')
    candidates = _glob.glob(os.path.join(ffmpeg_home, 'ffmpeg-*', 'bin')) if os.path.isdir(ffmpeg_home) else []
    if candidates:
        candidates.sort(reverse=True)
        ffmpeg_exe = os.path.join(candidates[0], 'ffmpeg.exe')
        ffprobe_exe = os.path.join(candidates[0], 'ffprobe.exe')
        if os.path.exists(ffmpeg_exe) and os.path.exists(ffprobe_exe):
            _FFMPEG_BIN, _FFPROBE_BIN = ffmpeg_exe, ffprobe_exe
            return _FFMPEG_BIN, _FFPROBE_BIN

    # 降级使用 PATH
    _FFMPEG_BIN, _FFPROBE_BIN = 'ffmpeg', 'ffprobe'
    return _FFMPEG_BIN, _FFPROBE_BIN


# 存储混剪任务状态
_mashup_tasks = {}
_mashup_lock = threading.Lock()

# 上传视频存储目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'datas', 'uploads', 'videos')
MASHUP_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'datas', 'uploads', 'mashup_output')


def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(MASHUP_OUTPUT_DIR, exist_ok=True)


def get_video_duration(video_path: str) -> float:
    """用 ffprobe 获取视频时长（秒）"""
    try:
        _, ffprobe = _find_ffmpeg()
        result = subprocess.run(
            [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"获取视频时长失败 {video_path}: {e}")
    return 60.0


def get_video_aspect(video_path: str) -> str:
    """用 ffprobe 获取视频画面比例，返回 '9:16' / '16:9' / '1:1' / ''（未知）"""
    try:
        _, ffprobe = _find_ffmpeg()
        result = subprocess.run(
            [ffprobe, '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=width,height', '-of', 'csv=p=0', video_path],
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = [p.strip() for p in result.stdout.strip().split(',') if p.strip()]
            if len(parts) >= 2:
                w = int(float(parts[0]))
                h = int(float(parts[1]))
                if w <= 0 or h <= 0:
                    return ''
                ratio = w / h
                if ratio >= 1.2:
                    return '16:9'
                if ratio <= 0.8:
                    return '9:16'
                return '1:1'
    except Exception as e:
        logger.warning(f"获取视频比例失败 {video_path}: {e}")
    return ''


def split_script_to_segments(script: str) -> list:
    """将文案按句子/段落/逗号拆分"""
    # 第一遍：按句末标点拆分
    raw_parts = re.split(r'[。；;！!？?～\n]+', script)
    segments = []
    for part in raw_parts:
        part = part.strip()
        if not part or len(part) < 3:
            continue
        # 较长的句子按逗号再拆
        if len(part) > 15 and '，' in part:
            sub_parts = part.split('，')
            for sp in sub_parts:
                sp = sp.strip()
                if sp and len(sp) >= 2:
                    segments.append(sp)
        else:
            segments.append(part)

    if len(segments) <= 1 and script.strip():
        raw_parts = re.split(r'[，,。；;！!？?\n～]+', script)
        for part in raw_parts:
            part = part.strip()
            if part and len(part) >= 2:
                segments.append(part)

    return [{"index": i, "text": s} for i, s in enumerate(segments)]


def build_video_inventory(classified_videos: list) -> str:
    """
    构建视频库描述文本（包含AI时间线片段），供 AI 匹配使用。
    每个视频的每个时间线片段单独列出，AI 可以直接匹配到具体时间位置。
    """
    lines = []
    for vi, v in enumerate(classified_videos):
        cls = v.get("classification", {})
        timeline = v.get("timeline", {})
        if "error" in cls:
            continue

        # 视频概览
        topic = cls.get("topic", "")
        summary = cls.get("summary", "")
        lines.append(f"视频{vi}: [{topic}] {summary}")

        # 时间线片段
        segments = timeline.get("segments", [])
        if segments:
            for si, seg in enumerate(segments):
                if "error" in seg:
                    continue
                desc = seg.get("description", "")
                keywords = ",".join(seg.get("keywords", []))
                start = seg.get("start", 0)
                end = seg.get("end", 0)
                mood = seg.get("mood", "")
                scene = seg.get("scene_type", "")
                lines.append(f"  片段{si} [{start}s-{end}s]: {desc} | 关键词={keywords} | 情绪={mood} | 场景={scene}")
        else:
            # 没有时间线数据时，用整个视频作为单个片段
            duration = get_video_duration(v.get("path", ""))
            lines.append(f"  片段0 [0s-{duration:.0f}s]: {summary} | 主题={topic}")

    return "\n".join(lines)


def ai_match_script_to_videos(script_segments: list, video_inventory: str, classified_videos: list) -> list:
    """
    使用 AI 将每段文案匹配到最合适的视频＋具体时间线片段。
    返回格式: [{"segment_index": 0, "video_index": 2, "timeline_segment_index": 3, "reason": "..."}]
    """
    segments_text = "\n".join([f"[{s['index']}] {s['text']}" for s in script_segments])

    prompt = (
        '你是一名专业的视频剪辑师。请根据以下文案片段和视频库中每个视频的具体时间线片段描述，'
        '为每段文案选择最匹配的视频和具体片段。\n'
        '\n'
        '【文案片段】\n'
        f'{segments_text}\n'
        '\n'
        '【视频库 - 含具体时间线片段】\n'
        f'{video_inventory}\n'
        '\n'
        '请为每段文案选择最佳匹配（视频编号 + 片段编号都从0开始），以JSON格式输出：\n'
        '[\n'
        '  {"segment_index": 0, "video_index": 2, "timeline_segment_index": 3, "reason": "匹配理由(10字内)"},\n'
        '  {"segment_index": 1, "video_index": 0, "timeline_segment_index": 1, "reason": "匹配理由(10字内)"},\n'
        '  ...\n'
        ']\n'
        '\n'
        '匹配原则：根据文案语义找到画面内容最相关的具体时间片段，而非整个视频。\n'
        '只输出JSON数组，不要包含markdown代码块标记。'
    )

    try:
        import requests

        api_key = os.getenv('AI_API_KEY', '')
        api_url = os.getenv('AI_API_URL', 'https://ark.cn-beijing.volces.com/api/v3')
        model = os.getenv('AI_MODEL', 'doubao-seed-2-0-pro-260215')

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 3000
        }

        resp = requests.post(f'{api_url}/chat/completions', headers=headers, json=payload, timeout=120)

        if resp.status_code != 200:
            logger.error(f"AI匹配请求失败: {resp.status_code} {resp.text[:200]}")
            return _fallback_match(script_segments, classified_videos)

        data = resp.json()
        content = data['choices'][0]['message']['content']

        json_str = content
        if '```json' in content:
            parts = content.split('```json', 1)
            if len(parts) > 1:
                end_idx = parts[1].find('```')
                if end_idx != -1:
                    json_str = parts[1][:end_idx]
        elif '```' in content:
            parts = content.split('```', 2)
            if len(parts) >= 2:
                json_str = parts[1]

        matches = json.loads(json_str.strip())
        logger.info(f"AI匹配结果: {len(matches)} 段文案已匹配到具体时间片段")
        return matches

    except Exception as e:
        logger.error(f"AI匹配异常: {e}")
        return _fallback_match(script_segments, classified_videos)


def _fallback_match(script_segments: list, classified_videos: list) -> list:
    """降级匹配：按顺序循环分配视频的第一个片段"""
    valid = [(vi, v) for vi, v in enumerate(classified_videos)
             if "error" not in v.get("classification", {})]
    if not valid:
        valid = [(vi, v) for vi, v in enumerate(classified_videos)]

    matches = []
    for seg in script_segments:
        vi = valid[seg['index'] % len(valid)][0]
        vinfo = classified_videos[vi]
        timeline = vinfo.get("timeline", {})
        segments = timeline.get("segments", [])
        tl_idx = seg['index'] % max(len(segments), 1)
        matches.append({
            "segment_index": seg['index'],
            "video_index": vi,
            "timeline_segment_index": tl_idx,
            "reason": "自动循环分配"
        })
    return matches


def run_ffmpeg_mashup(script_segments: list, matches: list, classified_videos: list, task_id: str, tts_config: dict = None) -> dict:
    """
    执行 FFmpeg 混剪：根据 AI 匹配的具体时间戳截取每个片段并拼接。
    优先使用 AI 时间线分析返回的精确时间戳，降级时使用 ffprobe 获取的真实时长。
    当 tts_config.enabled=True 时，为每段文案合成配音并静音原声后叠加到对应镜头。
    """
    tts_config = tts_config or {}
    tts_enabled = bool(tts_config.get("enabled"))
    voice = tts_config.get("voice") or tts_service.DEFAULT_VOICE
    voice_name = tts_config.get("voice_name") or voice
    # 一倍速合成，不调速；片段尾部短空隙（空口），让衔接更自然
    gap = float(tts_config.get("gap", 0.4) or 0.0)
    clone_audio = tts_config.get("clone_audio") or ""
    clone_prompt_text = tts_config.get("clone_prompt_text") or ""

    def _synth(text, path, rate):
        if clone_audio:
            tts_service.clone_synthesize(text, path, clone_audio, clone_prompt_text, rate)
        else:
            tts_service.synthesize(text, path, voice, rate)

    ensure_dirs()
    task_dir = os.path.join(MASHUP_OUTPUT_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    num_segments = len(script_segments)
    if num_segments == 0:
        return {"error": "无文案片段"}

    segment_files = []
    match_map = {m['segment_index']: m for m in matches}

    for seg in script_segments:
        seg_idx = seg['index']
        match = match_map.get(seg_idx)
        if match is None:
            continue

        vid = match['video_index']
        if vid >= len(classified_videos):
            continue

        video_info = classified_videos[vid]
        video_path = video_info.get('path', '')
        if not video_path or not os.path.exists(video_path):
            continue

        # --- 基于 AI 时间线确定精确的起止时间 ---
        timeline = video_info.get("timeline", {})
        tl_segments = timeline.get("segments", [])
        tl_idx = match.get('timeline_segment_index', 0)
        video_duration = get_video_duration(video_path)

        tl_desc = ""
        if tl_segments and tl_idx < len(tl_segments):
            # 使用 AI 分析出的精确时间戳
            tl_seg = tl_segments[tl_idx]
            start_time = float(tl_seg.get("start", 0))
            end_time = float(tl_seg.get("end", video_duration))
            fallback_duration = max(1.0, end_time - start_time)
            tl_desc = tl_seg.get("description", "")
        else:
            # 降级：没有时间线数据时用整个视频或合理分段
            base_dur = min(8.0, video_duration / max(len(script_segments), 1))
            fallback_duration = max(2.0, min(15.0, base_dur))
            if video_duration <= fallback_duration:
                start_time = 0
            else:
                max_start = video_duration - fallback_duration
                start_time = (vid * 7 + seg_idx * 13) % max(int(max_start), 1)

        # 校验起始时间与可用时长
        if start_time >= video_duration:
            start_time = 0
        max_available = max(1.0, video_duration - start_time)
        fallback_duration = min(fallback_duration, max_available)

        seg_filename = f"seg_{seg_idx:03d}.mp4"
        seg_path = os.path.join(task_dir, seg_filename)
        ffmpeg, _ = _find_ffmpeg()

        clip_duration = fallback_duration
        narration_duration = 0.0
        voice_used = ""
        voice_path = os.path.join(task_dir, f"voice_{seg_idx:03d}.wav")

        # 配音：一倍速合成，不调速；台词实际时长即配音时长，片尾加短空隙
        if tts_enabled:
            try:
                _synth(seg['text'], voice_path, 1.0)
                narration_duration = get_video_duration(voice_path)
                if narration_duration <= 0:
                    raise RuntimeError("无法获取配音时长")

                # 不调速：画面时长 = 台词实际配音时长 + 片尾短空隙
                clip_duration = narration_duration + gap
                voice_used = voice
            except Exception as e:
                logger.warning(f"配音失败，改用原声 seg_{seg_idx}: {e}")
                narration_duration = 0.0
                voice_used = ""

        try:
            if tts_enabled and voice_used and narration_duration > 0 and os.path.exists(voice_path):
                # 静音原声，只保留配音
                video_only_path = os.path.join(task_dir, f"video_{seg_idx:03d}.mp4")
                cut_cmd = [
                    ffmpeg, '-y',
                    '-stream_loop', '-1',
                    '-ss', str(start_time),
                    '-i', video_path,
                    '-t', str(clip_duration),
                    '-an',
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-pix_fmt', 'yuv420p',
                    video_only_path
                ]
                subprocess.run(cut_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=60)
                if not os.path.exists(video_only_path):
                    raise RuntimeError("视频片段截取失败")

                mux_cmd = [
                    ffmpeg, '-y',
                    '-i', video_only_path,
                    '-i', voice_path,
                    '-map', '0:v:0',
                    '-map', '1:a:0',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-ar', '44100',
                    '-ac', '2',
                    '-shortest',
                    seg_path
                ]
                subprocess.run(mux_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=60)
            else:
                cut_cmd = [
                    ffmpeg, '-y',
                    '-ss', str(start_time),
                    '-i', video_path,
                    '-t', str(clip_duration),
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-ar', '44100',
                    '-ac', '2',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-pix_fmt', 'yuv420p',
                    seg_path
                ]
                subprocess.run(cut_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=60)

            if os.path.exists(seg_path):
                segment_files.append({
                    "file": seg_path,
                    "source_video": os.path.basename(video_path),
                    "segment_index": seg_idx,
                    "start_time": round(start_time, 1),
                    "duration": round(clip_duration, 1),
                    "text": seg['text'],
                    "reason": match.get('reason', ''),
                    "timeline_desc": tl_desc,
                    "voice": voice_used,
                    "voice_name": voice_name if voice_used else "",
                    "narration_duration": round(narration_duration, 1),
                })
            else:
                logger.warning(f"截取片段失败 seg_{seg_idx}")
        except Exception as e:
            logger.error(f"FFmpeg截取异常 seg_{seg_idx}: {e}")

    if not segment_files:
        return {"error": "未能生成任何有效片段"}

    # 拼接所有片段
    concat_list_path = os.path.join(task_dir, 'concat_list.txt')
    with open(concat_list_path, 'w', encoding='utf-8') as f:
        for sf in segment_files:
            escaped = sf['file'].replace('\\', '/')
            f.write(f"file '{escaped}'\n")

    output_path = os.path.join(task_dir, 'mashup_output.mp4')
    ffmpeg, _ = _find_ffmpeg()
    concat_cmd = [
        ffmpeg, '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_list_path,
        '-c', 'copy',
        output_path
    ]

    try:
        result = subprocess.run(concat_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=120)
        if result.returncode == 0 and os.path.exists(output_path):
            total_duration = get_video_duration(output_path)

            # 生成镜头台词对照文件
            mapping_path = os.path.join(task_dir, '镜头台词对照.txt')
            with open(mapping_path, 'w', encoding='utf-8') as f:
                f.write(f"混剪任务: {task_id}\n")
                f.write(f"总片段数: {len(segment_files)}\n")
                f.write(f"总时长: {round(total_duration, 1)}秒\n")
                if tts_enabled:
                    f.write(f"配音音色: {voice_name}\n")
                f.write("=" * 60 + "\n\n")
                for sf in segment_files:
                    seg_idx = sf['segment_index']
                    text = sf['text']
                    source = sf['source_video']
                    start = sf['start_time']
                    dur = sf['duration']
                    reason = sf.get('reason', '')
                    tl_desc = sf.get('timeline_desc', '')
                    f.write(f"镜头 {seg_idx + 1}/{len(segment_files)}\n")
                    f.write(f"  台词: {text}\n")
                    f.write(f"  来源: {source}  [{start}s - {start + dur:.1f}s]  ({dur}秒)\n")
                    if sf.get('voice'):
                        f.write(f"  配音: {sf.get('voice_name', '')} ({sf.get('narration_duration', 0)}秒)\n")
                    if reason:
                        f.write(f"  AI匹配理由: {reason}\n")
                    if tl_desc:
                        f.write(f"  画面描述: {tl_desc}\n")
                    f.write("\n")
            logger.info(f"镜头台词对照文件已生成: {mapping_path}")

            return {
                "success": True,
                "output_path": output_path,
                "output_filename": "mashup_output.mp4",
                "total_duration": round(total_duration, 1),
                "segments": segment_files,
                "segment_count": len(segment_files),
                "task_id": task_id,
                "mapping_file": mapping_path,
                "tts_enabled": tts_enabled,
                "voice": voice,
                "voice_name": voice_name,
            }
        else:
            return {"error": f"拼接失败: {result.stderr[:300]}"}
    except Exception as e:
        return {"error": f"拼接异常: {str(e)[:200]}"}


def start_mashup_task(script: str, classified_videos: list, on_complete=None, tts_config: dict = None) -> str:
    """
    启动混剪任务（异步），返回 task_id。
    classified_videos: [{"filename": ..., "path": ..., "classification": {...}, "timeline": {...}}, ...]
    on_complete: 可选回调，任务结束（成功或失败）时调用 on_complete(task_id, result)
    tts_config: 可选配音配置 {"enabled": bool, "voice": str, "voice_name": str, "rate": float}
    """
    task_id = str(uuid.uuid4())[:12]

    with _mashup_lock:
        _mashup_tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "result": None,
            "error": None
        }

    def _run():
        result = None
        try:
            with _mashup_lock:
                _mashup_tasks[task_id]["progress"] = 10

            # 1. 拆分文案
            script_segments = split_script_to_segments(script)
            logger.info(f"混剪[{task_id}]: 文案拆分为 {len(script_segments)} 段")
            with _mashup_lock:
                _mashup_tasks[task_id]["progress"] = 20

            # 2. 构建视频库描述（含AI时间线片段）
            video_inventory = build_video_inventory(classified_videos)
            with _mashup_lock:
                _mashup_tasks[task_id]["progress"] = 30

            # 3. AI 匹配到具体时间片段
            matches = ai_match_script_to_videos(script_segments, video_inventory, classified_videos)
            with _mashup_lock:
                _mashup_tasks[task_id]["progress"] = 50

            # 4. FFmpeg 按时间戳截取并拼接（含配音）
            result = run_ffmpeg_mashup(script_segments, matches, classified_videos, task_id, tts_config)

            with _mashup_lock:
                if "error" in result:
                    _mashup_tasks[task_id]["status"] = "failed"
                    _mashup_tasks[task_id]["error"] = result["error"]
                else:
                    _mashup_tasks[task_id]["status"] = "completed"
                    _mashup_tasks[task_id]["result"] = result
                    _mashup_tasks[task_id]["progress"] = 100
        except Exception as e:
            with _mashup_lock:
                _mashup_tasks[task_id]["status"] = "failed"
                _mashup_tasks[task_id]["error"] = str(e)[:200]
            result = {"error": str(e)[:200]}
        finally:
            # 任务结束（无论成功或失败）回调，用于持久化
            if on_complete:
                try:
                    on_complete(task_id, result or {})
                except Exception as e:
                    logger.error(f"混剪完成回调异常: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return task_id


def get_mashup_status(task_id: str) -> dict:
    """查询混剪任务状态"""
    with _mashup_lock:
        task = _mashup_tasks.get(task_id)
        if task is None:
            return {"status": "not_found", "error": "任务不存在"}
        return {
            "status": task["status"],
            "progress": task["progress"],
            "result": task.get("result"),
            "error": task.get("error")
        }


def get_mashup_output_path(task_id: str) -> str:
    """获取混剪输出文件路径"""
    task_dir = os.path.join(MASHUP_OUTPUT_DIR, task_id)
    output_path = os.path.join(task_dir, 'mashup_output.mp4')
    if os.path.exists(output_path):
        return output_path
    return ""
