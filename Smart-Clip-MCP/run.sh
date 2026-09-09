#!/bin/bash
# Smart Clip MCP - 一键测试脚本
# 用法:
#   ./run.sh your_video.mp4                  # 完整剪辑
#   ./run.sh your_video.mp4 --analyze-only   # 只分析不剪辑
#   ./run.sh your_video.mp4 --count 3        # 只出 3 个片段
#
# 视频文件放在 test-videos/ 目录下，直接传文件名即可

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 配置区：改这里就行 ──────────────────────────────────
# LLM 配置（DeepSeek / OpenAI / 任何兼容接口）
LLM_API_KEY="sk-aae7d01bbb35437180dd5d60508eea3a"                        # 填你的 key
LLM_BASE_URL="https://api.deepseek.com/v1"  # DeepSeek; OpenAI 留空
LLM_MODEL="deepseek-chat"             # deepseek-chat / gpt-4o-mini

# Whisper 配置（语音转文字）
# - local: 本地跑 faster-whisper（免费，不用 API key，首次自动下载模型约 150MB）
# - api: 用 OpenAI Whisper API（需要 OPENAI_API_KEY）
WHISPER_MODE="local"
OPENAI_API_KEY=""                      # Whisper API 模式需要填

# 语言
LANGUAGE="zh"
# ── 配置区结束 ─────────────────────────────────────────

# 检查是否已配置
if [ -z "$LLM_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ 请先编辑 run.sh，填入 LLM_API_KEY 或 OPENAI_API_KEY"
    echo ""
    echo "   打开 run.sh，找到「配置区」修改："
    echo "   - 用 DeepSeek: 填 LLM_API_KEY，LLM_BASE_URL 保持默认"
    echo "   - 用 OpenAI:   填 OPENAI_API_KEY，LLM_BASE_URL 留空，LLM_MODEL 改为 gpt-4o-mini"
    exit 1
fi

# 首次构建
if ! docker image inspect smart-clip-mcp-smart-clip &>/dev/null; then
    echo "🔨 首次运行，构建 Docker 镜像（约 3-5 分钟）..."
    docker compose build
fi

# 创建目录
mkdir -p test-videos test-output

# 第一个参数是视频文件名，自动从 test-videos/ 查找
VIDEO="$1"
shift

if [ -z "$VIDEO" ]; then
    echo "用法: ./run.sh <视频文件名> [选项]"
    echo ""
    echo "示例:"
    echo "  ./run.sh demo.mp4"
    echo "  ./run.sh demo.mp4 --analyze-only"
    echo "  ./run.sh demo.mp4 --count 3"
    echo ""
    echo "视频文件请放在 test-videos/ 目录下"
    echo "当前可用视频:"
    ls test-videos/ 2>/dev/null | sed 's/^/  /' || echo "  (空)"
    exit 1
fi

if [ ! -f "test-videos/$VIDEO" ]; then
    echo "❌ 找不到 test-videos/$VIDEO"
    echo "   请先把视频文件放到 test-videos/ 目录下"
    exit 1
fi

# 执行
docker compose run --rm \
    -e SMART_CLIP_LLM_API_KEY="${LLM_API_KEY}" \
    -e SMART_CLIP_LLM_BASE_URL="${LLM_BASE_URL}" \
    -e SMART_CLIP_LLM_MODEL="${LLM_MODEL}" \
    -e SMART_CLIP_WHISPER_MODE="${WHISPER_MODE}" \
    -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
    -e SMART_CLIP_LANGUAGE="${LANGUAGE}" \
    -e HF_ENDPOINT="https://hf-mirror.com" \
    smart-clip \
    test --output /workspace/output/ /workspace/videos/"$VIDEO" "$@"
