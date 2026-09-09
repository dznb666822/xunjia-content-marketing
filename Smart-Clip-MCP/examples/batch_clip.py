"""Batch processing example for Smart Clip MCP."""

import asyncio
import os
from smart_clip.tools.smart_clip import _run_smart_clip
from smart_clip.tools.repurpose import repurpose_tool


async def batch_smart_clip(video_dir: str, output_base: str = "./batch-output"):
    """Process all videos in a directory."""
    videos = [
        f for f in os.listdir(video_dir)
        if f.endswith((".mp4", ".mov", ".mkv", ".avi"))
    ]

    print(f"Found {len(videos)} videos to process")

    for video in videos:
        video_path = os.path.join(video_dir, video)
        video_name = os.path.splitext(video)[0]
        output_dir = os.path.join(output_base, video_name)

        print(f"\nProcessing: {video}")
        result = await _run_smart_clip(
            video_path=video_path,
            intent="提取精彩片段",
            clip_count=3,
            platform="tiktok",
            output_dir=output_dir,
        )

        if result["success"]:
            print(f"  Generated {len(result['clips'])} clips")
        else:
            print(f"  Failed: {result.get('error')}")


async def batch_repurpose(video_dir: str, platform: str = "tiktok"):
    """Repurpose all videos for a specific platform."""
    videos = [
        os.path.join(video_dir, f)
        for f in os.listdir(video_dir)
        if f.endswith((".mp4", ".mov", ".mkv", ".avi"))
    ]

    for video_path in videos:
        result = repurpose_tool(
            video_path=video_path,
            platform=platform,
            clip_count=2,
            style="entertaining",
        )
        print(f"{os.path.basename(video_path)}: {len(result.get('clips', []))} clips")


if __name__ == "__main__":
    # Adjust path as needed
    asyncio.run(batch_smart_clip("./videos"))
