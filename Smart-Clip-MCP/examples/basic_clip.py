"""Basic usage example for Smart Clip MCP."""

import asyncio
from smart_clip.tools.smart_clip import _run_smart_clip


async def main():
    # Basic smart clip
    result = await _run_smart_clip(
        video_path="input.mp4",
        intent="提取最精彩的5个片段",
        clip_count=5,
        clip_duration_min=15,
        clip_duration_max=60,
        platform="tiktok",
        with_subtitles=True,
        output_dir="./output",
    )

    print(f"Success: {result['success']}")
    for clip in result.get("clips", []):
        print(f"  Clip {clip['index']}: {clip['start']:.1f}s - {clip['end']:.1f}s | {clip['reason']}")


if __name__ == "__main__":
    asyncio.run(main())
