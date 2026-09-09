#!/bin/bash
# Smart Clip MCP - 启动 MCP Server（SSE 模式）
# 用法: ./serve.sh
# 启动后访问 http://localhost:8000

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 配置区 ──────────────────────────────────
LLM_API_KEY=""
LLM_BASE_URL="https://api.deepseek.com/v1"
LLM_MODEL="deepseek-chat"
WHISPER_MODE="local"
OPENAI_API_KEY=""
LANGUAGE="zh"
PORT=8000
# ── 配置区结束 ──────────────────────────────

if [ -z "$LLM_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ 请先编辑 serve.sh，填入 LLM_API_KEY 或 OPENAI_API_KEY"
    exit 1
fi

mkdir -p test-videos test-output

echo "🚀 Starting Smart Clip MCP Server on http://localhost:${PORT}"
echo "   MCP SSE endpoint: http://localhost:${PORT}/sse"

docker compose up -d \
    -e SMART_CLIP_LLM_API_KEY="${LLM_API_KEY}" \
    -e SMART_CLIP_LLM_BASE_URL="${LLM_BASE_URL}" \
    -e SMART_CLIP_LLM_MODEL="${LLM_MODEL}" \
    -e SMART_CLIP_WHISPER_MODE="${WHISPER_MODE}" \
    -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
    -e SMART_CLIP_LANGUAGE="${LANGUAGE}" \
    -e SMART_CLIP_PORT="${PORT}"
