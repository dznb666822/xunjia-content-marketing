# Smart Clip MCP

AI-powered smart video clipping MCP server. Input a long video + editing intent, output highlight short clips.

**Not another FFmpeg wrapper — it's the "editing brain".** Uses subtitle semantic analysis + LLM-driven decision making to identify highlight moments, with [mcp-video](https://github.com/KyaniteLabs/mcp-video) as the execution layer (FFmpeg fallback built-in).

## Features

- 🧠 **LLM-driven highlight detection** — analyzes subtitles to identify the most engaging moments
- 🎬 **5 MCP tools** — smart_clip, repurpose, highlight_reel, analyze_content, get_edit_plan
- 🎯 **Platform-adaptive** — auto-resize and format for TikTok, YouTube Shorts, Instagram Reels
- 📝 **Auto subtitles** — Whisper transcription + burn-in with platform-specific styling
- 🔊 **Audio analysis** — energy peaks and silence detection for precise cut points
- 👀 **Human-in-the-loop** — preview edit plans before execution
- 💰 **Low cost** — ¥0.8-1.16 per hour of video (50x cheaper than cloud alternatives)

## Quick Start

### Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) installed and on PATH
- [mcp-video](https://github.com/KyaniteLabs/mcp-video) (auto-installed as dependency)
- [Whisper](https://github.com/openai/whisper) model (auto-downloaded on first use)

### Install

```bash
pip install smart-clip-mcp
```

### Configure MCP Client

**Claude Code:**
```bash
claude mcp add smart-clip -- uvx --from smart-clip-mcp smart-clip-mcp
```

**Claude Desktop / Cursor:**
```json
{
  "mcpServers": {
    "smart-clip": {
      "command": "uvx",
      "args": ["--from", "smart-clip-mcp", "smart-clip-mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

### Usage

Ask your AI agent:

> "Extract 5 highlight clips from this 1-hour podcast video"

> "Turn this interview into 3 TikTok-ready shorts"

> "Analyze this video and tell me the most engaging moments"

## MCP Tools

| Tool | Description |
|---|---|
| `smart_clip` | Auto-detect highlights and clip them from a long video |
| `repurpose` | Convert long video to platform-specific short clips |
| `highlight_reel` | Compile highlights from multiple videos into a reel |
| `analyze_content` | Analyze video content without clipping (preview mode) |
| `get_edit_plan` | Generate an edit plan for human review before execution |

## Architecture

```
Video → [Analyzer] → [Planner] → [Executor] → Clips
          │              │            │
          │ Whisper       │ LLM        │ mcp-video
          │ librosa       │ Prompts    │ FFmpeg
          │ PySceneDetect │ Strategy   │
```

- **Analyzer** — Content understanding: Whisper transcription, audio energy analysis, scene detection
- **Planner** — Decision making: LLM highlight detection, template matching, strategy engine
- **Executor** — Clip generation: trim, merge, subtitles, platform adaptation via mcp-video

## Configuration

Create `~/.smart-clip/config.yaml`:

```yaml
analyzer:
  whisper:
    mode: local          # local | api
    model: large-v3
    language: zh
  audio:
    energy_percentile: 90
    silence_threshold: 0.3

planner:
  llm:
    model: gpt-4o-mini
    temperature: 0
  strategy:
    min_score: 6.0
    min_gap: 10

executor:
  output:
    format: mp4
    quality: high
```

## Development

```bash
# Clone
git clone git@github.com:Ambrose1/Smart-Clip-MCP.git
cd Smart-Clip-MCP

# Create venv
python -m venv .venv
source .venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run MCP server locally (stdio mode)
smart-clip-mcp

# Run MCP server with SSE transport (HTTP)
smart-clip-mcp --transport sse --port 8000
```

## Docker

### Build & Run

```bash
# Build image
docker build -t smart-clip-mcp .

# Run with SSE transport (accessible via HTTP)
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -v $(pwd)/videos:/workspace/videos \
  -v $(pwd)/output:/workspace/output \
  smart-clip-mcp
```

### Docker Compose (recommended)

```bash
# Set your API key
export OPENAI_API_KEY=sk-...

# Start
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### Test with MCP Inspector

Once the server is running in SSE mode:

```bash
# Install MCP Inspector
npx @modelcontextprotocol/inspector

# Connect to http://localhost:8000/sse
```

Or test with curl:

```bash
# List available tools
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}'
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
