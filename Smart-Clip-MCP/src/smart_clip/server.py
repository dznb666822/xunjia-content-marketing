"""MCP Server entry point.

Supports two transport modes:
  - stdio (default): for local MCP clients like Claude Desktop
  - sse: for Docker / remote access over HTTP

Usage:
  smart-clip-mcp                  # stdio mode
  smart-clip-mcp --transport sse  # SSE mode on port 8000
  smart-clip-mcp --transport sse --port 9000 --host 0.0.0.0
"""

from __future__ import annotations

import argparse
import os

from fastmcp import FastMCP

from smart_clip.tools.smart_clip import smart_clip_tool
from smart_clip.tools.repurpose import repurpose_tool
from smart_clip.tools.highlight_reel import highlight_reel_tool
from smart_clip.tools.analyze_content import analyze_content_tool
from smart_clip.tools.get_edit_plan import get_edit_plan_tool

UPLOAD_DIR = os.getenv("SMART_CLIP_UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
OUTPUT_DIR = os.getenv("SMART_CLIP_OUTPUT_DIR", os.path.join(os.getcwd(), "smart-clip-output"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

mcp = FastMCP(
    "smart-clip",
    version="0.1.0",
    instructions="AI-powered smart video clipping MCP server. "
    "Identifies highlight moments from long videos using subtitle analysis + LLM, "
    "then clips them into short-form content. "
    "Use POST /upload to upload videos, GET /output/{filename} to download results.",
)

# Register tools
mcp.tool(smart_clip_tool)
mcp.tool(repurpose_tool)
mcp.tool(highlight_reel_tool)
mcp.tool(analyze_content_tool)
mcp.tool(get_edit_plan_tool)


# ── HTTP endpoints for file transfer (SSE mode only) ──

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for Docker HEALTHCHECK."""
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok", "service": "smart-clip"})


@mcp.custom_route("/upload", methods=["POST"])
async def upload_video(request):
    """Accept multipart video upload, return server-side path for use in tools."""
    from starlette.responses import JSONResponse

    try:
        form = await request.form()
        file = form.get("file")
        if file is None:
            return JSONResponse({"error": "No 'file' field in form data"}, status_code=400)

        import uuid
        filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        dest = os.path.join(UPLOAD_DIR, filename)
        with open(dest, "wb") as f:
            f.write(await file.read())

        return JSONResponse({
            "success": True,
            "path": dest,
            "filename": filename,
            "size": os.path.getsize(dest),
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@mcp.custom_route("/output/{filename:path}", methods=["GET"])
async def download_output(request):
    """Serve a file from the output directory."""
    from starlette.responses import FileResponse, JSONResponse

    filename = request.path_params.get("filename", "")
    filepath = os.path.join(OUTPUT_DIR, filename)

    # Security: prevent directory traversal
    real_path = os.path.realpath(filepath)
    real_output = os.path.realpath(OUTPUT_DIR)
    if not real_path.startswith(real_output):
        return JSONResponse({"error": "Invalid path"}, status_code=403)

    if not os.path.exists(filepath):
        return JSONResponse({"error": "File not found"}, status_code=404)

    return FileResponse(filepath)


@mcp.custom_route("/uploads/{filename:path}", methods=["GET"])
async def serve_upload(request):
    """Serve a file from the upload directory (for checking uploaded files)."""
    from starlette.responses import FileResponse, JSONResponse

    filename = request.path_params.get("filename", "")
    filepath = os.path.join(UPLOAD_DIR, filename)

    real_path = os.path.realpath(filepath)
    real_upload = os.path.realpath(UPLOAD_DIR)
    if not real_path.startswith(real_upload):
        return JSONResponse({"error": "Invalid path"}, status_code=403)

    if not os.path.exists(filepath):
        return JSONResponse({"error": "File not found"}, status_code=404)

    return FileResponse(filepath)


def main():
    """Run the MCP server or test clip."""
    parser = argparse.ArgumentParser(description="Smart Clip MCP Server")
    sub = parser.add_subparsers(dest="command")

    # Default server mode (no subcommand)
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=os.getenv("SMART_CLIP_TRANSPORT", "stdio"),
        help="Transport mode: stdio (default) or sse (HTTP)",
    )
    parser.add_argument("--host", default=os.getenv("SMART_CLIP_HOST", "0.0.0.0"), help="SSE host")
    parser.add_argument("--port", type=int, default=int(os.getenv("SMART_CLIP_PORT", "8000")), help="SSE port")

    # Test subcommand
    test_parser = sub.add_parser("test", help="Run a quick clip test")
    test_parser.add_argument("video", help="Path to input video file")
    test_parser.add_argument("--intent", default="提取精彩片段", help="Editing intent")
    test_parser.add_argument("--count", type=int, default=5, help="Number of clips")
    test_parser.add_argument("--min", type=int, default=15, help="Min clip duration (seconds)")
    test_parser.add_argument("--max", type=int, default=90, help="Max clip duration (seconds)")
    test_parser.add_argument("--platform", default="original", help="Target platform")
    test_parser.add_argument("--output", default="./smart-clip-output", help="Output directory")
    test_parser.add_argument("--analyze-only", action="store_true", help="Only analyze, don't clip")
    test_parser.add_argument("--whisper-mode", default=os.getenv("SMART_CLIP_WHISPER_MODE", "local"), choices=["api", "local"], help="Whisper mode: local (faster-whisper) or api (OpenAI)")
    test_parser.add_argument("--whisper-model", default=os.getenv("SMART_CLIP_WHISPER_MODEL", "base"), help="Whisper model size: tiny/base/small/medium/large-v3")
    test_parser.add_argument("--language", default=os.getenv("SMART_CLIP_LANGUAGE", "zh"), help="Language code")
    test_parser.add_argument("--srt", default=None, help="Path to external SRT/VTT subtitle file (auto-detect if omitted)")

    args = parser.parse_args()

    if args.command == "test":
        _run_test(args)
    else:
        if args.transport == "sse":
            mcp.run(transport="sse", host=args.host, port=args.port)
        else:
            mcp.run()


def _run_test(args):
    """Run the test clip command."""
    import asyncio
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from smart_clip.tools.smart_clip import _run_smart_clip

    result = asyncio.run(_run_smart_clip(
        video_input=args.video,
        intent=args.intent,
        clip_count=args.count,
        clip_duration_min=args.min,
        clip_duration_max=args.max,
        platform=args.platform,
        with_subtitles=True,
        with_bgm=False,
        output_dir=args.output,
        template="default",
        analyze_only=args.analyze_only,
        srt_path=args.srt,
    ))

    import json
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
